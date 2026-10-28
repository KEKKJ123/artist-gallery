"""未保存草稿独立存储，按图库与图片隔离；不改变来源、核查或归档。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from artist_gallery.core import operations as ops


def library_id(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT value FROM library_meta WHERE key='id'").fetchone()[0]


def load(conn: sqlite3.Connection, image_id: int) -> dict:
    if not conn.execute("SELECT 1 FROM image WHERE id=?", (image_id,)).fetchone():
        raise ops.OperationError("图片不存在")
    row = conn.execute("SELECT * FROM review_draft WHERE image_id=?", (image_id,)).fetchone()
    return {
        "library_id": library_id(conn),
        "image_id": image_id,
        "revision": row["revision"] if row else 0,
        "payload": json.loads(row["payload"]) if row else None,
    }


def save(conn: sqlite3.Connection, image_id: int, payload: Any, expected: int) -> dict:
    if payload is not None and (not isinstance(payload, dict) or len(ops.encode(payload)) > 128000):
        raise ops.OperationError("草稿格式不正确或超过长度限制")
    if type(expected) is not int or expected < 0:
        raise ops.OperationError("草稿版本无效")
    conn.execute("BEGIN IMMEDIATE")
    try:
        current = load(conn, image_id)
        if current["revision"] != expected:
            raise ops.ConflictError("草稿已在其他页面改变，未覆盖；请先重新读取草稿")
        # 清空也保留递增版本，防止旧请求在删除后以 0 版本重新创建过期草稿。
        conn.execute(
            "INSERT INTO review_draft(image_id,payload,revision) VALUES(?,?,?) "
            "ON CONFLICT(image_id) DO UPDATE SET payload=excluded.payload,"
            "revision=excluded.revision,updated_at=datetime('now')",
            (image_id, ops.encode(payload), expected + 1),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return load(conn, image_id)
