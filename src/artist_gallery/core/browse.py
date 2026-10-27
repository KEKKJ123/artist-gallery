"""两区导航与已归档查询，不扫描文件夹或按平台划分图片。"""

import sqlite3
from typing import Any

from artist_gallery.core.images import list_images
from artist_gallery.core.inbox import count_inbox_hinted


def navigation(conn: sqlite3.Connection) -> dict[str, int]:
    counts = dict(conn.execute("SELECT state, COUNT(*) FROM image GROUP BY state"))
    return {
        "inbox": counts.get("inbox", 0),
        "inbox_hinted": count_inbox_hinted(conn),
        "archived": counts.get("archived", 0),
    }


def list_archived(conn: sqlite3.Connection, *, offset: int = 0, limit: int = 100) -> dict[str, Any]:
    return list_images(conn, "archived", offset=offset, limit=limit)
