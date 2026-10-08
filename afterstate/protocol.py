from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile

from .execution import execute
from .fixtures import Site, prepare, reference_recover, oracle
from .state import Delta, StateStore, Snapshot, digest

PROTOCOLS = ("PRE", "REAL", "UNDO", "REINTRO", "WORKTREE", "OUTSIDE", "POST")


@dataclass
class Boundary:
    site: Site
    before: Snapshot
    after: Snapshot
    delta: Delta
    feedback: dict
    environment: dict
    fault_file: Path


def capture_boundary(category, root, store, fault_file):
    site = prepare(category, root)
    env = {"AFTERSTATE_FAULT_FILE": str(fault_file)}
    fault_file.write_text("fail")
    before = store.capture(root)
    failed = execute(site.command, root, env=env)
    after = store.capture(root)
    if failed.exit_code == 0 or before.fingerprint == after.fingerprint:
        raise ValueError("Not a partial-effect boundary")
    if score_clone(site, after, store)["success"]:
        raise ValueError("Completion contract already satisfied")
    return Boundary(site, before, after, Delta.between(before, after), failed.feedback(), env, fault_file)


def worktree_payload(path):

    return path.split("/")[0] not in {"packages", ".venv", "records.sqlite", "cache", ".git"}


def restore_condition(boundary, condition, root, store):
    b = boundary
    if condition not in PROTOCOLS:
        raise ValueError("Unknown state condition")
    store.restore(b.after if condition in {"REAL", "UNDO"} else b.before, root)
    if condition == "UNDO":
        store.apply(root, b.delta, reverse=True)
    elif condition == "REINTRO":
        store.apply(root, b.delta)
    elif condition in {"WORKTREE", "OUTSIDE"}:
        select = lambda p: worktree_payload(p) == (condition == "WORKTREE")
        store.apply(root, b.delta.subset(select))
    elif condition == "POST":
        if not b.site.legal_post:
            raise ValueError("POST ineligible: completing this command requires changing its input")
        b.fault_file.write_text("pass")
        result = execute(b.site.command, root, env=b.environment)
        if result.exit_code or not score_clone(b.site, store.capture(root), store)["success"]:
            raise ValueError("POST same-command completion failed")
    state = store.capture(root)
    if condition in {"PRE", "UNDO"} and state.fingerprint != b.before.fingerprint:
        raise ValueError("PRE/UNDO projection mismatch")
    if condition in {"REAL", "REINTRO"} and state.fingerprint != b.after.fingerprint:
        raise ValueError("REAL/REINTRO projection mismatch")

    b.fault_file.write_text("pass")
    return state


def score_clone(site, snapshot, store):
    with tempfile.TemporaryDirectory(prefix="afterstate-oracle-") as temporary:
        clone = Path(temporary) / "task"
        store.restore(snapshot, clone)
        return oracle(site, clone)


def visible_request(boundary, controller="Native", feedback="raw"):
    raw = boundary.feedback
    if feedback == "raw":
        failure = raw
    elif feedback == "neutral":

        failure = {"argv": raw["argv"], "exit_code": raw["exit_code"],
                   "diagnostic": boundary.site.fault_class}
    elif feedback == "terse":
        failure = {"tool": raw["argv"][0], "exit_code": raw["exit_code"],
                   "fault_class": boundary.site.fault_class}
    else:
        raise ValueError("Unknown feedback variant")
    return {"task": boundary.site.task, "history": [{"command": boundary.site.command, "result": failure}],
            "controller": controller, "cwd": "/task"}


def certify(boundary, root, store, mechanical_repeats=5, reference_repeats=3):
    if mechanical_repeats < 1 or reference_repeats < 1:
        raise ValueError("Certification repetitions must be positive")
    b = boundary
    mechanics = []
    for _ in range(mechanical_repeats):
        store.restore(b.before, root)
        b.fault_file.write_text("fail")
        result = execute(b.site.command, root, env=b.environment)
        snapshot = store.capture(root)
        ok = result.exit_code == b.feedback["exit_code"] and snapshot.fingerprint == b.after.fingerprint
        if not ok:
            raise ValueError(f"Mechanical replay failed for {b.site.site_id}")
        mechanics.append(snapshot.fingerprint)
    repairs = []
    for _ in range(reference_repeats):
        restore_condition(b, "REAL", root, store)
        reference_recover(b.site, root, b.environment)
        scored = score_clone(b.site, store.capture(root), store)
        if not scored["success"]:
            raise ValueError("Reference recovery failed its oracle")
        repairs.append(scored)
    fingerprints = {}
    for condition in PROTOCOLS:
        if condition == "POST" and not b.site.legal_post:
            continue
        fingerprints[condition] = restore_condition(b, condition, root, store).fingerprint
    return {"site_id": b.site.site_id, "origin": b.site.origin,
            "mechanical_repeats": len(mechanics), "reference_repeats": len(repairs),
            "state_fingerprints": fingerprints, "certified": True,
            "projection": "bytes, paths, modes, symlink targets; excludes mtime from equality",
            "first_request_sha256": digest(visible_request(b)),
            "post_eligible": b.site.legal_post,
            "changed_paths": [p for p in b.delta.before if b.before.projection().get(p) != b.after.projection().get(p)]}
