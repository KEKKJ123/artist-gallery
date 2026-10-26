import pytest
from PIL import Image

from artist_gallery.cli import main
from artist_gallery.core import db
from artist_gallery.core.importer import Action, import_files


def make_image(path, color=(255, 0, 0), size=(8, 8)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


@pytest.fixture
def lib(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    return root


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "src"
    make_image(d / "123456789_p0.png", (1, 0, 0))
    make_image(d / "123456789_p1.png", (2, 0, 0))
    make_image(d / "GxAbC12xyzQ.jpg", (3, 0, 0))
    make_image(d / "红豆 12345678.png", (4, 0, 0))
    make_image(d / "sub" / "1849000000000000000_1.jpg", (5, 0, 0))
    (d / "notes.txt").write_text("not an image")
    return d


def test_import_moves_and_classifies(lib, src):
    report = import_files(lib, [src])
    by_name = {i.src.name: i for i in report.items}
    assert len(report.items) == 5  # txt 被忽略

    assert by_name["123456789_p0.png"].rel_path == "images/pixiv/pixiv_123456789_p0.png"
    assert by_name["123456789_p1.png"].rel_path == "images/pixiv/pixiv_123456789_p1.png"
    assert by_name["1849000000000000000_1.jpg"].rel_path == "images/x/x_1849000000000000000_p0.jpg"
    assert by_name["GxAbC12xyzQ.jpg"].action is Action.INBOX
    assert by_name["GxAbC12xyzQ.jpg"].rel_path == "images/_inbox/GxAbC12xyzQ.jpg"
    assert by_name["红豆 12345678.png"].action is Action.HINT

    # 文件已移动：源不在了，目标在
    for it in report.items:
        assert not it.src.exists()
        assert (lib / it.rel_path).is_file()

    conn = db.connect(lib)
    # 同一 Pixiv 作品的两页归到同一个 work
    works = conn.execute(
        "SELECT COUNT(DISTINCT work_id) FROM image WHERE rel_path LIKE 'images/pixiv/%'"
    ).fetchone()[0]
    assert works == 1
    assert conn.execute("SELECT COUNT(*) FROM work").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM image WHERE work_id IS NULL").fetchone()[0] == 2
    hint = conn.execute(
        "SELECT source_hint, orig_name FROM image WHERE source_hint IS NOT NULL"
    ).fetchone()
    assert '"post_id": "12345678"' in hint[0] and hint[1] == "红豆 12345678.png"
    # 路径全部是相对路径、正斜杠
    for (p,) in conn.execute("SELECT rel_path FROM image"):
        assert "\\" not in p and ":" not in p
    assert conn.execute("SELECT COUNT(*) FROM op_log WHERE kind = 'import'").fetchone()[0] == 5
    conn.close()


def test_copy_mode_keeps_source(lib, src):
    import_files(lib, [src], move=False)
    assert (src / "123456789_p0.png").exists()


def test_dry_run_changes_nothing(lib, src):
    report = import_files(lib, [src], dry_run=True)
    assert report.counts()[Action.AUTO] == 3
    assert (src / "123456789_p0.png").exists()
    assert not (lib / "images" / "pixiv").exists()
    conn = db.connect(lib)
    assert conn.execute("SELECT COUNT(*) FROM image").fetchone()[0] == 0
    conn.close()


def test_duplicates_skipped_and_source_kept(lib, tmp_path):
    a = make_image(tmp_path / "a" / "123456789_p0.png", (9, 9, 9))
    import_files(lib, [a.parent], move=False)
    # 同内容、不同名字
    b = make_image(tmp_path / "b" / "whatever.png", (9, 9, 9))
    report = import_files(lib, [b.parent])
    assert report.items[0].action is Action.DUP
    assert b.exists()  # 重复的源文件不删


def test_duplicate_within_same_batch(lib, tmp_path):
    make_image(tmp_path / "s" / "one.png", (7, 7, 7))
    make_image(tmp_path / "s" / "two.png", (7, 7, 7))
    report = import_files(lib, [tmp_path / "s"])
    assert sorted(i.action for i in report.items) == [Action.DUP, Action.INBOX]


def test_name_collision_gets_suffix(lib, tmp_path):
    make_image(tmp_path / "a" / "same.png", (1, 2, 3))
    make_image(tmp_path / "b" / "same.png", (3, 2, 1))
    report = import_files(lib, [tmp_path / "a", tmp_path / "b"])
    paths = sorted(i.rel_path for i in report.items)
    assert paths == ["images/_inbox/same.png", "images/_inbox/same_2.png"]


def test_corrupt_file_is_error_and_kept(lib, tmp_path):
    bad = tmp_path / "s" / "broken.jpg"
    bad.parent.mkdir()
    bad.write_bytes(b"not really a jpeg")
    report = import_files(lib, [bad.parent])
    assert report.items[0].action is Action.ERROR
    assert bad.exists()


def test_refuse_import_from_inside_library(lib):
    with pytest.raises(ValueError):
        import_files(lib, [lib / "images"])


def test_refuse_non_library(tmp_path):
    with pytest.raises(FileNotFoundError):
        import_files(tmp_path, [tmp_path])


def test_cli_import_and_status(lib, src, capsys):
    assert main(["import", str(lib), str(src), "--dry-run"]) == 0
    assert "预演" in capsys.readouterr().out
    assert main(["import", str(lib), str(src)]) == 0
    assert main(["status", str(lib)]) == 0
    out = capsys.readouterr().out
    assert "收件箱" in out and "pixiv" in out


def test_migration_from_v1(tmp_path):
    """模拟一个 v1 图库（没有 orig_name 列），打开时应自动升级。"""
    root = tmp_path / "old"
    db.init_library(root)
    conn = db.connect(root)
    conn.executescript(
        "ALTER TABLE image DROP COLUMN orig_name; ALTER TABLE image DROP COLUMN source_hint;"
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    assert db.migrate(conn) == db.SCHEMA_VERSION
    cols = {r[1] for r in conn.execute("PRAGMA table_info(image)")}
    assert {"orig_name", "source_hint"} <= cols
    conn.close()
