import os
import pytest
from afterstate.execution import execute


def test_failure_does_not_rollback_partial_files(tmp_path):
    result=execute(["{python}","-c","from pathlib import Path; Path('partial').write_text('retained'); raise SystemExit(3)"],tmp_path)
    assert result.exit_code==3
    assert (tmp_path/"partial").read_text()=="retained"


def test_command_timeout_and_output_limit(tmp_path):
    result=execute(["{python}","-u","-c","import time; print('x'*10000); time.sleep(5)"],tmp_path,timeout=.5,output_bytes=100)
    assert result.timed_out and result.exit_code==124
    assert len(result.stdout.encode())<=100


@pytest.mark.skipif(os.name!="nt",reason="Windows paths are case-insensitive")
def test_windows_lowercased_tool_paths_are_anonymized(tmp_path):
    result=execute(["{python}","-c","from pathlib import Path; print(str(Path.cwd()).lower())"],tmp_path)
    assert result.stdout.strip()=="/task"
