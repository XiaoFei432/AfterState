from __future__ import annotations
import base64
from contextlib import closing
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import textwrap
import zipfile
from dataclasses import dataclass

from .execution import execute


CATEGORIES = ("package", "venv", "patch", "database", "build", "generation")


@dataclass
class Site:
    site_id: str
    category: str
    task: str
    command: list[str]
    legal_post: bool
    fault_class: str
    origin: str = "new_controlled_demonstration"

    @property
    def repository(self):
        return "demo-" + self.category


def write(root, name, text):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8", newline="\n")


def wheel(root: Path, name: str):
    version = "1.0.0"
    meta = name + "-" + version + ".dist-info/"
    files = {
        name + "/__init__.py": b"VALUE = 42\n",
        meta + "METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode(),
        meta + "WHEEL": b"Wheel-Version: 1.0\nGenerator: afterstate-demo\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    rows = []
    for path, data in files.items():
        sha = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append([path, "sha256=" + sha, str(len(data))])
    rows.append([meta + "RECORD", "", ""])
    out = io.StringIO(newline="")
    csv.writer(out).writerows(rows)
    files[meta + "RECORD"] = out.getvalue().encode()
    path = root / "wheels" / f"{name}-{version}-py3-none-any.whl"
    path.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for filename, data in files.items():
            info = zipfile.ZipInfo(filename, (2020, 1, 1, 0, 0, 0))
            z.writestr(info, data)


FAULT_HELPER = '''
import os
from pathlib import Path
def fault():
    return Path(os.environ["AFTERSTATE_FAULT_FILE"]).read_text().strip() == "fail"
'''


def prepare(category: str, root: Path) -> Site:
    if category not in CATEGORIES:
        raise ValueError("Unknown demonstration category")
    root.mkdir(parents=True, exist_ok=True)
    write(root, "prior-work.txt", "legitimate work before the failed command\n")
    command = ["{python}", "operation.py"]
    legal_post = category not in {"patch", "database"}
    if category == "package":
        wheel(root, "demo_alpha")
        wheel(root, "demo_beta")
        write(root, "operation.py", FAULT_HELPER + '''
import subprocess, sys
for name in ["demo_alpha", "demo_beta"]:
    if name == "demo_beta" and fault():
        raise SystemExit("controlled package source unavailable")
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
                    "--no-compile", "--no-cache-dir", "--upgrade", "--target", "packages",
                    "wheels/" + name + "-1.0.0-py3-none-any.whl"], check=True)
''')
        task = "Install both local demo wheels in packages/, ensure both import with VALUE=42, and preserve prior-work.txt."
    elif category == "venv":
        write(root, "operation.py", FAULT_HELPER + '''
import venv
venv.EnvBuilder(with_pip=False, symlinks=False).create(".venv")
if fault():
    raise SystemExit("controlled activation configuration unavailable")
Path("environment.json").write_text('{"ready": true, "python": ".venv"}\\n')
''')
        task = "Create a usable isolated .venv interpreter and environment.json with ready=true; preserve prior-work.txt. No pip is required."
    elif category == "patch":
        write(root, "a.txt", "old-a\n")
        write(root, "b.txt", "diverged-b\n")
        write(root, "change.patch", """
            diff --git a/a.txt b/a.txt
            --- a/a.txt
            +++ b/a.txt
            @@ -1 +1 @@
            -old-a
            +new-a
            diff --git a/b.txt b/b.txt
            --- a/b.txt
            +++ b/b.txt
            @@ -1 +1 @@
            -old-b
            +new-b
        """)
        command = ["git", "apply", "--reject", "change.patch"]
        task = "Apply the intended changes: a.txt=new-a and b.txt=new-b; remove rejected patch files and preserve prior-work.txt."
    elif category == "database":
        with closing(sqlite3.connect(root / "records.sqlite")) as db, db:
            db.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE prior (value TEXT)")
            db.execute("INSERT INTO prior VALUES ('keep')")
        write(root, "operation.py", '''
import sqlite3
db = sqlite3.connect("records.sqlite", isolation_level=None)
try:
    db.execute("INSERT INTO records VALUES (1, 'Alice')")
    db.execute("INSERT INTO records VALUES (1, 'Bob')")
finally:
    db.close()
''')
        task = "Complete migration with records exactly [(1,'Alice'),(2,'Bob')], preserve prior table and prior-work.txt."
    elif category == "build":
        write(root, "source/alpha.py", "VALUE = 21\n")
        write(root, "source/beta.py", "VALUE = 2\n")
        write(root, "operation.py", FAULT_HELPER + '''
import hashlib, json, py_compile
Path("cache").mkdir(exist_ok=True)
for name in ["alpha", "beta"]:
    src = Path("source/" + name + ".py")
    obj = Path("cache/" + name + ".pyc")
    key = hashlib.sha256(src.read_bytes()).hexdigest()
    stamp = Path("cache/" + name + ".sha256")
    if not (obj.exists() and stamp.exists() and stamp.read_text() == key):
        py_compile.compile(str(src), cfile=str(obj), doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        stamp.write_text(key)
    if name == "alpha" and fault():
        raise SystemExit("controlled build interrupted after first compiled unit")
Path("build.json").write_text(json.dumps({"units": ["alpha", "beta"]}))
''')
        task = "Compile alpha and beta into cache/*.pyc and create build.json listing both units. Validate the compiled product 21*2=42; preserve prior-work.txt."
    else:
        write(root, "operation.py", FAULT_HELPER + '''
Path("generated").mkdir(exist_ok=True)
Path("generated/header.txt").write_text("HEADER\\n")
if fault():
    raise SystemExit("controlled generation interrupted after header")
Path("generated/body.txt").write_text("BODY\\n")
Path("generated/index.json").write_text('["header.txt", "body.txt"]\\n')
''')
        task = "Generate header.txt=HEADER, body.txt=BODY and index.json listing both in generated/; preserve prior-work.txt."
    return Site("demo-" + category + "-001", category, task, command, legal_post,
                "intrinsic_input_error" if not legal_post else "controlled_external_fault")


def reference_recover(site: Site, root: Path, env: dict):
    if site.category == "patch":
        write(root, "a.txt", "new-a\n")
        write(root, "b.txt", "new-b\n")
        for p in root.glob("*.rej"):
            p.unlink()
        return
    if site.category == "database":
        with closing(sqlite3.connect(root / "records.sqlite")) as db, db:
            db.execute("INSERT OR REPLACE INTO records VALUES (1, 'Alice')")
            db.execute("INSERT OR REPLACE INTO records VALUES (2, 'Bob')")
        return
    result = execute(site.command, root, env=env)
    if result.exit_code:
        raise RuntimeError("Reference recovery failed: " + result.stderr)


def oracle(site: Site, root: Path) -> dict:

    functional = False
    try:
        extra = (root / "prior-work.txt").read_text() == "legitimate work before the failed command\n"
    except (OSError, UnicodeError):
        extra = False
    try:
        if site.category == "package":
            result = execute(["{python}", "-I", "-c", "import sys; sys.path.insert(0,'packages'); import demo_alpha,demo_beta; assert demo_alpha.VALUE == demo_beta.VALUE == 42"], root)
            functional = result.exit_code == 0
            extra &= all((root / "packages" / (n + "-1.0.0.dist-info") / "METADATA").is_file()
                         for n in ["demo_alpha", "demo_beta"])
        elif site.category == "venv":
            py = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            result = execute([str(py), "-I", "-c", "import sys; assert sys.prefix != sys.base_prefix"], root)
            functional = result.exit_code == 0
            extra &= json.loads((root / "environment.json").read_text()).get("ready") is True
        elif site.category == "patch":
            functional = all((root / f"{n}.txt").read_text() == f"new-{n}\n" for n in ["a", "b"])
            extra &= not list(root.glob("*.rej"))
        elif site.category == "database":
            with closing(sqlite3.connect(root / "records.sqlite")) as db, db:
                rows = db.execute("SELECT id,value FROM records ORDER BY id").fetchall()
                functional = rows == [(1, "Alice"), (2, "Bob")]
                extra &= db.execute("SELECT value FROM prior").fetchall() == [("keep",)]
                extra &= db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        elif site.category == "build":
            code = "from importlib.machinery import SourcelessFileLoader as L; a=L('a','cache/alpha.pyc').load_module(); b=L('b','cache/beta.pyc').load_module(); assert a.VALUE*b.VALUE == 42"
            functional = execute(["{python}", "-I", "-c", code], root).exit_code == 0
            extra &= json.loads((root / "build.json").read_text())["units"] == ["alpha", "beta"]
            for n in ["alpha", "beta"]:
                extra &= (root / "cache" / (n + ".sha256")).read_text() == hashlib.sha256((root / "source" / (n + ".py")).read_bytes()).hexdigest()
        else:
            functional = all((root / "generated" / (n + ".txt")).read_text() == n.upper() + "\n" for n in ["header", "body"])
            extra &= json.loads((root / "generated/index.json").read_text()) == ["header.txt", "body.txt"]
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):


        extra = False
    return {"functional": bool(functional), "state_obligations": bool(extra),
            "success": bool(functional and extra)}
