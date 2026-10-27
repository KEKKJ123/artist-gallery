"""收件箱与平台列表的查询（只读）。

收件箱 = image.work_id 为 NULL 的图片。写操作（归档、合并作品）在 M1c 加入。
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

from artist_gallery.core.thumbnail import THUMB_EXTS

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_LIMIT = 500

# 列表接口统一查这些列，配合 image_to_dict 使用（收件箱和文件夹视图共用）
IMAGE_COLUMNS = "id, rel_path, sha256, orig_name, source_hint, width, height, added_at, missing"


def _file_url(rel_path: str) -> str:
    """原图的 URL。rel_path 形如 images/pixiv/xxx.png，去掉 images/ 前缀并转义中文和空格。"""
    return "/images/" + quote(rel_path.removeprefix("images/"), safe="/")


def image_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """把按 IMAGE_COLUMNS 查出的一行转成给前端的字典。"""
    ext = PurePosixPath(row["rel_path"]).suffix.lower()
    hint = json.loads(row["source_hint"]) if row["source_hint"] else None
    return {
        "id": row["id"],
        "rel_path": row["rel_path"],
        "orig_name": row["orig_name"],
        "source_hint": hint,
        "width": row["width"],
        "height": row["height"],
        "added_at": row["added_at"],
        "missing": bool(row["missing"]),
        # 只有静态图有缩略图；视频 / GIF 为 None，前端显示占位图标
        "thumb_url": f"/thumbs/{row['sha256']}" if ext in THUMB_EXTS else None,
        "file_url": _file_url(row["rel_path"]),
        "ext": ext,
    }


def list_inbox(conn: sqlite3.Connection, *, offset: int = 0, limit: int = 100) -> dict[str, Any]:
    """收件箱列表，按入库顺序（added_at, id）。返回 {total, offset, limit, items}。"""
    offset = max(0, offset)
    limit = min(max(1, limit), MAX_LIMIT)
    total = conn.execute("SELECT COUNT(*) FROM image WHERE work_id IS NULL").fetchone()[0]
    rows = conn.execute(
        f"SELECT {IMAGE_COLUMNS} FROM image WHERE work_id IS NULL"
        " ORDER BY added_at, id LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [image_to_dict(r) for r in rows],
    }


def find_image_by_sha(conn: sqlite3.Connection, sha256: str) -> str | None:
    """按 sha256 查图库内相对路径；格式不对或不存在返回 None。"""
    if not SHA256_RE.match(sha256):
        return None
    row = conn.execute("SELECT rel_path FROM image WHERE sha256 = ?", (sha256,)).fetchone()
    return row[0] if row else None


def list_platforms(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """平台列表。url_regex 给前端在浏览器里直接解析粘贴的链接用。"""
    rows = conn.execute(
        "SELECT id, name, post_url, user_url, url_regex, builtin"
        " FROM platform ORDER BY builtin DESC, id"
    ).fetchall()
    return [{**dict(r), "builtin": bool(r["builtin"])} for r in rows]
