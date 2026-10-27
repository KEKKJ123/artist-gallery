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
        assert browse.list_folders(conn) == {
            "inbox": 0,
            "inbox_hinted": 0,
            "archived": 0,
            "folders": [],
        }

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


class TestInboxHintFilter:
    """收件箱"只看有来源建议的图"。筛选必须在服务端做：收件箱是分页的，前端只过滤已加载的页会漏图、总数也不对。"""

    HINT = '{"platform": "pixiv", "post_id": "12345678", "page": 0}'
    WEAK = '{"platform": "x", "post_id": null, "page": null}'

    def _add_inbox(self, c: sqlite3.Connection, name: str, hint: str | None) -> None:
        global _n
        _n += 1
        c.execute(
            "INSERT INTO image (work_id, rel_path, sha256, source_hint) VALUES (NULL, ?, ?, ?)",
            (f"images/_inbox/{name}", f"{_n:064x}", hint),
        )
        c.commit()

    @pytest.fixture
    def mixed(self, conn: sqlite3.Connection) -> sqlite3.Connection:
        self._add_inbox(conn, "a.png", self.HINT)
        self._add_inbox(conn, "b.png", None)
        self._add_inbox(conn, "c.png", self.WEAK)  # 只知道平台（X 的 media key）也算有建议
        self._add_inbox(conn, "d.png", "")  # 空串当作没有
        self._add_inbox(conn, "e.png", self.HINT)
        add(conn, "images/pixiv/z.png")  # 已归档的不属于收件箱，任何筛选都不应出现
        return conn

    @staticmethod
    def _names(r: dict) -> list[str]:
        return [i["rel_path"].rsplit("/", 1)[1] for i in r["items"]]

    def test_all_is_default(self, mixed: sqlite3.Connection) -> None:
        from artist_gallery.core import inbox

        r = inbox.list_inbox(mixed)
        assert r["filter"] == "all" and r["total"] == 5

    def test_hint_only(self, mixed: sqlite3.Connection) -> None:
        from artist_gallery.core import inbox

        r = inbox.list_inbox(mixed, hint_filter="hint")
        assert self._names(r) == ["a.png", "c.png", "e.png"]
        assert r["total"] == 3 and r["filter"] == "hint"

    def test_nohint_is_exact_complement_including_empty_string(
        self, mixed: sqlite3.Connection
    ) -> None:
        from artist_gallery.core import inbox

        r = inbox.list_inbox(mixed, hint_filter="nohint")
        assert self._names(r) == ["b.png", "d.png"]  # NULL 和 '' 都算"没有"
        hint = inbox.list_inbox(mixed, hint_filter="hint")["total"]
        assert (
            hint + r["total"] == inbox.list_inbox(mixed)["total"]
        )  # 两类加起来恰好是全部，不重不漏

    def test_archived_images_never_appear(self, mixed: sqlite3.Connection) -> None:
        from artist_gallery.core import inbox

        for f in ("all", "hint", "nohint"):
            assert "z.png" not in self._names(inbox.list_inbox(mixed, hint_filter=f))

    def test_total_and_paging_follow_the_filter_not_the_whole_inbox(
        self, conn: sqlite3.Connection
    ) -> None:
        """核心：第 1 页全是没建议的，有建议的都在后面——前端只滤已加载页就会一张都看不到。"""
        from artist_gallery.core import inbox

        for i in range(30):
            self._add_inbox(conn, f"n{i:02d}.png", None)
        for i in range(5):
            self._add_inbox(conn, f"h{i}.png", self.HINT)
        first = inbox.list_inbox(conn, limit=10, hint_filter="hint")
        assert first["total"] == 5 and len(first["items"]) == 5  # 一页就取全，没被前 30 张挤掉
        assert inbox.list_inbox(conn, limit=10)["total"] == 35
        seen: list[str] = []
        for off in range(0, 35, 10):
            seen += self._names(inbox.list_inbox(conn, offset=off, limit=10, hint_filter="nohint"))
        assert len(seen) == 30 and len(set(seen)) == 30

    def test_unknown_filter_is_rejected_not_silently_all(self, conn: sqlite3.Connection) -> None:
        from artist_gallery.core import inbox

        with pytest.raises(inbox.BadFilter):
            inbox.list_inbox(conn, hint_filter="hints")
        assert inbox.normalize_hint_filter(None) == "all"
        assert inbox.normalize_hint_filter("") == "all"

    def test_count_hinted_and_nav_payload(self, mixed: sqlite3.Connection) -> None:
        from artist_gallery.core import inbox

        assert inbox.count_inbox_hinted(mixed) == 3
        nav = browse.list_folders(mixed)
        assert nav["inbox"] == 5 and nav["inbox_hinted"] == 3
        assert browse.list_folders(mixed)["archived"] == 1  # 已归档计数不受影响

    def test_empty_inbox(self, conn: sqlite3.Connection) -> None:
        from artist_gallery.core import inbox

        for f in ("all", "hint", "nohint"):
            r = inbox.list_inbox(conn, hint_filter=f)
            assert r["total"] == 0 and r["items"] == []
        assert browse.list_folders(conn)["inbox_hinted"] == 0
