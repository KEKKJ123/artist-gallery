"""按逻辑图片分页；版本、来源、角色 tag 不增加重复卡片。"""

from __future__ import annotations

import re
import sqlite3
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

from artist_gallery.core.media import THUMB_EXTS

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_LIMIT = 500
# 展示版本缺失时仍保留逻辑图片，不让列表条目数与总数悄悄分叉。
IMAGE_FROM = "image i LEFT JOIN image_file f ON f.image_id=i.id AND f.is_display=1"
IMAGE_COLUMNS = (
    "i.id, i.state, i.artist_id, i.added_at, f.id AS file_id, f.rel_path, f.sha256,"
    " f.orig_name, f.width, f.height, f.missing"
)
HAS_HINT = """EXISTS (
    SELECT 1 FROM source_evidence e LEFT JOIN image_source s ON s.id=e.source_id
    WHERE e.image_id=i.id AND e.dismissed=0 AND (s.id IS NULL OR s.status='pending')
)"""


def image_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """基础投影，批量附加关系见 images_to_list。"""
    has_display = row["file_id"] is not None
    ext = PurePosixPath(row["rel_path"]).suffix.lower() if has_display else ""
    display_status = "unassigned" if not has_display else ("missing" if row["missing"] else "ok")
    return {
        **{
            k: row[k]
            for k in (
                "id",
                "state",
                "file_id",
                "orig_name",
                "rel_path",
                "width",
                "height",
                "added_at",
            )
        },
        "missing": bool(row["missing"]),
        "display_status": display_status,
        "display_message": "展示文件待设置" if not has_display else None,
        "thumb_url": f"/thumbs/{row['sha256']}" if ext in THUMB_EXTS else None,
        "file_url": (
            "/images/" + quote(row["rel_path"].removeprefix("images/"), safe="/")
            if has_display
            else None
        ),
        "ext": ext,
    }


def images_to_list(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """关系批量查询，不做每张图的 N+1 查询，建议保留全部并按有效内容去重。"""
    if not rows:
        return []
    result = {
        r["id"]: {**image_to_dict(r), "source_hints": [], "sources": [], "tags": [], "artist": None}
        for r in rows
    }
    q = ",".join("?" for _ in result)
    ids = list(result)
    seen: dict[int, set[tuple]] = {i: set() for i in ids}
    for r in conn.execute(
        f"SELECT e.* FROM source_evidence e LEFT JOIN image_source s ON s.id=e.source_id "
        f"WHERE e.image_id IN ({q}) AND e.dismissed=0 "
        "AND (s.id IS NULL OR s.status='pending') ORDER BY e.id",
        ids,
    ):
        key = (r["platform"], r["post_id"], r["page"])
        if key not in seen[r["image_id"]]:
            result[r["image_id"]]["source_hints"].append(
                {k: r[k] for k in ("platform", "post_id", "page", "confidence")}
            )
            seen[r["image_id"]].add(key)
    for r in conn.execute(
        "SELECT s.image_id, s.page, s.status, p.platform, p.post_id, p.posted_at "
        "FROM image_source s "
        f"JOIN post p ON p.id=s.post_id WHERE s.image_id IN ({q}) ORDER BY s.id",
        ids,
    ):
        result[r["image_id"]]["sources"].append(
            {k: r[k] for k in ("platform", "post_id", "page", "status", "posted_at")}
        )
    for r in conn.execute(
        f"SELECT it.image_id, t.ns, t.name FROM image_tag it JOIN tag t ON t.id=it.tag_id "
        f"WHERE it.image_id IN ({q}) ORDER BY t.ns,t.name",
        ids,
    ):
        result[r["image_id"]]["tags"].append({"ns": r["ns"], "name": r["name"]})
    for r in conn.execute(
        "SELECT i.id AS image_id,a.id,a.name FROM image i JOIN artist a ON a.id=i.artist_id "
        f"WHERE i.id IN ({q})",
        ids,
    ):
        result[r["image_id"]]["artist"] = {"id": r["id"], "name": r["name"]}
    return list(result.values())


def normalize_pagination(offset: int, limit: int) -> tuple[int, int]:
    return max(0, offset), min(max(1, limit), MAX_LIMIT)


def list_images(
    conn: sqlite3.Connection, state: str, *, offset: int = 0, limit: int = 100, extra: str = ""
) -> dict[str, Any]:
    offset, limit = normalize_pagination(offset, limit)
    where = "i.state=?" + extra  # extra 只允许调用方固定 SQL，不接收用户原文
    total = conn.execute(f"SELECT COUNT(*) FROM image i WHERE {where}", (state,)).fetchone()[0]
    rows = conn.execute(
        f"SELECT {IMAGE_COLUMNS} FROM {IMAGE_FROM} WHERE {where} "
        "ORDER BY i.added_at,i.id LIMIT ? OFFSET ?",
        (state, limit, offset),
    ).fetchall()
    return {"total": total, "offset": offset, "limit": limit, "items": images_to_list(conn, rows)}


def find_image_by_sha(conn: sqlite3.Connection, sha256: str) -> str | None:
    if not SHA256_RE.fullmatch(sha256):
        return None
    row = conn.execute("SELECT rel_path FROM image_file WHERE sha256=?", (sha256,)).fetchone()
    return row[0] if row else None
