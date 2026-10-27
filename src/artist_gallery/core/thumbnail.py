"""缩略图生成与缓存。

路径：.cache/thumbs/{sha256[:2]}/{sha256}.webp（内容寻址，可随时重建）。
视频和 GIF 返回 None，静态图懒生成后缓存。
.cache/ 已在 .gitignore 中排除，不进仓库。
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from PIL import Image, ImageOps

THUMB_SIZE = 400  # 最长边上限（像素）
THUMB_QUALITY = 80

# 会生成缩略图的格式；其余（GIF、视频等）不生成
THUMB_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})


def thumb_path(root: Path, sha256: str) -> Path:
    """缩略图的完整路径（不管文件是否已存在）。"""
    return root / ".cache" / "thumbs" / sha256[:2] / f"{sha256}.webp"


def get_or_create(root: Path, sha256: str, src: Path) -> Path | None:
    """返回缩略图路径，必要时生成。视频 / GIF / 无法解析的文件返回 None。

    src 是原图的完整路径。生成过程先写临时文件再改名：进程中途被杀，
    不会留下半截的 .webp 被当成有效缓存。
    """
    if src.suffix.lower() not in THUMB_EXTS:
        return None

    dest = thumb_path(root, sha256)
    if dest.is_file():
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)  # 手机拍的图按 EXIF 方向摆正
            im.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA" if "transparency" in im.info or "A" in im.mode else "RGB")
            im.save(tmp, "WEBP", quality=THUMB_QUALITY)
        os.replace(tmp, dest)
    except Exception:  # noqa: BLE001 —— 损坏、超大像素等一律视为"无缩略图"
        tmp.unlink(missing_ok=True)
        return None
    return dest
