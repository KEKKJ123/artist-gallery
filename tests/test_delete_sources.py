"""删除的文件系统结果与审计必须分别可追溯，不以事务代替文件恢复。"""

import json
from pathlib import Path

import pytest
from PIL import Image

from artist_gallery.cli import main
from artist_gallery.core import db
from artist_gallery.core.importer import count_pending_deletions, delete_sources, import_files


@pytest.fixture
def imported(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    source = tmp_path / "source.png"
    Image.new("RGB", (12, 12), (20, 30, 40)).save(source)
    return root, source, import_files(root, [source])


def logs(root):
    conn = db.connect(root)
    try:
        return [
            json.loads(r[0])
            for r in conn.execute(
                "SELECT payload FROM op_log WHERE kind='delete_source' ORDER BY id"
            )
        ]
    finally:
        conn.close()


def trigger(root, when, statement):
    conn = db.connect(root)
    try:
        with conn:
            conn.execute(
                f"CREATE TRIGGER fail_delete {when} ON op_log "
                f"WHEN NEW.kind='delete_source' BEGIN {statement}; END"
            )
    finally:
        conn.close()


def test_intent_failure_keeps_source_and_returns_error(imported):
    root, source, report = imported
    trigger(root, "BEFORE INSERT", "SELECT RAISE(ABORT,'audit insert failed')")
    result = delete_sources(report)
    assert len(result) == 1 and not result[0].deleted
    assert "日志失败" in result[0].message
    assert source.exists() and (root / report.items[0].rel_path).exists()
    assert logs(root) == []


def test_success_finishes_one_persisted_intent(imported):
    root, source, report = imported
    result = delete_sources(report)
    assert result[0].deleted and result[0].message == ""
    assert not source.exists()
    payloads = logs(root)
    assert len(payloads) == 1 and payloads[0]["status"] == "deleted"
    assert payloads[0]["sha256"] == report.items[0].sha256
    assert payloads[0]["kept"] == report.items[0].rel_path


def test_result_failure_preserves_pending_and_reports_actual_deletion(imported):
    root, source, report = imported
    trigger(root, "BEFORE UPDATE", "SELECT RAISE(ABORT,'audit update failed')")
    result = delete_sources(report)
    assert result[0].deleted and "已删除" in result[0].message
    assert "待核对" in result[0].message
    assert not source.exists() and (root / report.items[0].rel_path).exists()
    assert logs(root)[0]["status"] == "pending"
    conn = db.connect(root)
    try:
        assert count_pending_deletions(conn) == 1
    finally:
        conn.close()


def test_delete_failure_is_recorded_without_losing_source(imported, monkeypatch):
    root, source, report = imported
    unlink = Path.unlink

    def denied(path, *args, **kwargs):
        if path == source:
            raise PermissionError("denied")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)
    result = delete_sources(report)
    assert not result[0].deleted and source.exists()
    assert logs(root)[0]["status"] == "failed"


def test_interruption_keeps_durable_pending_without_automatic_retry(imported, monkeypatch):
    root, source, report = imported
    unlink = Path.unlink

    def interrupted(path, *args, **kwargs):
        if path == source:
            # 单独连接证明确已提交，而非同连接未提交写入。
            assert logs(root)[0]["status"] == "pending"
            raise KeyboardInterrupt
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", interrupted)
    with pytest.raises(KeyboardInterrupt):
        delete_sources(report)
    assert source.exists() and logs(root)[0]["status"] == "pending"
    db.open_library(root).close()  # 重新打开不自动重试删除
    assert source.exists()


def test_recheck_after_intent_detects_changed_source(imported, monkeypatch):
    import artist_gallery.core.importer as mod

    root, source, report = imported
    real = mod._source_delete_problem
    calls = 0

    def changed(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            assert logs(root)[0]["status"] == "pending"
            source.write_bytes(b"changed after intent commit")
        return real(*args)

    monkeypatch.setattr(mod, "_source_delete_problem", changed)
    result = delete_sources(report)
    assert not result[0].deleted
    assert source.read_bytes() == b"changed after intent commit"
    assert logs(root)[0]["status"] == "failed"


def test_cli_reports_deleted_but_unfinished_audit(imported, capsys):
    root, original, report = imported
    # 使用一个不同字节的新文件，保证 CLI 本次有可删除对象。
    source = original.with_name("second.png")
    Image.new("RGB", (12, 12), (70, 80, 90)).save(source)
    trigger(root, "BEFORE UPDATE", "SELECT RAISE(ABORT,'audit update failed')")
    assert main(["import", str(root), str(source), "--delete-source", "yes"]) == 1
    out = capsys.readouterr().out
    assert "待核对" in out and "已删除源文件 1" in out
    assert not source.exists()
    assert main(["status", str(root)]) == 0
    assert "待核对的源文件删除记录 1" in capsys.readouterr().out


def test_pending_counter_ignores_final_and_malformed_records(imported):
    root, _, _ = imported
    conn = db.connect(root)
    try:
        with conn:
            for payload in ("{}", "[]", "null", "not json", '{"status":"deleted"}'):
                conn.execute(
                    "INSERT INTO op_log(batch_id,kind,payload) VALUES ('x','delete_source',?)",
                    (payload,),
                )
        assert count_pending_deletions(conn) == 0
    finally:
        conn.close()
