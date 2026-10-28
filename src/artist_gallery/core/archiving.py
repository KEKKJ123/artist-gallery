"""归档、倒序撤销及显式中断恢复。数据库事务不能撤回磁盘操作。

先提交完整意图；所有目标均复制校验并持久记录所有权后才删旧位置；最后发布数据库。
任一步失败留 pending 和完好副本，阻断后续写操作，由用户查看清单后继续或恢复操作前。
不扫描猜选版本，不覆盖目标，不删除无法证明由当前操作创建且内容未变的文件。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path, PurePosixPath

from artist_gallery.core import operations as ops
from artist_gallery.core.fileops import _fsync_dir, copy_verified, sha256_file
from artist_gallery.core.layout import ARCHIVED


def media_path(root: Path, rel: str) -> Path:
    pure = PurePosixPath(rel)
    if (
        pure.is_absolute()
        or not pure.parts
        or pure.parts[0] != "images"
        or ".." in pure.parts
        or "\\" in rel
    ):
        raise ops.OperationError("图库文件路径异常，未操作")
    target = root / rel
    base = root.resolve()
    # 不跟随符号链接／Windows junction，避免库内路径穿到另一位置。
    for part in [target, *target.parents]:
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ops.OperationError("图库文件路径包含链接，未操作")
    if not target.resolve().is_relative_to(base / "images"):
        raise ops.OperationError("图库文件路径超出图片目录，未操作")
    return target


def _identity(path: Path) -> list[int]:
    s = path.stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]


def _valid(path: Path, sha: str) -> bool:
    return path.is_file() and sha256_file(path) == sha


def _occupied(root: Path, rel: str) -> bool:
    path = media_path(root, rel)
    return path.parent.exists() and any(
        p.name.casefold() == path.name.casefold() for p in path.parent.iterdir()
    )


def _unique(root: Path, name: str, taken: set[str]) -> str:
    path = PurePosixPath(name)
    for n in range(1, 100000):
        suffix = "" if n == 1 else f"_{n}"
        budget = 255 - len((suffix + path.suffix).encode())
        stem = path.stem.encode()[:budget].decode("utf-8", "ignore").rstrip(" .")
        rel = str(ARCHIVED / f"{stem}{suffix}{path.suffix}")
        if rel.casefold() not in taken and not _occupied(root, rel):
            taken.add(rel.casefold())
            return rel
    raise ops.OperationError("目标名称冲突过多，未归档")


def _plan(conn: sqlite3.Connection, root: Path, ids: list[int], force: bool) -> dict:
    images = []
    moves = []
    errors = []
    taken = {r[0].casefold() for r in conn.execute("SELECT rel_path FROM image_file")}
    for image_id in ids:
        row = conn.execute("SELECT state FROM image WHERE id=?", (image_id,)).fetchone()
        if row is None or row[0] != "inbox":
            errors.append({"image_id": image_id, "reason": "图片不存在或已经归档"})
            continue
        if (
            not force
            and not conn.execute(
                "SELECT 1 FROM image_source WHERE image_id=? AND status='confirmed'", (image_id,)
            ).fetchone()
        ):
            errors.append(
                {"image_id": image_id, "reason": "没有人工确认的具体发布；可另选范围或显式强制归档"}
            )
        files = list(
            conn.execute("SELECT * FROM image_file WHERE image_id=? ORDER BY id", (image_id,))
        )
        if not files or not any(f["is_display"] for f in files):
            errors.append(
                {"image_id": image_id, "reason": "展示文件待设置，强制归档也不能绕过文件安全"}
            )
        images.append({"id": image_id, "from": "inbox", "to": "archived"})
        for f in files:
            try:
                src = media_path(root, f["rel_path"])
                if f["missing"] or not _valid(src, f["sha256"]):
                    raise ops.OperationError("文件缺失或内容校验不符")
                target = _unique(root, PurePosixPath(f["rel_path"]).name, taken)
                moves.append(
                    {
                        "file_id": f["id"],
                        "image_id": image_id,
                        "from": f["rel_path"],
                        "to": target,
                        "sha256": f["sha256"],
                        "source_identity": _identity(src),
                        "target_identity": None,
                    }
                )
            except (OSError, ops.OperationError) as e:
                errors.append({"image_id": image_id, "reason": str(e)})
    return {"images": images, "moves": moves, "errors": errors, "force": force}


def preview(conn: sqlite3.Connection, root: Path, ids: list[int], *, force: bool = False) -> dict:
    ids = ops.image_ids(ids)
    ops.require_idle(conn)
    result = _plan(conn, root, ids, force)
    # 令牌绑定文件、路径、资料与操作范围；点击后数据改变会拒绝，不自动替换计划。
    import hashlib

    result["revisions"] = {str(i): ops.revision(conn, i) for i in ids}
    result["token"] = hashlib.sha256(ops.encode(result).encode()).hexdigest()
    return result


def _persist(conn: sqlite3.Connection, log_id: int, data: dict) -> None:
    ops.update_log(conn, log_id, data)
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")


def _check_records(conn: sqlite3.Connection, data: dict) -> None:
    for image in data["images"]:
        row = conn.execute("SELECT state FROM image WHERE id=?", (image["id"],)).fetchone()
        if row is None or row[0] != image["from"]:
            raise ops.ConflictError("图片状态与文件操作意图不符，保留现状")
    expected_files = {m["file_id"] for m in data["moves"]}
    actual_files = {
        r[0]
        for image in data["images"]
        for r in conn.execute("SELECT id FROM image_file WHERE image_id=?", (image["id"],))
    }
    if expected_files != actual_files:
        raise ops.ConflictError("文件版本列表已改变，保留现状")
    for m in data["moves"]:
        row = conn.execute(
            "SELECT image_id,rel_path,sha256 FROM image_file WHERE id=?", (m["file_id"],)
        ).fetchone()
        if row is None or list(row) != [m["image_id"], m["from"], m["sha256"]]:
            raise ops.ConflictError("文件记录与操作意图不符，保留现状")


def _target(root: Path, m: dict) -> Path:
    dst = media_path(root, m["to"])
    if (
        not m["target_identity"]
        or not _valid(dst, m["sha256"])
        or _identity(dst) != m["target_identity"]
    ):
        raise ops.ConflictError(f"目标副本缺失、被改动或无法证明所有权：{m['to']}；不覆盖或删除")
    return dst


def _finish(conn: sqlite3.Connection, root: Path, log_id: int, data: dict) -> None:
    _check_records(conn, data)
    for m in data["moves"]:
        src, dst = media_path(root, m["from"]), media_path(root, m["to"])
        if m["target_identity"]:
            _target(root, m)
        else:
            if not _valid(src, m["sha256"]) or _identity(src) != m["source_identity"]:
                raise ops.ConflictError(f"原文件已变化：{m['from']}")
            if _occupied(root, m["to"]):
                raise ops.ConflictError(
                    f"目标已占用或上次复制结果未登记：{m['to']}；保留文件，请人工核对"
                )
            copy_verified(src, dst, m["sha256"])
            m["target_identity"] = _identity(dst)
            _persist(conn, log_id, data)
    # 删除之前复核整个批次，不能因前半批可用就暗中只处理一部分。
    for m in data["moves"]:
        _target(root, m)
        src = media_path(root, m["from"])
        if src.exists() and (
            not _valid(src, m["sha256"]) or _identity(src) != m["source_identity"]
        ):
            raise ops.ConflictError(f"原文件已变化：{m['from']}；保留现状")
    data["phase"] = "removing"
    _persist(conn, log_id, data)
    for m in data["moves"]:
        src = media_path(root, m["from"])
        if src.exists():
            _target(root, m)
            if not _valid(src, m["sha256"]) or _identity(src) != m["source_identity"]:
                raise ops.ConflictError("删除旧位置前复核失败，已保留文件")
            src.unlink()
            _fsync_dir(src.parent)
    _check_records(conn, data)
    for m in data["moves"]:
        _target(root, m)
        conn.execute("UPDATE image_file SET rel_path=? WHERE id=?", (m["to"], m["file_id"]))
    for image in data["images"]:
        conn.execute("UPDATE image SET state=? WHERE id=?", (image["to"], image["id"]))
    data.update(status="done", phase="complete", error="")
    ops.update_log(conn, log_id, data)
    if data.get("undo_of"):
        original = json.loads(
            conn.execute("SELECT payload FROM op_log WHERE id=?", (data["undo_of"],)).fetchone()[0]
        )
        ops.update_log(conn, data["undo_of"], {**original, "undone": True, "undo_error": ""})
    conn.commit()


def _run(conn: sqlite3.Connection, root: Path, log_id: int, data: dict) -> dict:
    try:
        _finish(conn, root, log_id, data)
    except BaseException as e:
        conn.rollback()
        # 始终从持久化日志读，不把内存中尚未提交的所有权误写为已知。
        try:
            with conn:
                stored = json.loads(
                    conn.execute("SELECT payload FROM op_log WHERE id=?", (log_id,)).fetchone()[0]
                )
                ops.update_log(conn, log_id, {**stored, "error": str(e)})
        except sqlite3.Error:
            pass
        if not isinstance(e, Exception):
            raise
        raise ops.ConflictError(
            f"文件操作 #{log_id} 尚未完成：{e}。保留副本与恢复记录，请先检查恢复"
        ) from e
    return {"operation_id": log_id, "status": "done"}


def archive(
    conn: sqlite3.Connection,
    root: Path,
    ids: list[int],
    token: str,
    *,
    force: bool = False,
    confirmed: bool = False,
) -> dict:
    ids = ops.image_ids(ids)
    conn.execute("BEGIN IMMEDIATE")
    try:
        plan = preview(conn, root, ids, force=force)
        if plan["errors"]:
            raise ops.OperationError(
                "所选图片存在缺项或文件异常，整批未执行；请查看清单并重新选择范围"
            )
        if plan["token"] != token:
            raise ops.ConflictError("归档计划已改变，请重新预览")
        if (force or len(ids) > 1) and confirmed is not True:
            raise ops.OperationError("强制归档或大范围操作需要显式清单确认")
        data = {**plan, "status": "pending", "phase": "copying"}
        log_id = ops.log_operation(conn, "archive", data)
        conn.commit()  # 意图持久化之前绝不复制／删除。
        conn.execute("BEGIN IMMEDIATE")
    except BaseException:
        conn.rollback()
        raise
    return _run(conn, root, log_id, data)


def undo(conn: sqlite3.Connection, root: Path, expected_id: int) -> dict:
    top = ops.latest(conn)
    if top.get("id") != expected_id or not top["can_undo"]:
        raise ops.ConflictError("撤销顺序已改变，请刷新")
    if top["kind"] == "review":
        ops.undo_review(conn, expected_id)
        return {"status": "done"}
    conn.execute("BEGIN IMMEDIATE")
    try:
        ops.require_idle(conn)
        if ops.latest(conn).get("id") != expected_id:
            raise ops.ConflictError("撤销顺序已改变，请刷新")
        original = json.loads(
            conn.execute("SELECT payload FROM op_log WHERE id=?", (expected_id,)).fetchone()[0]
        )
        moves = []
        for m in original["moves"]:
            src = media_path(root, m["to"])
            if not _valid(src, m["sha256"]) or _occupied(root, m["from"]):
                raise ops.ConflictError("文件已变化、缺失或原位置被占用；撤销未执行，不覆盖不删除")
            moves.append(
                {
                    **m,
                    "from": m["to"],
                    "to": m["from"],
                    "source_identity": _identity(src),
                    "target_identity": None,
                }
            )
        data = {
            "status": "pending",
            "phase": "copying",
            "undo_of": expected_id,
            "moves": moves,
            "images": [
                {"id": i["id"], "from": i["to"], "to": i["from"]} for i in original["images"]
            ],
        }
        _check_records(conn, data)
        log_id = ops.log_operation(conn, "undo_archive", data)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
    except BaseException:
        conn.rollback()
        raise
    return _run(conn, root, log_id, data)


def recover(
    conn: sqlite3.Connection, root: Path, log_id: int, *, action: str, confirmed: bool
) -> dict:
    """显式恢复。不执行删源，不自动猜测未登记副本属于本次操作。"""
    if confirmed is not True or action not in {"finish", "rollback"}:
        raise ops.OperationError("请查看完整文件清单后明确选择继续完成或恢复操作前")
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT kind,payload FROM op_log WHERE id=?", (log_id,)).fetchone()
        if row is None or row["kind"] not in {"archive", "undo_archive"}:
            raise ops.OperationError("恢复记录不存在")
        data = json.loads(row["payload"])
        if data.get("status") != "pending":
            raise ops.ConflictError("操作已结束，请刷新恢复记录")
        if action == "finish":
            if data.get("recovery") == "rollback":
                raise ops.ConflictError("已开始恢复操作前，请继续恢复，不反向切换")
            return _run(conn, root, log_id, data)
        _check_records(conn, data)
        # 先完整预检；目标所有权未知时不能通过取消操作偷偷删除目标。
        for m in data["moves"]:
            src = media_path(root, m["from"])
            if src.exists() and not _valid(src, m["sha256"]):
                raise ops.ConflictError("原位置文件内容已改变，保留现状")
            if m["target_identity"]:
                dst = media_path(root, m["to"])
                if not (m.get("cleanup_started") and not dst.exists()):
                    _target(root, m)
            elif _occupied(root, m["to"]):
                raise ops.ConflictError("存在所有权未登记的目标文件，保留现状，请人工核对")
            elif not src.exists():
                raise ops.ConflictError("两处均无完整副本，保留现状")
        data["recovery"] = "rollback"
        _persist(conn, log_id, data)
        # 先让全部原位置拥有校验通过的副本，再删除当前操作自己的目标。
        for m in data["moves"]:
            src = media_path(root, m["from"])
            if not src.exists():
                copy_verified(_target(root, m), src, m["sha256"])
        for m in data["moves"]:
            if not _valid(media_path(root, m["from"]), m["sha256"]):
                raise ops.ConflictError("恢复副本校验失败，保留文件")
        for m in data["moves"]:
            if m["target_identity"]:
                dst = media_path(root, m["to"])
                # 清理意图先提交：断在 unlink 后也能重复完成恢复，不误判副本丢失。
                if not (m.get("cleanup_started") and not dst.exists()):
                    dst = _target(root, m)
                    m["cleanup_started"] = True
                    _persist(conn, log_id, data)
                    dst = _target(root, m)
                    if not _valid(media_path(root, m["from"]), m["sha256"]):
                        raise ops.ConflictError("删除恢复副本前原位置复核失败，保留文件")
                    dst.unlink()
                    _fsync_dir(dst.parent)
                m["target_identity"] = None
                _persist(conn, log_id, data)
        data.update(status="cancelled", error="", phase="rolled_back")
        ops.update_log(conn, log_id, data)
        conn.commit()
        return {"operation_id": log_id, "status": "cancelled"}
    except BaseException:
        conn.rollback()
        raise
