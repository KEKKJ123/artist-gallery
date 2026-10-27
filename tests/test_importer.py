import pytest
from PIL import Image

from artist_gallery.cli import main
from artist_gallery.core import db
from artist_gallery.core.importer import Action, _safe_stem, delete_sources, import_files


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
    assert by_name["作品_123456789.mp4"].rel_path == "images/_inbox/作品_123456789.mp4"
    mk = by_name["EO2cBcJWoAAJJWf.jpeg"]
    assert mk.action is Action.HINT and mk.rel_path.startswith("images/_inbox/")
    conn = db.connect(lib)
    hint = conn.execute(
        "SELECT platform, post_id, page FROM source_evidence WHERE platform='x'"
    ).fetchone()
    assert tuple(hint) == ("x", None, None)
    conn.close()


def test_hidden_folders_skipped(lib, tmp_path):
    make_image(tmp_path / "s" / ".thumbnails" / "a.jpg", (1, 1, 1))
    make_image(tmp_path / "s" / "b.jpg", (2, 2, 2))
    report = import_files(lib, [tmp_path / "s"])
    assert [i.src.name for i in report.items] == ["b.jpg"]


def test_import_copies_and_classifies(lib, src):
    report = import_files(lib, [src])
    by_name = {i.src.name: i for i in report.items}
    assert len(report.items) == 5  # txt 被忽略

    assert by_name["123456789_p0.png"].rel_path == "images/_inbox/123456789_p0.png"
    assert by_name["123456789_p1.png"].rel_path == "images/_inbox/123456789_p1.png"
    assert (
        by_name["1849000000000000000_1.jpg"].rel_path == "images/_inbox/1849000000000000000_1.jpg"
    )
    assert by_name["GxAbC12xyzQ.jpg"].action is Action.INBOX
    assert by_name["GxAbC12xyzQ.jpg"].rel_path == "images/_inbox/GxAbC12xyzQ.jpg"
    assert by_name["红豆 12345678.png"].action is Action.HINT

    # 导入只复制：源文件全部还在，图库里也有
    for it in report.items:
        assert it.src.exists()
        assert (lib / it.rel_path).is_file()

    conn = db.connect(lib)
    assert conn.execute("SELECT COUNT(*) FROM image WHERE state='inbox'").fetchone()[0] == 5
    assert (
        conn.execute("SELECT COUNT(*) FROM image_source WHERE status='confirmed'").fetchone()[0]
        == 0
    )
    assert conn.execute("SELECT COUNT(*) FROM post").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM image_source").fetchone()[0] == 4
    for (path,) in conn.execute("SELECT rel_path FROM image_file"):
        assert "\\" not in path and ":" not in path
    assert conn.execute("SELECT COUNT(*) FROM op_log WHERE kind='import'").fetchone()[0] == 5
    conn.close()


def test_delete_sources_after_confirm(lib, src):
    report = import_files(lib, [src])
    results = delete_sources(report)
    assert len(results) == 5 and all(r.deleted for r in results)
    for it in report.items:
        assert not it.src.exists()
        assert (lib / it.rel_path).is_file()
    conn = db.connect(lib)
    n = conn.execute("SELECT COUNT(*) FROM op_log WHERE kind = 'delete_source'").fetchone()[0]
    assert n == 5
    conn.close()


def test_delete_sources_skips_unsafe_cases(lib, tmp_path):
    a = make_image(tmp_path / "s" / "a.png", (1, 9, 9))  # 导入后被修改
    b = make_image(tmp_path / "s" / "b.png", (2, 9, 9))  # 图库副本被弄坏
    c = make_image(tmp_path / "s" / "c.png", (3, 9, 9))  # 正常
    report = import_files(lib, [tmp_path / "s"])
    rel = {i.src.name: i.rel_path for i in report.items}
    make_image(a, (99, 99, 99))
    (lib / rel["b.png"]).write_bytes(b"corrupted")
    results = {r.item.src.name: r for r in delete_sources(report)}
    assert not results["a.png"].deleted and a.exists()
    assert not results["b.png"].deleted and b.exists()
    assert results["c.png"].deleted and not c.exists()


def test_dry_run_and_duplicates_are_never_deletable(lib, src, tmp_path):
    assert import_files(lib, [src], dry_run=True).deletable() == []
    import_files(lib, [src])
    again = import_files(lib, [src])  # 全是重复
    assert again.deletable() == []
    assert delete_sources(again) == []
    assert (src / "123456789_p0.png").exists()


@pytest.mark.parametrize(("flag", "deleted"), [("yes", True), ("no", False), ("ask", False)])
def test_cli_delete_source_flag(lib, src, flag, deleted, monkeypatch):
    # ask 在测试里是非交互环境 → 视为不删
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert main(["import", str(lib), str(src), "--delete-source", flag]) == 0
    assert (src / "123456789_p0.png").exists() is (not deleted)


def test_cli_interactive_confirm(lib, src, monkeypatch):
    import artist_gallery.cli as cli_mod

    monkeypatch.setattr(cli_mod.sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    assert main(["import", str(lib), str(src)]) == 0
    assert not (src / "123456789_p0.png").exists()


def test_dry_run_changes_nothing(lib, src):
    report = import_files(lib, [src], dry_run=True)
    assert report.counts()[Action.HINT] == 4
    assert (src / "123456789_p0.png").exists()
    assert not (lib / "images" / "pixiv").exists()
    conn = db.connect(lib)
    assert conn.execute("SELECT COUNT(*) FROM image").fetchone()[0] == 0
    conn.close()


def test_duplicates_skipped_and_source_kept(lib, tmp_path):
    a = make_image(tmp_path / "a" / "123456789_p0.png", (9, 9, 9))
    import_files(lib, [a.parent])
    # 同内容、不同名字
    b = make_image(tmp_path / "b" / "whatever.png", (9, 9, 9))
    report = import_files(lib, [b.parent])
    assert report.items[0].action is Action.DUP
    delete_sources(report)
    assert b.exists()  # 重复的源文件即使确认删除也不删（库里那份不是它的副本）


def test_failed_copy_does_not_mark_duplicate(lib, tmp_path, monkeypatch):
    """同批次两份相同内容：第一份复制失败时，第二份应该照常导入，而不是被当成重复跳过。"""
    import artist_gallery.core.importer as imp_mod

    a = make_image(tmp_path / "s" / "a.png", (5, 5, 5))
    b = make_image(tmp_path / "s" / "b.png", (5, 5, 5))
    real_copy = imp_mod.copy_verified

    def flaky_copy(src, dst, sha):
        if src.name == "a.png":
            raise OSError("模拟磁盘错误")
        real_copy(src, dst, sha)

    monkeypatch.setattr(imp_mod, "copy_verified", flaky_copy)
    report = import_files(lib, [tmp_path / "s"])
    actions = {i.src.name: i.action for i in report.items}
    assert actions == {"a.png": Action.ERROR, "b.png": Action.INBOX}
    assert [i.src for i in report.deletable()] == [b]  # 失败的那份不会被列为可删
    assert a.exists()


def test_cli_newer_db_version_is_clean_error(lib, capsys):
    conn = db.connect(lib)
    conn.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()
    assert main(["status", str(lib)]) == 1
    assert "请先升级程序" in capsys.readouterr().err


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


def test_safe_stem_truncates_by_bytes():
    # 纯函数测试，任何平台都能跑：120 个汉字 = 360 字节
    s = _safe_stem("長" * 120)
    assert len(s.encode("utf-8")) <= 250
    assert s == "長" * 83  # 按完整字符截断，不会切出半个 UTF-8 字符


def test_long_inbox_name_is_truncated(lib, tmp_path):
    # 端到端：需要一个能存下 >255 字节文件名的文件系统（如 Windows NTFS）。
    # Android 的 ext4/F2FS 本身就建不出这种文件——那里也不可能遇到它，跳过即可。
    long_name = "長" * 90 + ".png"  # 274 字节
    try:
        make_image(tmp_path / "s" / long_name, (8, 1, 1))
    except OSError as e:
        pytest.skip(f"当前文件系统不支持超长文件名：{e}")
    report = import_files(lib, [tmp_path / "s"])
    name = report.items[0].rel_path.rsplit("/", 1)[1]
    assert len(name.encode("utf-8")) <= 255
    assert (lib / report.items[0].rel_path).is_file()


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("CON", "_CON"),
        (
            "CON.data",
            "_CON.data",
        ),  # Windows 保留名（这种文件在 Windows 上建不出来，但可能从手机拷来）
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
    import_files(root, [tmp_path / "x.png"])
    # 从图库的上级目录导入：图库里已有的文件不能被再次扫进来
    report = import_files(root, [tmp_path])
    assert all(not str(i.src).startswith(str(root)) for i in report.items)


def test_preserves_legal_name_and_extension_case(lib, tmp_path):
    src = make_image(tmp_path / "s" / "原来的中文标题.PNG", (8, 9, 1))
    report = import_files(lib, [src])
    assert report.items[0].rel_path == "images/_inbox/原来的中文标题.PNG"


def test_existing_untracked_collision_is_not_overwritten(lib, tmp_path):
    target = lib / "images" / "_inbox" / "SAME.png"
    target.write_bytes(b"untracked")
    src = make_image(tmp_path / "s" / "same.png", (8, 9, 1))
    report = import_files(lib, [src])
    assert report.items[0].rel_path == "images/_inbox/same_2.png"
    assert target.read_bytes() == b"untracked"


def test_db_write_failure_cleans_only_new_copy(lib, tmp_path, monkeypatch):
    import artist_gallery.core.importer as mod

    src = make_image(tmp_path / "s" / "a.png")

    def fail(*args):
        raise RuntimeError("failed to record evidence")

    monkeypatch.setattr(mod, "record_filename", fail)
    result = import_files(lib, [src])
    assert result.items[0].action is Action.ERROR
    assert src.exists()
    assert not list((lib / "images" / "_inbox").iterdir())
    conn = db.connect(lib)
    assert conn.execute("SELECT COUNT(*) FROM image").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM image_file").fetchone()[0] == 0
    conn.close()
