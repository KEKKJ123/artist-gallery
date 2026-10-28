"""归档必须与撤销、日志、失败和中断恢复一起验证。"""

from pathlib import Path

import pytest
from PIL import Image

from artist_gallery.core import archiving, db, review
from artist_gallery.core import operations as ops
from artist_gallery.core.fileops import sha256_file
from artist_gallery.core.importer import import_files


@pytest.fixture
def lib(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    src = tmp_path / "src"
    src.mkdir()
    for name, color in [("123456789_p2.png", "red"), ("other.png", "blue")]:
        Image.new("RGB", (12, 10), color).save(src / name)
    import_files(root, [src])
    conn = db.open_library(root)
    source = review.detail(conn, 1)["sources"][0]
    review.save(
        conn,
        [1],
        {"1": ops.revision(conn, 1)},
        edits=[{"id": source["id"], "status": "confirmed", "page": None}],
    )
    yield root, conn
    conn.close()


def execute(root, conn, ids, force=False):
    plan = archiving.preview(conn, root, ids, force=force)
    return archiving.archive(conn, root, ids, plan["token"], force=force, confirmed=force)


def test_archive_and_undo_restore_files_and_sources(lib):
    root, conn = lib
    before = review.detail(conn, 1)
    raw = (root / before["rel_path"]).read_bytes()
    done = execute(root, conn, [1])
    after = review.detail(conn, 1)
    assert after["state"] == "archived" and after["rel_path"].startswith("images/archived/")
    assert not (root / before["rel_path"]).exists()
    assert (root / after["rel_path"]).read_bytes() == raw
    assert after["sources"] == before["sources"]
    archiving.undo(conn, root, done["operation_id"])
    assert review.detail(conn, 1) == before
    assert (root / before["rel_path"]).read_bytes() == raw
    assert not (root / after["rel_path"]).exists()


def test_mixed_batch_not_partially_executed(lib):
    root, conn = lib
    before = [review.detail(conn, i) for i in [1, 2]]
    plan = archiving.preview(conn, root, [1, 2])
    assert {e["image_id"] for e in plan["errors"]} == {2}
    with pytest.raises(ops.OperationError):
        archiving.archive(conn, root, [1, 2], plan["token"])
    assert [review.detail(conn, i) for i in [1, 2]] == before
    assert not list((root / "images/archived").iterdir())


def test_force_only_relaxes_metadata(lib):
    root, conn = lib
    plan = archiving.preview(conn, root, [2], force=True)
    with pytest.raises(ops.OperationError, match="显式"):
        archiving.archive(conn, root, [2], plan["token"], force=True)
    execute(root, conn, [2], force=True)
    item = review.detail(conn, 2)
    assert item["state"] == "archived" and item["sources"] == []


@pytest.mark.parametrize("fault", ["missing", "corrupt", "no_display"])
def test_force_cannot_bypass_file_faults(lib, fault):
    root, conn = lib
    file = root / review.detail(conn, 2)["rel_path"]
    if fault == "missing":
        file.unlink()
    elif fault == "corrupt":
        file.write_bytes(b"changed")
    else:
        with conn:
            conn.execute("UPDATE image_file SET is_display=0 WHERE image_id=2")
    plan = archiving.preview(conn, root, [2], force=True)
    assert plan["errors"]
    with pytest.raises(ops.OperationError):
        archiving.archive(conn, root, [2], plan["token"], force=True, confirmed=True)
    assert review.detail(conn, 2)["state"] == "inbox"


def test_collision_preserves_external_target_and_uses_suffix(lib):
    root, conn = lib
    occupied = root / "images/archived/123456789_P2.PNG"
    occupied.write_bytes(b"not ours")
    execute(root, conn, [1])
    assert review.detail(conn, 1)["rel_path"].endswith("_2.png")
    assert occupied.read_bytes() == b"not ours"


def test_stale_plan_rejected_before_intent(lib):
    root, conn = lib
    plan = archiving.preview(conn, root, [1])
    (root / "images/archived/123456789_p2.png").write_bytes(b"occupied")
    with pytest.raises(ops.ConflictError, match="计划"):
        archiving.archive(conn, root, [1], plan["token"])
    assert not ops.pending(conn)
    assert review.detail(conn, 1)["state"] == "inbox"


def test_undo_conflict_preserves_all(lib):
    root, conn = lib
    before = review.detail(conn, 1)
    done = execute(root, conn, [1])
    (root / before["rel_path"]).write_bytes(b"occupied")
    after = review.detail(conn, 1)
    with pytest.raises(ops.ConflictError, match="占用"):
        archiving.undo(conn, root, done["operation_id"])
    assert review.detail(conn, 1) == after
    assert (root / before["rel_path"]).read_bytes() == b"occupied"
    assert (root / after["rel_path"]).is_file()


@pytest.mark.parametrize("action", ["finish", "rollback"])
def test_delete_failure_recover_explicitly(lib, monkeypatch, action):
    root, conn = lib
    before = review.detail(conn, 1)
    original = Path.unlink

    def fail_old(path, *args, **kwargs):
        if path == root / before["rel_path"]:
            raise PermissionError("injected")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_old)
    with pytest.raises(ops.ConflictError, match="尚未完成"):
        execute(root, conn, [1])
    pending = ops.pending(conn)[0]
    assert (root / before["rel_path"]).is_file()
    assert (root / pending["moves"][0]["to"]).is_file()
    assert review.detail(conn, 1) == before
    with pytest.raises(ops.ConflictError, match="未完成"):
        review.save(conn, [1], {"1": ops.revision(conn, 1)}, text="")
    monkeypatch.setattr(Path, "unlink", original)
    with pytest.raises(ops.OperationError):
        archiving.recover(conn, root, pending["id"], action=action, confirmed=False)
    archiving.recover(conn, root, pending["id"], action=action, confirmed=True)
    assert not ops.pending(conn)
    if action == "finish":
        assert review.detail(conn, 1)["state"] == "archived"
        assert not (root / before["rel_path"]).exists()
    else:
        assert review.detail(conn, 1) == before
        assert not (root / pending["moves"][0]["to"]).exists()


def test_copy_failure_keeps_original_and_cancel(lib, monkeypatch):
    root, conn = lib
    before = review.detail(conn, 1)

    def fail(*args):
        raise OSError("injected copy")

    monkeypatch.setattr(archiving, "copy_verified", fail)
    with pytest.raises(ops.ConflictError):
        execute(root, conn, [1])
    wait = ops.pending(conn)[0]
    assert review.detail(conn, 1) == before
    archiving.recover(conn, root, wait["id"], action="rollback", confirmed=True)
    assert not ops.pending(conn)
    assert (root / before["rel_path"]).is_file()


def test_unknown_target_after_log_failure_never_deleted(lib, monkeypatch):
    root, conn = lib
    before = review.detail(conn, 1)
    original = archiving._persist

    def fail_before_record(*args):
        raise sqlite_error()

    def sqlite_error():
        import sqlite3

        return sqlite3.OperationalError("injected persist")

    monkeypatch.setattr(archiving, "_persist", fail_before_record)
    with pytest.raises(ops.ConflictError):
        execute(root, conn, [1])
    wait = ops.pending(conn)[0]
    target = root / wait["moves"][0]["to"]
    assert target.exists() and (root / before["rel_path"]).exists()
    monkeypatch.setattr(archiving, "_persist", original)
    with pytest.raises(ops.ConflictError):
        archiving.recover(conn, root, wait["id"], action="rollback", confirmed=True)
    assert target.exists() and (root / before["rel_path"]).exists()


def test_multiple_versions_move_and_undo_together(lib):
    root, conn = lib
    second = root / "images/_inbox/extra.png"
    Image.new("RGB", (20, 10), "white").save(second)
    with conn:
        conn.execute(
            "INSERT INTO image_file(image_id,rel_path,sha256,orig_name,is_display) "
            "VALUES(1,?,?,?,0)",
            ("images/_inbox/extra.png", sha256_file(second), "extra.png"),
        )
    done = execute(root, conn, [1])
    assert not second.exists()
    assert (root / "images/archived/extra.png").exists()
    archiving.undo(conn, root, done["operation_id"])
    assert second.exists()


def test_metadata_after_archive_does_not_unarchive(lib):
    root, conn = lib
    execute(root, conn, [1])
    review.save(
        conn, [1], {"1": ops.revision(conn, 1)}, text="https://x.com/a/status/1849000000000000000"
    )
    assert review.detail(conn, 1)["state"] == "archived"


@pytest.mark.parametrize("action", ["finish", "rollback"])
def test_interrupt_after_old_removal_reopens_and_recovers(lib, monkeypatch, action):
    root, conn = lib
    original = ops.update_log

    def interrupt_done(c, log_id, payload):
        if payload.get("status") == "done":
            raise KeyboardInterrupt()
        original(c, log_id, payload)

    monkeypatch.setattr(ops, "update_log", interrupt_done)
    before = review.detail(conn, 1)
    with pytest.raises(KeyboardInterrupt):
        execute(root, conn, [1])
    assert not (root / before["rel_path"]).exists()
    monkeypatch.setattr(ops, "update_log", original)
    other = db.open_library(root)
    try:
        waiting = ops.pending(other)[0]
        archiving.recover(other, root, waiting["id"], action=action, confirmed=True)
        assert not ops.pending(other)
        if action == "rollback":
            assert review.detail(other, 1) == before
        else:
            assert review.detail(other, 1)["state"] == "archived"
    finally:
        other.close()


def test_rollback_interrupted_after_cleanup_is_repeatable(lib, monkeypatch):
    root, conn = lib
    original = Path.unlink
    before = review.detail(conn, 1)

    def deny_old(path, *args, **kwargs):
        if path == root / before["rel_path"]:
            raise PermissionError("deny old")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny_old)
    with pytest.raises(ops.ConflictError):
        execute(root, conn, [1])
    waiting = ops.pending(conn)[0]

    def interrupt_after_target(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path == root / waiting["moves"][0]["to"]:
            raise KeyboardInterrupt()
        return result

    monkeypatch.setattr(Path, "unlink", interrupt_after_target)
    with pytest.raises(KeyboardInterrupt):
        archiving.recover(conn, root, waiting["id"], action="rollback", confirmed=True)
    monkeypatch.setattr(Path, "unlink", original)
    archiving.recover(conn, root, waiting["id"], action="rollback", confirmed=True)
    assert not ops.pending(conn)
    assert review.detail(conn, 1) == before


def test_pending_blocks_cli_import(lib, tmp_path, monkeypatch):
    root, conn = lib

    def fail(*args):
        raise OSError("copy failure")

    monkeypatch.setattr(archiving, "copy_verified", fail)
    with pytest.raises(ops.ConflictError):
        execute(root, conn, [1])
    src = tmp_path / "new.png"
    Image.new("RGB", (8, 8), "yellow").save(src)
    with pytest.raises(ops.ConflictError):
        import_files(root, [src])
    assert src.exists()


def test_intent_commit_failure_never_copies(lib, monkeypatch):
    root, conn = lib

    def fail(*args):
        raise RuntimeError("intent failed")

    monkeypatch.setattr(ops, "log_operation", fail)
    with pytest.raises(RuntimeError):
        execute(root, conn, [1])
    assert not list((root / "images/archived").iterdir())
    assert review.detail(conn, 1)["state"] == "inbox"
