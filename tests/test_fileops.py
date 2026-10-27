"""独占落位与失败清理；只使用生成的临时字节。"""

import pytest

from artist_gallery.core import fileops


def test_existing_target_and_part_are_untouched(tmp_path):
    src, dst = tmp_path / "source", tmp_path / "dest"
    src.write_bytes(b"new")
    dst.write_bytes(b"old")
    part = dst.with_name(dst.name + ".part")
    part.write_bytes(b"other process")
    with pytest.raises(FileExistsError):
        fileops.copy_verified(src, dst, fileops.sha256_file(src))
    assert dst.read_bytes() == b"old"
    assert part.read_bytes() == b"other process"
    assert not list(tmp_path.glob(".import-*"))


def test_bad_hash_removes_only_own_temp(tmp_path):
    src, dst = tmp_path / "source", tmp_path / "dest"
    src.write_bytes(b"new")
    with pytest.raises(OSError, match="校验失败"):
        fileops.copy_verified(src, dst, "0" * 64)
    assert src.read_bytes() == b"new"
    assert not dst.exists()
    assert not list(tmp_path.glob(".import-*"))


def test_competing_target_created_after_copy_is_not_overwritten(tmp_path, monkeypatch):
    src, dst = tmp_path / "source", tmp_path / "dest"
    src.write_bytes(b"ours")
    sha = fileops.sha256_file(src)
    real = fileops.sha256_file

    def competing(path):
        result = real(path)
        if path.name.startswith(".import-"):
            dst.write_bytes(b"competitor")
        return result

    monkeypatch.setattr(fileops, "sha256_file", competing)
    with pytest.raises(FileExistsError):
        fileops.copy_verified(src, dst, sha)
    assert dst.read_bytes() == b"competitor"
    assert not list(tmp_path.glob(".import-*"))


def test_final_write_interrupted_keeps_source_and_cleans_ours(tmp_path, monkeypatch):
    src, dst = tmp_path / "source", tmp_path / "dest"
    src.write_bytes(b"ours")
    real = fileops.shutil.copyfileobj
    calls = 0

    def interrupt(source, target, length):
        nonlocal calls
        calls += 1
        if calls == 2:
            target.write(b"partial")
            raise KeyboardInterrupt
        real(source, target, length)

    monkeypatch.setattr(fileops.shutil, "copyfileobj", interrupt)
    with pytest.raises(KeyboardInterrupt):
        fileops.copy_verified(src, dst, fileops.sha256_file(src))
    assert src.read_bytes() == b"ours"
    assert not dst.exists() and not list(tmp_path.glob(".import-*"))
