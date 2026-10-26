import re

import pytest

from artist_gallery.core import db


def test_init_creates_layout(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    assert (root / "library.db").exists()
    assert (root / "images" / "_inbox").is_dir()
    assert (root / ".cache" / "thumbs").is_dir()


def test_init_refuses_existing(tmp_path):
    db.init_library(tmp_path)
    with pytest.raises(FileExistsError):
        db.init_library(tmp_path)


def test_schema_version_and_seed(tmp_path):
    db.init_library(tmp_path)
    conn = db.connect(tmp_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    ids = {r["id"] for r in conn.execute("SELECT id FROM platform")}
    assert {"pixiv", "x"} <= ids
    conn.close()


@pytest.mark.parametrize(
    ("platform", "text", "post_id"),
    [
        ("pixiv", "https://www.pixiv.net/artworks/123456789", "123456789"),
        ("pixiv", "https://www.pixiv.net/en/artworks/123456789", "123456789"),
        ("x", "https://x.com/someone/status/1849000000000000000", "1849000000000000000"),
        ("x", "https://twitter.com/someone/status/1849000000000000000?s=20", "1849000000000000000"),
    ],
)
def test_seed_url_regex(tmp_path, platform, text, post_id):
    db.init_library(tmp_path)
    conn = db.connect(tmp_path)
    pattern = conn.execute("SELECT url_regex FROM platform WHERE id = ?", (platform,)).fetchone()[0]
    conn.close()
    m = re.search(pattern, text)
    assert m and m["post_id"] == post_id


def test_pixiv_file_regex(tmp_path):
    db.init_library(tmp_path)
    conn = db.connect(tmp_path)
    pattern = conn.execute("SELECT file_regex FROM platform WHERE id = 'pixiv'").fetchone()[0]
    conn.close()
    m = re.search(pattern, "某作品标题_123456789_p2.png")
    assert m and (m["post_id"], m["page"]) == ("123456789", "2")
