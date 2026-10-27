"""按显式整理状态查询收件箱及建议筛选。"""

import sqlite3
from typing import Any

from artist_gallery.core.images import HAS_HINT, list_images

HINT_FILTERS = ("all", "hint", "nohint")


class BadFilter(ValueError):
    pass


def normalize_hint_filter(value: str | None) -> str:
    if value is None or value == "":
        return "all"
    if value not in HINT_FILTERS:
        raise BadFilter(f"filter 必须是 {' / '.join(HINT_FILTERS)} 之一，收到 {value!r}")
    return value


def list_inbox(
    conn: sqlite3.Connection, *, offset: int = 0, limit: int = 100, hint_filter: str = "all"
) -> dict[str, Any]:
    hint_filter = normalize_hint_filter(hint_filter)
    extra = (
        ""
        if hint_filter == "all"
        else f" AND {'NOT ' if hint_filter == 'nohint' else ''}{HAS_HINT}"
    )
    return {
        "filter": hint_filter,
        **list_images(conn, "inbox", offset=offset, limit=limit, extra=extra),
    }


def count_inbox_hinted(conn: sqlite3.Connection) -> int:
    return conn.execute(
        f"SELECT COUNT(*) FROM image i WHERE i.state='inbox' AND {HAS_HINT}"
    ).fetchone()[0]
