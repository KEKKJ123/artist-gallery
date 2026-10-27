"""两区按状态查询：与路径无关，多个版本／来源／标签不重复卡片。"""

import sqlite3

import pytest

from artist_gallery.core import browse, db, inbox
from artist_gallery.core.images import IMAGE_COLUMNS, IMAGE_FROM, images_to_list


@pytest.fixture
def conn(tmp_path):
    db.init_library(tmp_path)
    c = db.open_library(tmp_path)
    yield c
    c.close()


def add(c, name, state="inbox"):
    i = c.execute("INSERT INTO image (state) VALUES (?)", (state,)).lastrowid
    c.execute(
        "INSERT INTO image_file (image_id, rel_path, sha256, orig_name) VALUES (?, ?, ?, ?)",
        (i, f"images/_inbox/{name}.png", f"{i:064x}", f"{name}.png"),
    )
    return i


def test_state_not_path_controls_browse(conn):
    add(conn, "one", "archived")
    add(conn, "two")
    assert browse.navigation(conn) == {"inbox": 1, "inbox_hinted": 0, "archived": 1}
    archived = browse.list_archived(conn)
    assert archived["total"] == 1
    assert archived["items"][0]["rel_path"].startswith("images/_inbox/")
    assert inbox.list_inbox(conn)["items"][0]["orig_name"] == "two.png"


def test_multiple_relations_do_not_duplicate_cards(conn):
    i = add(conn, "one")
    conn.execute(
        "INSERT INTO image_file (image_id,rel_path,sha256,orig_name,is_display) VALUES (?,?,?,?,0)",
        (i, "images/_inbox/version.png", "f" * 64, "version.png"),
    )
    for n, platform in enumerate(("pixiv", "x")):
        p = conn.execute(
            "INSERT INTO post (platform,post_id) VALUES (?,?)", (platform, "123")
        ).lastrowid
        conn.execute(
            "INSERT INTO image_source (image_id,post_id,page,status,confirmed_at) "
            "VALUES (?,?,?,'confirmed','2026-10-28')",
            (i, p, n),
        )
    for name in ("红豆", "另一个角色"):
        t = conn.execute("INSERT INTO tag (ns,name) VALUES ('character',?)", (name,)).lastrowid
        conn.execute("INSERT INTO image_tag VALUES (?,?)", (i, t))
    a = conn.execute("INSERT INTO artist (name) VALUES ('某画师')").lastrowid
    conn.execute("UPDATE image SET artist_id=? WHERE id=?", (a, i))
    data = inbox.list_inbox(conn)
    assert data["total"] == len(data["items"]) == 1
    item = data["items"][0]
    assert len(item["sources"]) == 2 and len(item["tags"]) == 2
    assert item["artist"] == {"id": a, "name": "某画师"}
    assert item["source_hints"] == []
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_pagination_and_empty_projection(conn):
    for n in range(8):
        add(conn, str(n), "archived")
    data = browse.list_archived(conn, offset=2, limit=3)
    assert data["total"] == 8
    assert [i["orig_name"] for i in data["items"]] == ["2.png", "3.png", "4.png"]
    assert browse.list_archived(conn, offset=99)["items"] == []
    assert images_to_list(conn, []) == []


@pytest.mark.parametrize("bad", ["oops", "HINT", "no-hint"])
def test_filter_validation(conn, bad):
    with pytest.raises(inbox.BadFilter):
        inbox.list_inbox(conn, hint_filter=bad)


def test_display_constraint_and_direct_tags(conn):
    i, other = add(conn, "a"), add(conn, "b")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO image_file (image_id,rel_path,sha256,orig_name) VALUES (?,?,?,?)",
            (i, "images/b.png", "e" * 64, "b.png"),
        )
    t = conn.execute("INSERT INTO tag (ns,name) VALUES ('character','红豆')").lastrowid
    conn.execute("INSERT INTO image_tag VALUES (?,?)", (i, t))
    items = images_to_list(
        conn, conn.execute(f"SELECT {IMAGE_COLUMNS} FROM {IMAGE_FROM}").fetchall()
    )
    by_id = {x["id"]: x for x in items}
    assert by_id[i]["tags"] == [{"ns": "character", "name": "红豆"}]
    assert by_id[other]["tags"] == []


def test_confirmed_source_can_have_unknown_page(conn):
    i = add(conn, "unknown-page")
    post = conn.execute("INSERT INTO post(platform,post_id) VALUES ('pixiv','123456789')").lastrowid
    conn.execute(
        "INSERT INTO image_source(image_id,post_id,status,confirmed_at) "
        "VALUES (?,?,'confirmed','now')",
        (i, post),
    )
    item = inbox.list_inbox(conn)["items"][0]
    assert item["sources"][0]["page"] is None
    assert item["sources"][0]["status"] == "confirmed"
    assert item["state"] == "inbox"  # 确认也不隐式归档
