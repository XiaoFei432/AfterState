from pathlib import Path
import pytest
from afterstate.fixtures import reference_recover,oracle
from afterstate.protocol import capture_boundary,certify,restore_condition,score_clone,visible_request
from afterstate.state import StateStore,digest


@pytest.mark.parametrize("category",["patch","database","build","generation"])
def test_real_failures_and_reconstruction(category,tmp_path):
    root=tmp_path/"task"; store=StateStore(tmp_path/"store")
    b=capture_boundary(category,root,store,tmp_path/"fault")
    certificate=certify(b,root,store,mechanical_repeats=2,reference_repeats=1)
    states=certificate["state_fingerprints"]
    assert states["PRE"]==states["UNDO"]
    assert states["REAL"]==states["REINTRO"]
    assert states["PRE"]!=states["REAL"]
    requests=[]
    for condition in ["PRE","REAL"]:
        restore_condition(b,condition,root,store)
        requests.append(digest(visible_request(b)))
    assert requests[0]==requests[1]
    assert "protocol" not in visible_request(b)
    if category in {"patch","database"}:
        with pytest.raises(ValueError,match="POST ineligible"):
            restore_condition(b,"POST",root,store)


def test_oracle_clone_never_modifies_continuation(tmp_path):
    root=tmp_path/"task"; store=StateStore(tmp_path/"store")
    b=capture_boundary("database",root,store,tmp_path/"fault")
    snap=store.capture(root)
    scored=score_clone(b.site,snap,store)
    assert not scored["success"]
    assert store.capture(root).fingerprint==snap.fingerprint


def test_hidden_oracle_checks_extra_obligations(tmp_path):
    root=tmp_path/"task"; store=StateStore(tmp_path/"store")
    b=capture_boundary("patch",root,store,tmp_path/"fault")
    reference_recover(b.site,root,b.environment)
    (root/"b.txt.rej").write_text("leftover")
    scored=score_clone(b.site,store.capture(root),store)
    assert scored["functional"] and not scored["success"]
    assert not scored["state_obligations"]


def test_deleting_prior_work_is_a_scored_failure_not_a_crash(tmp_path):
    root=tmp_path/"task"; store=StateStore(tmp_path/"store")
    b=capture_boundary("generation",root,store,tmp_path/"fault")
    b.fault_file.write_text("pass")
    reference_recover(b.site,root,b.environment)
    (root/"prior-work.txt").unlink()
    scored=score_clone(b.site,store.capture(root),store)
    assert scored["functional"] and not scored["success"]


def test_missing_extra_artifact_does_not_erase_functional_success(tmp_path):
    root=tmp_path/"task"; store=StateStore(tmp_path/"store")
    b=capture_boundary("generation",root,store,tmp_path/"fault")
    b.fault_file.write_text("pass")
    reference_recover(b.site,root,b.environment)
    (root/"generated/index.json").unlink()
    scored=score_clone(b.site,store.capture(root),store)
    assert scored["functional"] and not scored["success"]
