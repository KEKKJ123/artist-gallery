"""导入线索的记录；不执行人工确认、不改图片整理状态。"""

import hashlib
import json
import sqlite3

from artist_gallery.core.recognize import Confidence, Recognition


def record_filename(
    conn: sqlite3.Connection, image_id: int, file_id: int, name: str, rec: Recognition
) -> bool:
    """同一输入／规则只保存一次；新页码线索不会覆盖已有来源属性。调用方控制事务。"""
    if rec.confidence is Confidence.NONE or not rec.platform:
        return False
    key = hashlib.sha256(
        json.dumps(
            [image_id, file_id, name, rec.rule_key, rec.platform, rec.post_id, rec.page],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    if conn.execute("SELECT 1 FROM source_evidence WHERE evidence_key=?", (key,)).fetchone():
        return False
    source_id = None
    if rec.post_id is not None:
        conn.execute(
            "INSERT INTO post (platform, post_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (rec.platform, rec.post_id),
        )
        post = conn.execute(
            "SELECT id FROM post WHERE platform=? AND post_id=?", (rec.platform, rec.post_id)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO image_source (image_id, post_id, page) VALUES (?, ?, ?)"
            " ON CONFLICT DO NOTHING",
            (image_id, post, rec.page),
        )
        source_id = conn.execute(
            "SELECT id FROM image_source WHERE image_id=? AND post_id=?", (image_id, post)
        ).fetchone()[0]
    conn.execute(
        "INSERT INTO source_evidence (image_id, file_id, source_id, platform, post_id, page,"
        " input_kind, input_text, rule_key, confidence, evidence_key)"
        " VALUES (?, ?, ?, ?, ?, ?, 'filename', ?, ?, ?, ?)",
        (
            image_id,
            file_id,
            source_id,
            rec.platform,
            rec.post_id,
            rec.page,
            name,
            rec.rule_key,
            rec.confidence.value,
            key,
        ),
    )
    return True
