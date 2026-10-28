"""操作日志、来源快照与倒序撤销；文件操作的恢复由 archiving 负责。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from typing import Any

REVERSIBLE = frozenset({"review", "archive"})
BARRIERS = frozenset({"import", "delete_source"})


class OperationError(ValueError):
    """无法安全执行，调用方应显示原因而不是自动缩小范围。"""


class ConflictError(OperationError):
    """数据已改变或有未完成操作，必须重新读取后再决定。"""


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def image_ids(values: Any) -> list[int]:
    if not isinstance(values, list) or not values or len(values) > 10000:
        raise OperationError("请选择 1～10000 张图片")
    if any(type(v) is not int or v <= 0 for v in values) or len(set(values)) != len(values):
        raise OperationError("图片编号必须是互不重复的正整数")
    return values


def pending(conn: sqlite3.Connection) -> list[dict]:
    return [
        {"id": r["id"], "kind": r["kind"], **json.loads(r["payload"])}
        for r in conn.execute("SELECT * FROM op_log WHERE kind IN ('archive','undo_archive')")
        if json.loads(r["payload"]).get("status") == "pending"
    ]


def require_idle(conn: sqlite3.Connection) -> None:
    if pending(conn):
        raise ConflictError("有未完成的文件操作，请先检查恢复；不会自动重试或继续写入")


def source_snapshot(conn: sqlite3.Connection, ids: list[int]) -> dict:
    q = ",".join("?" for _ in ids)
    images = [
        dict(r)
        for r in conn.execute(f"SELECT id,state FROM image WHERE id IN ({q}) ORDER BY id", ids)
    ]
    if len(images) != len(ids):
        raise ConflictError("部分图片已不存在，未执行任何修改")
    return {
        "images": images,
        "sources": [
            dict(r)
            for r in conn.execute(
                f"SELECT * FROM image_source WHERE image_id IN ({q}) ORDER BY id", ids
            )
        ],
        "evidence": [
            dict(r)
            for r in conn.execute(
                f"SELECT * FROM source_evidence WHERE image_id IN ({q}) ORDER BY id", ids
            )
        ],
    }


def revision(conn: sqlite3.Connection, image_id: int) -> str:
    snapshot = source_snapshot(conn, [image_id])
    snapshot["times"] = [
        list(r)
        for r in conn.execute(
            "SELECT p.id,p.posted_at FROM post p JOIN image_source s ON s.post_id=p.id "
            "WHERE s.image_id=? ORDER BY p.id",
            (image_id,),
        )
    ]
    return hashlib.sha256(encode(snapshot).encode()).hexdigest()


def check_revisions(conn: sqlite3.Connection, ids: list[int], expected: dict) -> None:
    if not isinstance(expected, dict):
        raise OperationError("缺少图片版本，请重新加载")
    for i in ids:
        if expected.get(str(i)) != revision(conn, i):
            raise ConflictError(f"图片 {i} 的资料已改变，请重新加载；草稿不会自动覆盖新资料")


def log_operation(conn: sqlite3.Connection, kind: str, payload: dict) -> int:
    return conn.execute(
        "INSERT INTO op_log(batch_id,kind,payload) VALUES(?,?,?)",
        (uuid.uuid4().hex, kind, encode(payload)),
    ).lastrowid


def update_log(conn: sqlite3.Connection, log_id: int, payload: dict) -> None:
    conn.execute("UPDATE op_log SET payload=? WHERE id=?", (encode(payload), log_id))


def latest(conn: sqlite3.Connection) -> dict:
    waiting = pending(conn)
    if waiting:
        return {"can_undo": False, "pending": waiting, "message": "请先检查未完成的文件操作"}
    for row in conn.execute("SELECT * FROM op_log ORDER BY id DESC"):
        if row["kind"] in BARRIERS:
            return {
                "can_undo": False,
                "pending": [],
                "message": "更早的操作已越过导入／删源边界，无法撤销",
            }
        if row["kind"] not in REVERSIBLE:
            continue
        data = json.loads(row["payload"])
        if data.get("status") == "done" and not data.get("undone"):
            return {
                "can_undo": True,
                "id": row["id"],
                "kind": row["kind"],
                "pending": [],
                "message": data.get("undo_error", ""),
            }
    return {"can_undo": False, "pending": [], "message": "没有可撤销的操作"}


def undo_review(conn: sqlite3.Connection, log_id: int) -> None:
    """整批预检再恢复；任何冲突都不改来源、不跨过当前记录。"""
    conn.execute("BEGIN IMMEDIATE")
    try:
        require_idle(conn)
        top = latest(conn)
        if not top.get("can_undo") or top.get("id") != log_id or top.get("kind") != "review":
            raise ConflictError("撤销顺序已改变，请刷新操作记录")
        data = json.loads(
            conn.execute("SELECT payload FROM op_log WHERE id=?", (log_id,)).fetchone()[0]
        )
        ids = [r["id"] for r in data["after"]["images"]]
        if source_snapshot(conn, ids) != data["after"]:
            raise ConflictError("当前来源资料与记录不符，未撤销，也不会覆盖后续整理")
        for post in data["post_times"]:
            current = conn.execute(
                "SELECT posted_at FROM post WHERE id=?", (post["id"],)
            ).fetchone()
            if current is None or current[0] != post["after"]:
                raise ConflictError("平台发布时间已改变，未撤销")
        q = ",".join("?" for _ in ids)
        conn.execute(f"DELETE FROM source_evidence WHERE image_id IN ({q})", ids)
        conn.execute(f"DELETE FROM image_source WHERE image_id IN ({q})", ids)
        for table, key in (("image_source", "sources"), ("source_evidence", "evidence")):
            for row in data["before"][key]:
                cols = list(row)
                conn.execute(
                    f"INSERT INTO {table} ({','.join(cols)}) "
                    f"VALUES ({','.join('?' for _ in cols)})",
                    list(row.values()),
                )
        for post in data["post_times"]:
            conn.execute("UPDATE post SET posted_at=? WHERE id=?", (post["before"], post["id"]))
        update_log(conn, log_id, {**data, "undone": True, "undo_error": ""})
        log_operation(conn, "undo_review", {"target": log_id})
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
