import pytest
from PIL import Image

from artist_gallery.cli import main
from artist_gallery.core import db
from artist_gallery.core.importer import Action, _safe_stem, import_files


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


def test_video_classified_like_images(lib, tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "Video_24301078824427.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42 a")
    (d / "作品_123456789.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42 b")
    make_image(d / "EO2cBcJWoAAJJWf.jpeg", (6, 0, 0))
    report = import_files(lib, [d])
    by_name = {i.src.name: i for i in report.items}
    assert by_name["Video_24301078824427.mp4"].action is Action.INBOX
    assert by_name["作品_123456789.mp4"].rel_path == "images/pixiv/pixiv_123456789_p0.mp4"
    mk = by_name["EO2cBcJWoAAJJWf.jpeg"]
    assert mk.action is Action.HINT and mk.rel_path.startswith("images/_inbox/")
    conn = db.connect(lib)
    hint = conn.execute("SELECT source_hint FROM image WHERE source_hint IS NOT NULL").fetchone()
    assert hint[0] == '{"platform": "x", "post_id": null, "page": null}'
    conn.close()


def test_hidden_folders_skipped(lib, tmp_path):
    make_image(tmp_path / "s" / ".thumbnails" / "a.jpg", (1, 1, 1))
    make_image(tmp_path / "s" / "b.jpg", (2, 2, 2))
    report = import_files(lib, [tmp_path / "s"])
    assert [i.src.name for i in report.items] == ["b.jpg"]


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


def test_long_inbox_name_is_truncated(lib, tmp_path):
    long_name = "長" * 120 + ".png"  # 360 字节：NTFS 能存，但 Android 的 ext4/F2FS 上限是 255 字节
    make_image(tmp_path / "s" / long_name, (8, 1, 1))
    report = import_files(lib, [tmp_path / "s"])
    name = report.items[0].rel_path.rsplit("/", 1)[1]
    assert len(name.encode("utf-8")) <= 200
    assert (lib / report.items[0].rel_path).is_file()


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("CON", "_CON"),  # Windows 保留名（这种文件在 Windows 上建不出来，但可能从手机拷来）
        ("a:b?c", "a_b_c"),  # Linux/Android 允许、Windows 不允许的字符
        ("trailing. ", "trailing"),
        ("", "unnamed"),
    ],
)
def test_safe_stem(stem, expected):
    assert _safe_stem(stem) == expected


def test_case_insensitive_collision(lib, tmp_path):
    make_image(tmp_path / "a" / "Same.png", (9, 1, 1))
    make_image(tmp_path / "b" / "same.png", (9, 2, 2))
    report = import_files(lib, [tmp_path / "a", tmp_path / "b"])
    paths = sorted(i.rel_path.lower() for i in report.items)
    assert paths == ["images/_inbox/same.png", "images/_inbox/same_2.png"]


def test_library_inside_source_is_skipped(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    make_image(tmp_path / "x.png", (3, 3, 3))
    import_files(root, [tmp_path / "x.png"], move=False)
    # 从图库的上级目录导入：图库里已有的文件不能被再次扫进来
    report = import_files(root, [tmp_path], move=False)
    assert all(not str(i.src).startswith(str(root)) for i in report.items)
