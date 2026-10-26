"""缩略图生成测试。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from artist_gallery.core.thumbnail import THUMB_EXTS, get_or_create, thumb_path


def _make_image(path: Path, size: tuple[int, int] = (200, 150), mode: str = "RGB") -> Path:
    img = Image.new(mode, size, color=(100, 150, 200))
    img.save(path)
    return path


FAKE_SHA = "a" * 64


class TestThumbPath:
    def test_structure(self, tmp_path: Path) -> None:
        p = thumb_path(tmp_path, "abcdef" + "0" * 58)
        assert p.parent.name == "ab"
        assert p.name == "abcdef" + "0" * 58 + ".webp"

    def test_under_cache(self, tmp_path: Path) -> None:
        p = thumb_path(tmp_path, FAKE_SHA)
        assert p.is_relative_to(tmp_path / ".cache" / "thumbs")


class TestGetOrCreate:
    def test_generates_webp(self, tmp_path: Path) -> None:
        src = _make_image(tmp_path / "img.png", size=(400, 300))
        result = get_or_create(tmp_path, FAKE_SHA, src)
        assert result is not None
        assert result.exists()
        assert result.suffix == ".webp"
        # 校验是合法的 WebP
        with Image.open(result) as im:
            assert im.format == "WEBP"

    def test_thumbnail_size_bounded(self, tmp_path: Path) -> None:
        """超过 THUMB_SIZE 的图应被缩小。"""
        from artist_gallery.core.thumbnail import THUMB_SIZE

        src = _make_image(tmp_path / "big.png", size=(1200, 800))
        result = get_or_create(tmp_path, FAKE_SHA, src)
        assert result is not None
        with Image.open(result) as im:
            assert max(im.size) <= THUMB_SIZE

    def test_small_image_not_upscaled(self, tmp_path: Path) -> None:
        """小图不应被放大。"""
        src = _make_image(tmp_path / "small.png", size=(50, 50))
        result = get_or_create(tmp_path, FAKE_SHA, src)
        assert result is not None
        with Image.open(result) as im:
            assert im.size == (50, 50)

    def test_cached_on_second_call(self, tmp_path: Path) -> None:
        src = _make_image(tmp_path / "img.png")
        r1 = get_or_create(tmp_path, FAKE_SHA, src)
        mtime = r1.stat().st_mtime  # type: ignore[union-attr]
        r2 = get_or_create(tmp_path, FAKE_SHA, src)
        assert r1 == r2
        assert r2.stat().st_mtime == mtime  # 没有重新生成

    def test_skips_gif(self, tmp_path: Path) -> None:
        src = tmp_path / "anim.gif"
        src.write_bytes(b"GIF89a fake")
        assert get_or_create(tmp_path, FAKE_SHA, src) is None

    def test_skips_video(self, tmp_path: Path) -> None:
        for ext in (".mp4", ".webm", ".mov", ".mkv"):
            src = tmp_path / f"v{ext}"
            src.write_bytes(b"fake video")
            assert get_or_create(tmp_path, FAKE_SHA, src) is None

    def test_skips_unknown_ext(self, tmp_path: Path) -> None:
        src = tmp_path / "file.xyz"
        src.write_bytes(b"data")
        assert get_or_create(tmp_path, FAKE_SHA, src) is None

    def test_broken_image_returns_none(self, tmp_path: Path) -> None:
        src = tmp_path / "broken.jpg"
        src.write_bytes(b"not an image at all")
        result = get_or_create(tmp_path, FAKE_SHA, src)
        assert result is None
        # 不应留下临时文件
        assert not any(tmp_path.rglob("*.tmp"))

    def test_missing_source_returns_none(self, tmp_path: Path) -> None:
        src = tmp_path / "nonexistent.png"
        assert get_or_create(tmp_path, FAKE_SHA, src) is None

    def test_rgba_image(self, tmp_path: Path) -> None:
        src = _make_image(tmp_path / "rgba.png", mode="RGBA")
        result = get_or_create(tmp_path, FAKE_SHA, src)
        assert result is not None
        assert result.exists()

    def test_thumb_exts_coverage(self) -> None:
        """确保常见格式在 THUMB_EXTS 里。"""
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            assert ext in THUMB_EXTS
