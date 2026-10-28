import re
import sqlite3

import pytest

from artist_gallery.core import db
from artist_gallery.core.platforms import BUILTIN_BY_ID
from artist_gallery.core.recognize import load_rules, recognize


def test_init_creates_layout(tmp_path):
    db.init_library(tmp_path)
    for sub in ("library.db", "images/_inbox", "images/archived", ".cache/thumbs"):
        assert (tmp_path / sub).exists()
    conn = db.open_library(tmp_path)
    assert conn.execute("PRAGMA application_id").fetchone()[0] == db.APPLICATION_ID
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"image", "image_file", "image_tag", "source_evidence"} <= names
    assert not {"work", "work_tag", "group_member"} & names
    conn.close()


@pytest.mark.parametrize("occupied", ["library.db", "photo.png", "images/kept.txt"])
def test_init_refuses_nonempty_without_touching(tmp_path, occupied):
    path = tmp_path / occupied
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        db.init_library(tmp_path)
    assert path.read_bytes() == b"keep"


def test_open_non_library_does_not_create(tmp_path):
    for opener in (db.connect, db.open_library):
        with pytest.raises(db.NotALibraryError):
            opener(tmp_path)
    assert not (tmp_path / db.DB_NAME).exists()


@pytest.mark.parametrize("kind", ["unknown", "newer", "incomplete", "broken"])
def test_other_formats_fail_without_write(tmp_path, kind):
    path = tmp_path / db.DB_NAME
    if kind == "broken":
        path.write_bytes(b"broken")
    elif kind == "newer":
        db.init_library(tmp_path)
        conn = db.connect(tmp_path)
        conn.execute(f"PRAGMA user_version={db.SCHEMA_VERSION + 1}")
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(path)
        if kind == "incomplete":
            conn.execute(f"PRAGMA application_id={db.APPLICATION_ID}")
            conn.execute("PRAGMA user_version=5")
        conn.commit()
        conn.close()
    before = path.read_bytes()
    with pytest.raises((db.LibraryFormatError, sqlite3.DatabaseError)):
        db.open_library(tmp_path)
    assert path.read_bytes() == before


def _init_baseline(tmp_path):
    """真实当前格式 v5 基线（不是改路线前旧库），供后续升级机制测试。"""
    from importlib import resources

    tmp_path.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(tmp_path / db.DB_NAME)
    schema = resources.files("artist_gallery.core").joinpath("schema.sql").read_text("utf-8")
    conn.executescript(schema)
    conn.execute(f"PRAGMA application_id={db.APPLICATION_ID}")
    conn.execute("PRAGMA user_version=5")
    conn.commit()
    conn.close()


def test_failed_new_format_migration_rolls_back(tmp_path, monkeypatch):
    _init_baseline(tmp_path)
    monkeypatch.setattr(
        db, "MIGRATIONS", ["ALTER TABLE image ADD COLUMN zzz TEXT; SELECT * FROM no_such;"]
    )
    monkeypatch.setattr(db, "SCHEMA_VERSION", 6)
    monkeypatch.setattr(db, "REQUIRED_SCHEMAS", {**db.REQUIRED_SCHEMAS, 6: db.REQUIRED_SCHEMAS[5]})
    conn = db.connect(tmp_path)
    with pytest.raises(sqlite3.OperationalError):
        db.migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
    assert "zzz" not in {r[1] for r in conn.execute("PRAGMA table_info(image)")}
    conn.close()


def test_successful_new_format_upgrade(tmp_path, monkeypatch):
    _init_baseline(tmp_path)
    monkeypatch.setattr(db, "MIGRATIONS", ["ALTER TABLE image ADD COLUMN note TEXT;"])
    monkeypatch.setattr(db, "SCHEMA_VERSION", 6)
    monkeypatch.setattr(db, "REQUIRED_SCHEMAS", {**db.REQUIRED_SCHEMAS, 6: db.REQUIRED_SCHEMAS[5]})
    conn = db.open_library(tmp_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
    assert "note" in {r[1] for r in conn.execute("PRAGMA table_info(image)")}
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
    r = recognize("lofter_1a2b3c4d", load_rules(conn))
    assert (r.platform, r.post_id, r.page) == ("lofter", "1a2b3c4d", None)
    assert {r["id"] for r in conn.execute("SELECT * FROM platform")} >= {"pixiv", "x", "zerochan"}
    conn.close()


@pytest.mark.parametrize(
    ("platform", "text", "post_id"),
    [
        ("pixiv", "https://www.pixiv.net/artworks/123456789", "123456789"),
        ("pixiv", "https://www.pixiv.net/en/artworks/123456789", "123456789"),
        ("x", "https://x.com/someone/status/1849000000000000000", "1849000000000000000"),
        ("zerochan", "https://www.zerochan.net/3017022", "3017022"),
    ],
)
def test_builtin_url_regex(platform, text, post_id):
    m = re.search(BUILTIN_BY_ID[platform].url_regex, text)
    assert m and m["post_id"] == post_id


def test_incomplete_current_schema_is_rejected_before_sync(tmp_path, monkeypatch):
    db.init_library(tmp_path)
    conn = db.connect(tmp_path)
    conn.execute("ALTER TABLE image_file DROP COLUMN width")
    conn.commit()
    conn.close()
    before = (tmp_path / db.DB_NAME).read_bytes()
    monkeypatch.setattr(db, "sync_builtin_platforms", lambda _: pytest.fail("不完整库不准同步"))
    with pytest.raises(db.LibraryFormatError, match="结构不完整"):
        db.open_library(tmp_path)
    assert (tmp_path / db.DB_NAME).read_bytes() == before


def test_readonly_does_not_sync_or_allow_write(tmp_path, monkeypatch):
    db.init_library(tmp_path)
    before = (tmp_path / db.DB_NAME).read_bytes()
    monkeypatch.setattr(db, "sync_builtin_platforms", lambda _: pytest.fail("只读不准同步"))
    conn = db.open_library(tmp_path, readonly=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO image DEFAULT VALUES")
    conn.close()
    assert (tmp_path / db.DB_NAME).read_bytes() == before


def test_new_required_field_does_not_block_its_migration(tmp_path, monkeypatch):
    _init_baseline(tmp_path)
    required6 = {**db.REQUIRED_SCHEMAS[5], "image": db.REQUIRED_SCHEMAS[5]["image"] | {"note"}}
    monkeypatch.setattr(db, "MIGRATIONS", ["ALTER TABLE image ADD COLUMN note TEXT;"])
    monkeypatch.setattr(db, "SCHEMA_VERSION", 6)
    monkeypatch.setattr(db, "REQUIRED_SCHEMAS", {**db.REQUIRED_SCHEMAS, 6: required6})
    conn = db.open_library(tmp_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
    assert "note" in {r[1] for r in conn.execute("PRAGMA table_info(image)")}
    conn.close()


def test_target_schema_failure_rolls_back_entire_step(tmp_path, monkeypatch):
    _init_baseline(tmp_path)
    required6 = {**db.REQUIRED_SCHEMAS[5], "image": db.REQUIRED_SCHEMAS[5]["image"] | {"note"}}
    monkeypatch.setattr(db, "MIGRATIONS", ["ALTER TABLE image ADD COLUMN wrong_field TEXT;"])
    monkeypatch.setattr(db, "SCHEMA_VERSION", 6)
    monkeypatch.setattr(db, "REQUIRED_SCHEMAS", {**db.REQUIRED_SCHEMAS, 6: required6})
    with pytest.raises(db.LibraryFormatError, match="结构不完整"):
        db.open_library(tmp_path)
    conn = db.connect(tmp_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
    assert "wrong_field" not in {r[1] for r in conn.execute("PRAGMA table_info(image)")}
    conn.close()


def test_all_intermediate_versions_checked_and_repeat_open_is_idempotent(tmp_path, monkeypatch):
    _init_baseline(tmp_path)
    required6 = {**db.REQUIRED_SCHEMAS[5], "image": db.REQUIRED_SCHEMAS[5]["image"] | {"note"}}
    required7 = {**required6, "image": required6["image"] | {"extra_note"}}
    monkeypatch.setattr(
        db,
        "MIGRATIONS",
        [
            "ALTER TABLE image ADD COLUMN note TEXT;",
            "ALTER TABLE image ADD COLUMN extra_note TEXT;",
        ],
    )
    monkeypatch.setattr(db, "SCHEMA_VERSION", 7)
    monkeypatch.setattr(db, "REQUIRED_SCHEMAS", {**db.REQUIRED_SCHEMAS, 6: required6, 7: required7})
    for _ in range(2):
        conn = db.open_library(tmp_path)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
        conn.close()


def test_missing_upgrade_validation_refuses_before_any_write(tmp_path, monkeypatch):
    _init_baseline(tmp_path)
    before = (tmp_path / db.DB_NAME).read_bytes()
    monkeypatch.setattr(db, "MIGRATIONS", ["ALTER TABLE image ADD COLUMN note TEXT;"])
    monkeypatch.setattr(db, "SCHEMA_VERSION", 6)
    monkeypatch.setattr(db, "REQUIRED_SCHEMAS", {5: db.REQUIRED_SCHEMAS[5]})
    with pytest.raises(db.LibraryFormatError, match="缺少图库版本 6"):
        db.open_library(tmp_path)
    assert (tmp_path / db.DB_NAME).read_bytes() == before


def test_readonly_outdated_supported_format_does_not_upgrade(tmp_path, monkeypatch):
    _init_baseline(tmp_path)
    before = (tmp_path / db.DB_NAME).read_bytes()
    monkeypatch.setattr(db, "MIGRATIONS", ["ALTER TABLE image ADD COLUMN note TEXT;"])
    monkeypatch.setattr(db, "SCHEMA_VERSION", 6)
    monkeypatch.setattr(db, "REQUIRED_SCHEMAS", {**db.REQUIRED_SCHEMAS, 6: db.REQUIRED_SCHEMAS[5]})
    with pytest.raises(db.LibraryFormatError, match="需要升级"):
        db.open_library(tmp_path, readonly=True)
    assert (tmp_path / db.DB_NAME).read_bytes() == before
