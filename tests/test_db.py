import re
import sqlite3
from pathlib import Path

import pytest

from artist_gallery.core import db
from artist_gallery.core.platforms import BUILTIN_BY_ID
from artist_gallery.core.recognize import load_rules, recognize

FIXTURES = Path(__file__).parent / "fixtures"


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


def test_open_non_library(tmp_path):
    with pytest.raises(db.NotALibraryError):
        db.open_library(tmp_path)


def test_schema_version_and_builtins(tmp_path):
    db.init_library(tmp_path)
    conn = db.open_library(tmp_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    rows = {r["id"]: r["builtin"] for r in conn.execute("SELECT id, builtin FROM platform")}
    assert rows == {"pixiv": 1, "x": 1, "zerochan": 1}
    conn.close()


@pytest.mark.parametrize(
    ("platform", "text", "post_id"),
    [
        ("pixiv", "https://www.pixiv.net/artworks/123456789", "123456789"),
        ("pixiv", "https://www.pixiv.net/en/artworks/123456789", "123456789"),
        ("x", "https://x.com/someone/status/1849000000000000000", "1849000000000000000"),
        ("x", "https://twitter.com/someone/status/1849000000000000000?s=20", "1849000000000000000"),
        ("zerochan", "https://www.zerochan.net/3017022", "3017022"),
    ],
)
def test_builtin_url_regex(platform, text, post_id):
    m = re.search(BUILTIN_BY_ID[platform].url_regex, text)
    assert m and m["post_id"] == post_id


def _make_v1_library(root: Path) -> None:
    """用 v1 版 schema.sql 原样建一个真正的 v1 图库，并放一行数据。"""
    root.mkdir()
    conn = sqlite3.connect(root / db.DB_NAME)
    conn.executescript((FIXTURES / "schema_v1.sql").read_text("utf-8"))
    conn.execute("INSERT INTO work DEFAULT VALUES")
    conn.execute("INSERT INTO image (work_id, rel_path, sha256) VALUES (1, 'images/a.png', 'x')")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()


def test_migration_from_real_v1(tmp_path):
    root = tmp_path / "old"
    _make_v1_library(root)
    conn = db.open_library(root)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    cols = {r[1] for r in conn.execute("PRAGMA table_info(image)")}
    assert {"orig_name", "source_hint"} <= cols
    assert conn.execute("SELECT rel_path FROM image").fetchone()[0] == "images/a.png"  # 数据还在
    # 旧库里过时的内置正则被代码定义取代：单页 Pixiv、Zerochan 都能识别
    rules = load_rules(conn)
    assert recognize("红豆_80742555", rules).platform == "pixiv"
    assert recognize("Vigna.full.3017022", rules).platform == "zerochan"
    conn.close()


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    root = tmp_path / "old"
    _make_v1_library(root)
    bad = [*db.MIGRATIONS[:1], "ALTER TABLE image ADD COLUMN zzz TEXT; SELECT * FROM no_such;"]
    monkeypatch.setattr(db, "MIGRATIONS", bad)
    monkeypatch.setattr(db, "SCHEMA_VERSION", 1 + len(bad))
    conn = db.connect(root)
    with pytest.raises(sqlite3.OperationalError):
        db.migrate(conn)
    # 第一条成功提交（v2），第二条整体回滚：版本停在 2，zzz 列不存在
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert "zzz" not in {r[1] for r in conn.execute("PRAGMA table_info(image)")}
    conn.close()


def test_custom_platform_rule(tmp_path):
    db.init_library(tmp_path)
    conn = db.open_library(tmp_path)
    with conn:
        conn.execute(
            "INSERT INTO platform (id, name, file_regex) VALUES"
            " ('lofter', 'LOFTER', '^lofter_(?P<post_id>[0-9a-f]{8})$'),"
            " ('broken', 'Broken', '(?P<post_id>[')"
        )
    rules = load_rules(conn)  # 无效正则只记日志，不报错
    r = recognize("lofter_1a2b3c4d", rules)
    assert (r.platform, r.post_id) == ("lofter", "1a2b3c4d")
    conn.close()
