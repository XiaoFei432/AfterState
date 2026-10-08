from __future__ import annotations
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict


@dataclass
class Result:
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool = False

    def feedback(self):
        return {k: v for k, v in asdict(self).items() if k not in {"elapsed_seconds", "timed_out"}}


def execute(argv, root: Path, timeout=300.0, env=None, output_bytes=8192) -> Result:
    if timeout <= 0:
        raise ValueError("Command timeout must be positive")
    actual = [sys.executable if x == "{python}" else x for x in argv]
    child_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
                 "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1",
                 "GIT_CONFIG_NOSYSTEM": "1", **(env or {})}
    start = time.monotonic()

    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        p = subprocess.Popen(actual, cwd=root, env=child_env, stdout=out, stderr=err,
                             start_new_session=(os.name != "nt"))
        timed_out = False
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            p.kill()
            p.wait()
        out.seek(0)
        err.seek(0)
        def scrub(raw):
            text=raw.decode("utf-8",errors="replace")
            for value,replacement in [(str(root),"/task"),(str(root).replace("\\","/"),"/task"),(sys.executable,"{python}")]:
                text=re.sub(re.escape(value),lambda match: replacement,text,flags=re.IGNORECASE if os.name=="nt" else 0)
            return text
        return Result(list(argv), 124 if timed_out else p.returncode,
                      scrub(out.read(output_bytes)), scrub(err.read(output_bytes)),
                      time.monotonic() - start, timed_out)
