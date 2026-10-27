"""外部文件夹增量导入，旧分类稳定与线索不丢。"""

import shutil

import pytest
from PIL import Image

from artist_gallery.core import db, inbox
from artist_gallery.core.importer import Action, import_files


def picture(path, color=(10, 20, 30)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color).save(path)
    return path


def test_incremental_preserves_metadata_and_new_evidence(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    first = picture(tmp_path / "src" / "123456789_p2.png")
    report = import_files(root, [first.parent])
    conn = db.open_library(root)
    with conn:
        image = conn.execute("SELECT id FROM image").fetchone()[0]
        artist = conn.execute("INSERT INTO artist(name) VALUES ('author')").lastrowid
        conn.execute("UPDATE image SET state='archived',artist_id=? WHERE id=?", (artist, image))
        tag = conn.execute("INSERT INTO tag(ns,name) VALUES ('character','红豆')").lastrowid
        conn.execute("INSERT INTO image_tag VALUES (?,?)", (image, tag))
        conn.execute("UPDATE image_source SET status='confirmed',confirmed_at='now'")
    before = dict(conn.execute("SELECT * FROM image").fetchone())
    renamed = tmp_path / "src" / "1849000000000000000_1.png"
    first.rename(renamed)
    again = import_files(root, [renamed.parent])
    assert again.items[0].action is Action.DUP and again.items[0].evidence_added
    assert again.deletable() == []
    assert dict(conn.execute("SELECT * FROM image").fetchone()) == before
    assert conn.execute("SELECT COUNT(*) FROM image_tag").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM image_file").fetchone()[0] == 1
    assert conn.execute("SELECT orig_name FROM image_file").fetchone()[0] == first.name
    assert conn.execute("SELECT COUNT(*) FROM source_evidence").fetchone()[0] == 2
    assert conn.execute("SELECT page FROM image_source WHERE status='confirmed'").fetchone()[0] == 2
    assert not import_files(root, [renamed.parent]).items[0].evidence_added
    assert conn.execute("SELECT COUNT(*) FROM source_evidence").fetchone()[0] == 2
    renamed.unlink()  # 源目录减少不联动删除图库
    import_files(root, [renamed.parent])
    assert dict(conn.execute("SELECT * FROM image").fetchone()) == before
    assert (root / report.items[0].rel_path).exists()
    conn.close()


@pytest.mark.parametrize("broken", ["missing", "changed"])
def test_existing_copy_is_checked_not_overwritten(tmp_path, broken):
    root = tmp_path / "lib"
    db.init_library(root)
    src = picture(tmp_path / "src" / "a.png")
    one = import_files(root, [src]).items[0]
    target = root / one.rel_path
    if broken == "missing":
        target.unlink()
    else:
        target.write_bytes(b"changed")
    again = import_files(root, [src])
    assert again.items[0].action is Action.ERROR
    assert again.deletable() == []
    assert src.exists()
    if broken == "changed":
        assert target.read_bytes() == b"changed"


def test_same_name_changed_bytes_are_new_image(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    src = picture(tmp_path / "src" / "a.png")
    import_files(root, [src])
    picture(src, (90, 20, 30))
    report = import_files(root, [src])
    assert report.items[0].rel_path == "images/_inbox/a_2.png"
    conn = db.open_library(root)
    assert inbox.list_inbox(conn)["total"] == 2
    conn.close()


def test_same_batch_different_names_keep_both_sources(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    a = picture(tmp_path / "src" / "123456789_p0.png")
    shutil.copyfile(a, a.with_name("1849000000000000000_1.png"))
    import_files(root, [a.parent])
    conn = db.open_library(root)
    data = inbox.list_inbox(conn)
    assert data["total"] == 1
    assert len(data["items"][0]["source_hints"]) == 2
    assert conn.execute("SELECT COUNT(*) FROM import_record").fetchone()[0] == 2
    conn.close()


def test_dry_run_is_byte_identical(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    a = picture(tmp_path / "src" / "123456789_p0.png")
    before = (root / db.DB_NAME).read_bytes()
    report = import_files(root, [a], dry_run=True)
    assert report.items[0].action is Action.HINT
    assert before == (root / db.DB_NAME).read_bytes()
    assert not list((root / "images").rglob("*.png"))


def test_suggestions_filter_and_page_conflicts(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    a = picture(tmp_path / "src" / "123456789_p0.png")
    b = picture(tmp_path / "src" / "unknown.png", (50, 50, 50))
    import_files(root, [a, b])
    conn = db.open_library(root)
    assert inbox.list_inbox(conn, hint_filter="hint")["total"] == 1
    assert inbox.list_inbox(conn, hint_filter="nohint")["total"] == 1
    alias = a.with_name("123456789_p1.png")
    shutil.copyfile(a, alias)
    import_files(root, [alias])
    hints = inbox.list_inbox(conn, hint_filter="hint")["items"][0]["source_hints"]
    assert {x["page"] for x in hints} == {0, 1}
    assert conn.execute("SELECT page FROM image_source").fetchone()[0] == 0
    conn.close()


@pytest.mark.parametrize("status", ["confirmed", "rejected"])
def test_new_evidence_does_not_override_review_decision(tmp_path, status):
    root = tmp_path / "lib"
    db.init_library(root)
    src = picture(tmp_path / "s" / "123456789_p0.png")
    import_files(root, [src])
    conn = db.open_library(root)
    with conn:
        conn.execute(
            "UPDATE image_source SET status=?,confirmed_at=?",
            (status, "now" if status == "confirmed" else None),
        )
    before = dict(conn.execute("SELECT * FROM image_source").fetchone())
    alias = src.with_name("123456789_p1.png")
    shutil.copyfile(src, alias)
    import_files(root, [alias])
    assert dict(conn.execute("SELECT * FROM image_source").fetchone()) == before
    assert conn.execute("SELECT COUNT(*) FROM source_evidence").fetchone()[0] == 2
    assert inbox.list_inbox(conn, hint_filter="hint")["total"] == 0
    conn.close()
