import os
from pathlib import Path
import pytest
from afterstate.state import StateStore, Delta, Snapshot, safe_path


def test_delta_reconstructs_and_preserves_legitimate_prior_work(tmp_path):
    root=tmp_path/"task"; root.mkdir()
    store=StateStore(tmp_path/"store")
    (root/"prior").write_text("legitimate work")
    (root/"deleted").write_text("old")
    before=store.capture(root)
    (root/"deleted").unlink()
    (root/"nested").mkdir()
    (root/"nested/new").write_text("partial output")
    after=store.capture(root)
    delta=Delta.between(before,after)
    store.apply(root,delta,reverse=True)
    assert store.capture(root).fingerprint==before.fingerprint
    assert (root/"prior").read_text()=="legitimate work"
    store.apply(root,delta)
    assert store.capture(root).fingerprint==after.fingerprint
    clone=tmp_path/"clone"
    store.restore(after,clone)
    assert store.capture(clone).fingerprint==after.fingerprint
    assert (clone/"nested/new").stat().st_mtime_ns==after.entries["nested/new"]["mtime_ns"]


def test_delta_does_not_overwrite_unexpected_state(tmp_path):
    root=tmp_path/"task"; root.mkdir(); store=StateStore(tmp_path/"store")
    (root/"x").write_text("0"); before=store.capture(root)
    (root/"x").write_text("1"); after=store.capture(root)
    (root/"x").write_text("foreign change")
    with pytest.raises(ValueError,match="precondition"):
        store.apply(root,Delta.between(before,after),reverse=True)
    assert (root/"x").read_text()=="foreign change"


@pytest.mark.parametrize("name",["../outside","/absolute","C:/absolute","a/../../b","a\\b"])
def test_unsafe_paths(name,tmp_path):
    with pytest.raises(ValueError): safe_path(tmp_path,name)


def test_blob_corruption_detected_before_restore(tmp_path):
    root=tmp_path/"task"; root.mkdir(); (root/"x").write_text("x")
    store=StateStore(tmp_path/"store"); snap=store.capture(root)
    (store.directory/"blobs"/snap.entries["x"]["sha256"]).write_text("corrupt")
    with pytest.raises(ValueError,match="Corrupt"):
        store.restore(snap,tmp_path/"clone")


def test_store_must_not_be_inside_task(tmp_path):
    store=StateStore(tmp_path/"store")
    with pytest.raises(ValueError): store.capture(tmp_path)


@pytest.mark.skipif(os.name=="nt",reason="Symlinks on Windows require optional developer privileges")
def test_symlink_not_followed_and_inspection_cannot_escape(tmp_path):
    from afterstate.controllers import inspect_action
    root=tmp_path/"task"; root.mkdir()
    (tmp_path/"secret").write_text("secret")
    (root/"link").symlink_to(tmp_path/"secret")
    store=StateStore(tmp_path/"store"); snap=store.capture(root)
    assert snap.entries["link"]["kind"]=="symlink"
    with pytest.raises(ValueError): inspect_action({"type":"read","path":"link"},root)
