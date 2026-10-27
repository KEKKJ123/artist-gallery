"""按文件夹浏览：文件夹树、区间查询的边界、收件箱隔离、路径校验。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from artist_gallery.core import browse, db
from artist_gallery.core.browse import BadFolderPath, normalize_folder


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    root = tmp_path / "lib"
    db.init_library(root)
    c = db.open_library(root)
    yield c
    c.close()


_n = 0


def add(c: sqlite3.Connection, rel: str, *, inbox: bool = False) -> None:
    """直接往库里塞一行，不碰磁盘（浏览只读数据库）。"""
    global _n
    _n += 1
    work_id = None
    if not inbox:
        work_id = c.execute("INSERT INTO work DEFAULT VALUES").lastrowid
    c.execute(
        "INSERT INTO image (work_id, rel_path, sha256) VALUES (?, ?, ?)",
        (work_id, rel, f"{_n:064x}"),
    )
    c.commit()


def paths(result: dict) -> list[str]:
    return [i["rel_path"] for i in result["items"]]


class TestNormalize:
    def test_strips_slashes_and_accepts_unicode(self) -> None:
        assert normalize_folder("/pixiv/") == "pixiv"
        assert normalize_folder("精选/红豆") == "精选/红豆"
        assert normalize_folder("") == ""
        assert normalize_folder("/") == ""

    @pytest.mark.parametrize(
        "bad", ["..", "a/../b", "./a", "a/./b", "a//b", "a\\b", "a/b\\c", "a\x00b", "../etc"]
    )
    def test_rejects_traversal_and_oddities(self, bad: str) -> None:
        with pytest.raises(BadFolderPath):
            normalize_folder(bad)


class TestFolderTree:
    def test_counts_include_subfolders_and_inbox_is_separate(
        self, conn: sqlite3.Connection
    ) -> None:
        add(conn, "images/pixiv/a.png")
        add(conn, "images/pixiv/b.png")
        add(conn, "images/x/c.png")
        add(conn, "images/精选/红豆/d.png")
        add(conn, "images/精选/e.png")
        add(conn, "images/_inbox/f.png", inbox=True)
        add(conn, "images/_inbox/g.png", inbox=True)

        t = browse.list_folders(conn)
        assert t["inbox"] == 2
        assert t["archived"] == 5  # 收件箱的不算
        by = {f["path"]: f for f in t["folders"]}
        assert by["pixiv"]["count"] == 2
        assert by["x"]["count"] == 1
        assert by["精选"]["count"] == 2  # 含子文件夹里的 1 张
        assert by["精选/红豆"]["count"] == 1
        assert "_inbox" not in by

    def test_structure_fields(self, conn: sqlite3.Connection) -> None:
        add(conn, "images/精选/红豆/a.png")
        by = {f["path"]: f for f in browse.list_folders(conn)["folders"]}
        assert by["精选"] == {
            "path": "精选",
            "name": "精选",
            "depth": 0,
            "count": 1,
            "has_children": True,
        }
        assert by["精选/红豆"]["depth"] == 1
        assert by["精选/红豆"]["name"] == "红豆"
        assert by["精选/红豆"]["has_children"] is False

    def test_parent_always_listed_before_children_and_siblings_sorted(
        self, conn: sqlite3.Connection
    ) -> None:
        for rel in ("images/b/z/1.png", "images/b/a/2.png", "images/a/3.png", "images/B2/4.png"):
            add(conn, rel)
        order = [f["path"] for f in browse.list_folders(conn)["folders"]]
        assert order.index("b") < order.index("b/a") < order.index("b/z")
        # 不区分大小写排序：a, b, b/a, b/z, B2
        assert order == ["a", "b", "b/a", "b/z", "B2"]

    def test_files_directly_under_images_belong_to_no_folder_but_count_as_archived(
        self, conn: sqlite3.Connection
    ) -> None:
        add(conn, "images/loose.png")
        t = browse.list_folders(conn)
        assert t["folders"] == [] and t["archived"] == 1

    def test_empty_library(self, conn: sqlite3.Connection) -> None:
        assert browse.list_folders(conn) == {"inbox": 0, "archived": 0, "folders": []}

    def test_folder_named_like_inbox_but_nested_is_not_hidden(
        self, conn: sqlite3.Connection
    ) -> None:
        # 只有 images/_inbox/ 这一个顶层目录是收件箱；别处叫 _inbox 的普通子文件夹照常显示
        add(conn, "images/pixiv/_inbox/a.png")
        assert "pixiv/_inbox" in {f["path"] for f in browse.list_folders(conn)["folders"]}


class TestFolderImages:
    def test_includes_subfolders(self, conn: sqlite3.Connection) -> None:
        add(conn, "images/精选/a.png")
        add(conn, "images/精选/红豆/b.png")
        add(conn, "images/x/c.png")
        assert paths(browse.list_folder_images(conn, "精选")) == [
            "images/精选/a.png",
            "images/精选/红豆/b.png",
        ]
        assert paths(browse.list_folder_images(conn, "精选/红豆")) == ["images/精选/红豆/b.png"]

    def test_sibling_with_same_prefix_is_not_included(self, conn: sqlite3.Connection) -> None:
        """'pixiv' 不能把 'pixiv2'、'pixiv-old'、'pixiv.png' 带进来——区间边界的核心。"""
        add(conn, "images/pixiv/a.png")
        add(conn, "images/pixiv2/b.png")
        add(conn, "images/pixiv-old/c.png")
        add(conn, "images/pixiv.png")
        add(conn, "images/pixiv_x/d.png")
        add(conn, "images/pixiv0/e.png")  # '0' 恰好是 '/' 的下一个字符，最容易踩的边界
        r = browse.list_folder_images(conn, "pixiv")
        assert paths(r) == ["images/pixiv/a.png"]
        assert r["total"] == 1

    @pytest.mark.parametrize("name", ["100%", "a_b", "a%b", "50%_off", "[x]"])
    def test_wildcard_characters_in_folder_names_are_literal(
        self, conn: sqlite3.Connection, name: str
    ) -> None:
        add(conn, f"images/{name}/a.png")
        add(conn, "images/other/b.png")
        add(conn, "images/aXb/c.png")  # 若误当成 LIKE 通配符，'a_b' 或 'a%b' 会匹配到它
        assert paths(browse.list_folder_images(conn, name)) == [f"images/{name}/a.png"]

    def test_root_means_all_archived_without_inbox(self, conn: sqlite3.Connection) -> None:
        add(conn, "images/pixiv/a.png")
        add(conn, "images/loose.png")
        add(conn, "images/_inbox/z.png", inbox=True)
        r = browse.list_folder_images(conn, "")
        assert paths(r) == ["images/loose.png", "images/pixiv/a.png"]
        assert r["total"] == 2

    def test_inbox_folder_itself_is_still_listable_by_path(self, conn: sqlite3.Connection) -> None:
        # 前端不会链到它（有专门的收件箱视图），但直接请求这个路径不应报错或泄露别处的图
        add(conn, "images/_inbox/z.png", inbox=True)
        add(conn, "images/pixiv/a.png")
        assert paths(browse.list_folder_images(conn, "_inbox")) == ["images/_inbox/z.png"]

    def test_unknown_folder_is_empty_not_an_error(self, conn: sqlite3.Connection) -> None:
        add(conn, "images/pixiv/a.png")
        r = browse.list_folder_images(conn, "不存在")
        assert r["total"] == 0 and r["items"] == []

    def test_ordered_by_path_so_pages_of_one_work_stay_together(
        self, conn: sqlite3.Connection
    ) -> None:
        for p in (2, 0, 1):
            add(conn, f"images/pixiv/pixiv_123_p{p}.png")
        add(conn, "images/pixiv/pixiv_100_p0.png")
        assert paths(browse.list_folder_images(conn, "pixiv")) == [
            "images/pixiv/pixiv_100_p0.png",
            "images/pixiv/pixiv_123_p0.png",
            "images/pixiv/pixiv_123_p1.png",
            "images/pixiv/pixiv_123_p2.png",
        ]

    def test_pagination_covers_everything_exactly_once(self, conn: sqlite3.Connection) -> None:
        for i in range(25):
            add(conn, f"images/pixiv/{i:03d}.png")
        seen: list[str] = []
        for off in range(0, 30, 10):
            r = browse.list_folder_images(conn, "pixiv", offset=off, limit=10)
            assert r["total"] == 25
            seen += paths(r)
        assert len(seen) == 25 and len(set(seen)) == 25 and seen == sorted(seen)

    def test_limit_is_clamped_and_negative_offset_ignored(self, conn: sqlite3.Connection) -> None:
        add(conn, "images/pixiv/a.png")
        assert browse.list_folder_images(conn, "pixiv", limit=10**9)["limit"] == 500
        assert browse.list_folder_images(conn, "pixiv", limit=0)["limit"] == 1
        assert browse.list_folder_images(conn, "pixiv", offset=-5)["offset"] == 0

    def test_item_shape_matches_inbox_items(self, conn: sqlite3.Connection) -> None:
        """文件夹视图和收件箱共用同一个前端网格，字段必须一致。"""
        from artist_gallery.core import inbox

        add(conn, "images/pixiv/a.png")
        add(conn, "images/_inbox/b.png", inbox=True)
        folder_item = browse.list_folder_images(conn, "pixiv")["items"][0]
        inbox_item = inbox.list_inbox(conn)["items"][0]
        assert set(folder_item) == set(inbox_item)
        assert folder_item["file_url"] == "/images/pixiv/a.png"
        assert folder_item["thumb_url"].startswith("/thumbs/")

    def test_chinese_and_space_in_path_roundtrip(self, conn: sqlite3.Connection) -> None:
        add(conn, "images/我的 收藏/红豆 1.png")
        r = browse.list_folder_images(conn, "我的 收藏")
        assert (
            r["items"][0]["file_url"]
            == "/images/%E6%88%91%E7%9A%84%20%E6%94%B6%E8%97%8F/%E7%BA%A2%E8%B1%86%201.png"
        )
