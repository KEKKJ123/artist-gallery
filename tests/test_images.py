"""图片投影、URL 与平台资料。"""

from pathlib import Path

import pytest

from artist_gallery.core import db
from artist_gallery.core.images import (
    IMAGE_COLUMNS,
    IMAGE_FROM,
    image_to_dict,
    normalize_pagination,
)
from artist_gallery.core.platforms import list_platforms


@pytest.mark.parametrize(
    ("offset", "limit", "expected"),
    [(-3, 0, (0, 1)), (4, 900, (4, 500)), (3, 25, (3, 25))],
)
def test_pagination_bounds(offset, limit, expected):
    assert normalize_pagination(offset, limit) == expected


@pytest.mark.parametrize(("ext", "has_thumb"), [(".PNG", True), (".gif", False), (".mp4", False)])
def test_projection_and_url_encoding(tmp_path: Path, ext, has_thumb):
    db.init_library(tmp_path)
    conn = db.open_library(tmp_path)
    try:
        i = conn.execute("INSERT INTO image DEFAULT VALUES").lastrowid
        conn.execute(
            "INSERT INTO image_file (image_id,rel_path,sha256,orig_name,missing) "
            "VALUES (?,?,?,?,1)",
            (i, f"images/中文 空格/a%#{ext}", "a" * 64, "original" + ext),
        )
        row = conn.execute(f"SELECT {IMAGE_COLUMNS} FROM {IMAGE_FROM}").fetchone()
        item = image_to_dict(row)
        assert item["missing"] is True
        assert item["file_url"] == f"/images/%E4%B8%AD%E6%96%87%20%E7%A9%BA%E6%A0%BC/a%25%23{ext}"
        assert bool(item["thumb_url"]) is has_thumb
    finally:
        conn.close()


def test_platform_list_preserves_custom_fields_and_builtin_order(tmp_path):
    db.init_library(tmp_path)
    conn = db.open_library(tmp_path)
    try:
        conn.execute(
            "INSERT INTO platform (id,name,user_url) VALUES (?,?,?)",
            ("aaa", "自定义", "https://example.org/{uid}"),
        )
        platforms = list_platforms(conn)
        assert [p["id"] for p in platforms] == ["pixiv", "x", "zerochan", "aaa"]
        assert all(p["builtin"] is True for p in platforms[:-1])
        assert platforms[-1]["builtin"] is False
        assert platforms[-1]["user_url"] == "https://example.org/{uid}"
    finally:
        conn.close()
