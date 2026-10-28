"""来源核查：离线逐行解析、显式人工决定和整批事务，不执行归档。"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from artist_gallery.core import operations as ops
from artist_gallery.core.images import IMAGE_COLUMNS, IMAGE_FROM, images_to_list
from artist_gallery.core.recognize import MAX_PAGE

MAX_TEXT = 64000


def parse_links(conn: sqlite3.Connection, text: str) -> list[dict]:
    """完整 URL 校验后再解析，不请求外站，不从发帖账号推断作者。"""
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        raise ops.OperationError("链接文本过长（最多 64000 字符）")
    result = []
    platforms = list(conn.execute("SELECT id,url_regex FROM platform ORDER BY builtin DESC,id"))
    for number, raw in enumerate(text.splitlines(), 1):
        value = raw.strip()
        if not value:
            continue
        entry: dict[str, Any] = {"line": number, "input": value}
        try:
            url = urlsplit(value)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
            ):
                raise ValueError("请填写完整的 http(s) 发布链接")
            if any(c.isspace() for c in value) or url.port not in {None, 80, 443}:
                raise ValueError("链接包含空白或不支持的端口")
            host = url.hostname.lower().removeprefix("www.").removeprefix("mobile.")
            path = url.path.rstrip("/")
            platform = post_id = None
            page = None
            if host == "pixiv.net":
                m = re.fullmatch(r"/(?:[a-zA-Z-]+/)?artworks/([0-9]+)", path)
                post_id = m[1] if m else None
                platform = "pixiv"
            elif host in {"x.com", "twitter.com"}:
                m = re.fullmatch(
                    r"/(?:[A-Za-z0-9_]+|i/web)/status/([0-9]+)(?:/photo/([0-9]+))?", path
                )
                post_id = m[1] if m else None
                platform = "x"
                if m and m[2]:
                    digits = m[2].lstrip("0") or "0"
                    if len(digits) > 16 or not 1 <= int(digits) <= MAX_PAGE + 1:
                        raise ValueError("链接中的图片位置超出范围")
                    page = int(digits) - 1
            elif host == "zerochan.net":
                m = re.fullmatch(r"/([0-9]+)", path)
                post_id = m[1] if m else None
                platform = "zerochan"
            else:
                # 自定义平台只允许整个 URL 匹配，不能把 evil.example/?url=... 当成来源。
                for row in platforms:
                    if row["id"] in {"pixiv", "x", "zerochan"} or not row["url_regex"]:
                        continue
                    try:
                        m = re.fullmatch(row["url_regex"], value)
                    except re.error:
                        continue
                    if m and m.groupdict().get("post_id"):
                        platform, post_id = row["id"], m["post_id"]
                        break
            if not post_id or platform not in {r["id"] for r in platforms}:
                raise ValueError("无法识别为已登记平台的具体发布；账号页和图片直链不能代替帖子链接")
            if len(post_id) > 256:
                raise ValueError("发布 ID 过长")
            # 无页码链接保持未知；不读取查询参数猜作者或发布时间。
            entry.update(platform=platform, post_id=post_id, page=page)
        except ValueError as e:
            entry["error"] = str(e)
        result.append(entry)
    return result


def detail(conn: sqlite3.Connection, image_id: int) -> dict:
    row = conn.execute(
        f"SELECT {IMAGE_COLUMNS} FROM {IMAGE_FROM} WHERE i.id=?", (image_id,)
    ).fetchone()
    if row is None:
        raise ops.OperationError("图片不存在")
    item = images_to_list(conn, [row])[0]
    item["sources"] = [
        dict(r)
        for r in conn.execute(
            "SELECT s.id,s.page,s.status,s.confirmed_at,p.platform,p.post_id,p.posted_at "
            "FROM image_source s JOIN post p ON p.id=s.post_id WHERE s.image_id=? ORDER BY s.id",
            (image_id,),
        )
    ]
    item["evidence"] = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM source_evidence WHERE image_id=? ORDER BY id", (image_id,)
        )
    ]
    for source in item["sources"]:
        source["time_image_ids"] = [
            r[0]
            for r in conn.execute(
                "SELECT s.image_id FROM image_source s JOIN post p ON p.id=s.post_id "
                "WHERE p.platform=? AND p.post_id=? ORDER BY s.image_id",
                (source["platform"], source["post_id"]),
            )
        ]
    item["revision"] = ops.revision(conn, image_id)
    return item


def _page(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if type(value) is not int or not 0 <= value <= MAX_PAGE:
        raise ops.OperationError("页码必须是非负整数或留空，未知不会补为 p0")
    return value


def _time(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise ops.OperationError("发布时间格式不正确")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError
    except ValueError as e:
        raise ops.OperationError(
            "发布时间请带时区，例如 2026-10-28T12:00:00+08:00；未知可留空"
        ) from e
    return dt.isoformat()


def save(
    conn: sqlite3.Connection,
    ids: list[int],
    expected: dict,
    *,
    text: str = "",
    edits: list[dict] | None = None,
    evidence_edits: list[dict] | None = None,
    confirm_scope: bool = False,
) -> dict:
    """链接只追加待核查，确认必须来自 edits 的显式决定；同一事务影响精确选择。"""
    ids = ops.image_ids(ids)
    parsed = parse_links(conn, text)
    links = [line for line in parsed if "error" not in line]
    if len(ids) > 1 and links and confirm_scope is not True:
        raise ops.OperationError("请明确确认：全部有效链接添加给每张所选图片")
    edits = [] if edits is None else edits
    if not isinstance(edits, list) or len(edits) > 1000:
        raise ops.OperationError("来源修改列表不正确")
    evidence_edits = [] if evidence_edits is None else evidence_edits
    if not isinstance(evidence_edits, list) or len(evidence_edits) > 1000:
        raise ops.OperationError("线索修改列表不正确")
    if (edits or evidence_edits) and len(ids) != 1:
        raise ops.OperationError("已有来源的核查请逐图进行，不把一张图的决定传播给其他图片")
    if len(ids) > 1 and confirm_scope is not True:
        raise ops.OperationError("大范围操作需要清单确认")
    conn.execute("BEGIN IMMEDIATE")
    try:
        ops.require_idle(conn)
        ops.check_revisions(conn, ids, expected)
        before = ops.source_snapshot(conn, ids)
        post_times = []
        for image_id in ids:
            for link in links:
                conn.execute(
                    "INSERT INTO post(platform,post_id) VALUES(?,?) ON CONFLICT DO NOTHING",
                    (link["platform"], link["post_id"]),
                )
                post = conn.execute(
                    "SELECT id FROM post WHERE platform=? AND post_id=?",
                    (link["platform"], link["post_id"]),
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO image_source(image_id,post_id,page) VALUES(?,?,?) "
                    "ON CONFLICT DO NOTHING",
                    (image_id, post, link["page"]),
                )
                source = conn.execute(
                    "SELECT id FROM image_source WHERE image_id=? AND post_id=?", (image_id, post)
                ).fetchone()[0]
                key = hashlib.sha256(
                    ops.encode(
                        [
                            image_id,
                            "link-v1",
                            link["input"],
                            link["platform"],
                            link["post_id"],
                            link["page"],
                        ]
                    ).encode()
                ).hexdigest()
                conn.execute(
                    "INSERT INTO source_evidence(image_id,source_id,platform,post_id,page,"
                    "input_kind,input_text,rule_key,confidence,evidence_key) "
                    "VALUES(?,?,?,?,?,'link',?,'link-v1','high',?) "
                    "ON CONFLICT(evidence_key) DO NOTHING",
                    (
                        image_id,
                        source,
                        link["platform"],
                        link["post_id"],
                        link["page"],
                        link["input"],
                        key,
                    ),
                )
        seen = set()
        for edit in edits:
            if not isinstance(edit, dict) or type(edit.get("id")) is not int or edit["id"] in seen:
                raise ops.OperationError("来源修改编号重复或无效")
            seen.add(edit["id"])
            source = conn.execute(
                "SELECT * FROM image_source WHERE id=? AND image_id=?", (edit["id"], ids[0])
            ).fetchone()
            if source is None:
                raise ops.ConflictError("来源不属于当前图片，未执行修改")
            if edit.get("remove") is True:
                conn.execute(
                    "UPDATE source_evidence SET source_id=NULL,dismissed=1 WHERE source_id=?",
                    (source["id"],),
                )
                conn.execute("DELETE FROM image_source WHERE id=?", (source["id"],))
                continue
            status = edit.get("status", source["status"])
            if status not in {"pending", "confirmed", "rejected"}:
                raise ops.OperationError("来源核查状态无效")
            page = _page(edit.get("page", source["page"]))
            conn.execute(
                "UPDATE image_source SET status=?,page=?,confirmed_at=CASE WHEN ?='confirmed' "
                "THEN COALESCE(confirmed_at,datetime('now')) ELSE NULL END WHERE id=?",
                (status, page, status, source["id"]),
            )
            if "posted_at" in edit:
                posted_at = _time(edit["posted_at"])
                post = conn.execute(
                    "SELECT posted_at FROM post WHERE id=?", (source["post_id"],)
                ).fetchone()
                if posted_at != post[0]:
                    # 发布的时间由共享帖子所有；清单由接口返回其影响数，不能自动抓取推断。
                    affected = conn.execute(
                        "SELECT COUNT(*) FROM image_source WHERE post_id=?", (source["post_id"],)
                    ).fetchone()[0]
                    affected_ids = [
                        r[0]
                        for r in conn.execute(
                            "SELECT image_id FROM image_source WHERE post_id=? ORDER BY image_id",
                            (source["post_id"],),
                        )
                    ]
                    if affected > 1 and (
                        confirm_scope is not True or edit.get("time_scope_ids") != affected_ids
                    ):
                        raise ops.OperationError(
                            f"该发布时间关联 {affected} 张图片，请先确认共享发布的修改范围"
                        )
                    post_times.append(
                        {"id": source["post_id"], "before": post[0], "after": posted_at}
                    )
                    conn.execute(
                        "UPDATE post SET posted_at=? WHERE id=?", (posted_at, source["post_id"])
                    )
        for edit in evidence_edits:
            if (
                not isinstance(edit, dict)
                or type(edit.get("id")) is not int
                or type(edit.get("dismissed")) is not bool
            ):
                raise ops.OperationError("线索决定无效")
            evidence = conn.execute(
                "SELECT id FROM source_evidence WHERE id=? AND image_id=? AND source_id IS NULL",
                (edit["id"], ids[0]),
            ).fetchone()
            if evidence is None:
                raise ops.ConflictError("线索不属于当前图片或应通过具体来源核查")
            conn.execute(
                "UPDATE source_evidence SET dismissed=? WHERE id=?",
                (int(edit["dismissed"]), edit["id"]),
            )
        after = ops.source_snapshot(conn, ids)
        log_id = None
        if before != after or post_times:
            log_id = ops.log_operation(
                conn,
                "review",
                {"status": "done", "before": before, "after": after, "post_times": post_times},
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return {"operation_id": log_id, "lines": parsed, "items": [detail(conn, i) for i in ids]}
