"""无展示版本时保留一图一卡、分页与属性，只读且不自动选其他版本。"""

import pytest
from starlette.testclient import TestClient

from artist_gallery.core import browse, db, inbox
from artist_gallery.server.app import create_app


@pytest.mark.parametrize("state", ["inbox", "archived"])
@pytest.mark.parametrize("files", [0, 1, 2])
def test_unassigned_display_keeps_item_and_does_not_mutate(tmp_path, state, files):
    db.init_library(tmp_path)
    conn = db.open_library(tmp_path)
    with conn:
        image_id = conn.execute("INSERT INTO image(state) VALUES (?)", (state,)).lastrowid
        for n in range(files):
            conn.execute(
                "INSERT INTO image_file(image_id,rel_path,sha256,orig_name,is_display) "
                "VALUES (?,?,?,?,0)",
                (image_id, f"images/_inbox/{n}.png", f"{n:064x}", f"{n}.png"),
            )
        tag = conn.execute("INSERT INTO tag(ns,name) VALUES ('character','红豆')").lastrowid
        conn.execute("INSERT INTO image_tag VALUES (?,?)", (image_id, tag))
    before = [tuple(r) for r in conn.execute("SELECT * FROM image_file")]
    data = inbox.list_inbox(conn) if state == "inbox" else browse.list_archived(conn)
    assert data["total"] == len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == image_id and item["state"] == state
    assert item["display_status"] == "unassigned"
    assert item["display_message"] == "展示文件待设置"
    assert item["thumb_url"] is None and item["file_url"] is None
    assert item["file_id"] is None and item["rel_path"] is None
    assert item["tags"] == [{"ns": "character", "name": "红豆"}]
    assert [tuple(r) for r in conn.execute("SELECT * FROM image_file")] == before
    assert browse.navigation(conn)[state] == 1
    conn.close()


def test_normal_and_unassigned_items_have_consistent_pagination(tmp_path):
    db.init_library(tmp_path)
    conn = db.open_library(tmp_path)
    with conn:
        for n in range(8):
            image_id = conn.execute("INSERT INTO image DEFAULT VALUES").lastrowid
            if n % 2:
                conn.execute(
                    "INSERT INTO image_file(image_id,rel_path,sha256,orig_name) VALUES (?,?,?,?)",
                    (image_id, f"images/_inbox/{n}.png", f"{n:064x}", f"{n}.png"),
                )
    ids = []
    for offset in range(0, 8, 3):
        page = inbox.list_inbox(conn, offset=offset, limit=3)
        assert page["total"] == 8
        ids.extend(item["id"] for item in page["items"])
    assert ids == list(range(1, 9))
    conn.close()


def test_api_serializes_placeholder_without_fabricated_media_url(tmp_path):
    db.init_library(tmp_path)
    conn = db.open_library(tmp_path)
    with conn:
        conn.execute("INSERT INTO image DEFAULT VALUES")
    conn.close()
    client = TestClient(create_app(tmp_path))
    data = client.get("/api/inbox").json()
    assert data["total"] == len(data["items"]) == 1
    assert data["items"][0]["display_status"] == "unassigned"
    assert data["items"][0]["file_url"] is None
    assert client.get("/api/navigation").json()["inbox"] == 1
