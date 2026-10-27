"""拆分后的请求资源必须保持隔离，并在异常时释放。"""

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from starlette.testclient import TestClient

from artist_gallery.core import db
from artist_gallery.server.app import create_app
from artist_gallery.server.context import connection


def test_two_apps_keep_separate_libraries(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    for root in (a, b):
        db.init_library(root)
    conn = db.open_library(a)
    try:
        with conn:
            image_id = conn.execute("INSERT INTO image DEFAULT VALUES").lastrowid
            conn.execute(
                "INSERT INTO image_file (image_id, rel_path, sha256, orig_name) "
                "VALUES (?, ?, ?, ?)",
                (image_id, "images/_inbox/a.png", "a" * 64, "a.png"),
            )
    finally:
        conn.close()
    # 交错请求，不能因为后创建了 b，就把 a 的处理器也接到 b 上。
    ca, cb = TestClient(create_app(a)), TestClient(create_app(b))
    assert ca.get("/api/inbox").json()["total"] == 1
    assert cb.get("/api/inbox").json()["total"] == 0
    assert ca.get("/api/inbox").json()["total"] == 1


def test_request_connection_closes_after_exception(tmp_path: Path) -> None:
    db.init_library(tmp_path)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(library_root=tmp_path)))
    with pytest.raises(RuntimeError, match="handler failed"), connection(request) as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
        raise RuntimeError("handler failed")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")


def test_request_connection_does_not_repeat_startup_migrations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db.init_library(tmp_path)
    client = TestClient(create_app(tmp_path))
    migrate = Mock(side_effect=AssertionError("请求不应执行迁移"))
    monkeypatch.setattr(db, "open_library", migrate)
    assert client.get("/api/inbox").status_code == 200
    assert client.get("/api/navigation").status_code == 200
    migrate.assert_not_called()
