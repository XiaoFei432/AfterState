from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
from dataclasses import dataclass


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def safe_path(root: Path, name: str) -> Path:
    p = PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
        raise ValueError(f"Unsafe relative state path: {name!r}")
    target = root.joinpath(*p.parts)

    for parent in target.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError(f"Symlink ancestor: {name!r}")
    return target


@dataclass(frozen=True)
class Snapshot:
    entries: dict

    def projection(self) -> dict:

        return {p: {k: v for k, v in e.items() if k != "mtime_ns"}
                for p, e in sorted(self.entries.items())}

    @property
    def fingerprint(self) -> str:
        return digest(self.projection())


class StateStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory).resolve()
        (self.directory / "blobs").mkdir(parents=True, exist_ok=True)

    def capture(self, root: Path) -> Snapshot:
        root = root.resolve()
        if self.directory == root or root in self.directory.parents:
            raise ValueError("Snapshot storage must be outside task state")
        entries = {}

        def visit(folder: Path):
            for p in sorted(folder.iterdir()):
                s = p.lstat()
                name = p.relative_to(root).as_posix()
                e = {"mode": stat.S_IMODE(s.st_mode), "mtime_ns": s.st_mtime_ns}
                if p.is_symlink():
                    e.update(kind="symlink", target=os.readlink(p))
                elif p.is_dir():
                    e["kind"] = "directory"
                elif p.is_file():
                    if s.st_nlink > 1:
                        raise ValueError(f"Hard links are unsupported: {name}")
                    content = p.read_bytes()
                    sha = hashlib.sha256(content).hexdigest()
                    blob = self.directory / "blobs" / sha
                    if not blob.exists():
                        blob.write_bytes(content)
                    e.update(kind="file", sha256=sha, size=len(content))
                else:
                    raise ValueError(f"Unsupported special file: {name}")
                entries[name] = e
                if e["kind"] == "directory":
                    visit(p)
        visit(root)
        return Snapshot(entries)

    def save(self, snapshot: Snapshot, name: str) -> None:
        safe_path(self.directory, name + ".json").write_text(
            json.dumps(snapshot.entries, indent=2, sort_keys=True), encoding="utf-8")

    def _validate(self, snapshot: Snapshot):
        for name, e in snapshot.entries.items():
            safe_path(self.directory, name)
            if e["kind"] not in {"file", "directory", "symlink"}:
                raise ValueError("Unsupported snapshot entry")
            if e["kind"] == "file":
                sha = e["sha256"]
                if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                    raise ValueError("Invalid blob identifier")
                content = (self.directory / "blobs" / sha).read_bytes()
                if hashlib.sha256(content).hexdigest() != sha:
                    raise ValueError("Corrupt snapshot blob")
            for parent in PurePosixPath(name).parents:
                if str(parent) == ".":
                    break
                if snapshot.entries.get(str(parent), {}).get("kind") != "directory":
                    raise ValueError("Snapshot has missing/non-directory ancestor")

    def restore(self, snapshot: Snapshot, root: Path):
        root = root.resolve()
        if root == self.directory or root in self.directory.parents or self.directory in root.parents:
            raise ValueError("Task state and snapshot store must be disjoint")
        self._validate(snapshot)
        root.mkdir(parents=True, exist_ok=True)
        current = self.capture(root)
        self.apply(root, Delta.between(current, snapshot), verify=True)

    def apply(self, root: Path, delta: "Delta", reverse=False, verify=True):
        root = root.resolve()
        before, after = (delta.after, delta.before) if reverse else (delta.before, delta.after)
        current = self.capture(root)
        if verify:
            for name, expected in before.items():
                got = current.entries.get(name)
                semantic = lambda e: {k: v for k, v in e.items() if k != "mtime_ns"} if e else None
                if semantic(got) != semantic(expected):
                    raise ValueError(f"Delta precondition failed: {name}")
        merged = dict(current.entries)
        for name, entry in after.items():
            if entry is None:
                merged.pop(name, None)
            else:
                merged[name] = entry
        self._validate(Snapshot(merged))

        for name in sorted(before, key=lambda x: (x.count("/"), x), reverse=True):
            old, new = before[name], after[name]
            p = safe_path(root, name)
            if old and (new is None or old["kind"] != new["kind"] or old["kind"] != "directory"):
                if p.is_symlink() or p.is_file():
                    p.unlink()
                elif p.is_dir():
                    p.rmdir()
        for name in sorted(after, key=lambda x: (x.count("/"), x)):
            e = after[name]
            if e is None:
                continue
            p = safe_path(root, name)
            if e["kind"] == "directory":
                p.mkdir(exist_ok=True)
            elif e["kind"] == "symlink":
                os.symlink(e["target"], p)
            else:
                p.write_bytes((self.directory / "blobs" / e["sha256"]).read_bytes())
            if e["kind"] != "symlink":
                os.chmod(p, e["mode"])

        for name, e in sorted(merged.items(), key=lambda kv: kv[0].count("/"), reverse=True):
            if e["kind"] != "symlink":
                os.utime(safe_path(root, name), ns=(e["mtime_ns"], e["mtime_ns"]))


@dataclass(frozen=True)
class Delta:
    before: dict
    after: dict

    @classmethod
    def between(cls, before: Snapshot, after: Snapshot) -> "Delta":
        keys = sorted(set(before.entries) | set(after.entries))
        changed = [k for k in keys if before.entries.get(k) != after.entries.get(k)]
        return cls({k: before.entries.get(k) for k in changed},
                   {k: after.entries.get(k) for k in changed})

    def subset(self, predicate) -> "Delta":
        keys = [k for k in self.before if predicate(k)]
        return Delta({k: self.before[k] for k in keys}, {k: self.after[k] for k in keys})
