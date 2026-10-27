"""收件箱列表与来源建议统计的查询（只读）。

收件箱 = image.work_id 为 NULL 的图片。写操作（归档、合并作品）在 M1c 加入。
"""

from __future__ import annotations

import sqlite3
from typing import Any

from artist_gallery.core.images import IMAGE_COLUMNS, image_to_dict, normalize_pagination


class BadFilter(ValueError):
    """收件箱筛选参数不合法。"""


# 来源建议筛选：all = 不筛；hint = 只看有建议的；nohint = 只看没有建议的
HINT_FILTERS = ("all", "hint", "nohint")
_HAS_HINT = "(source_hint IS NOT NULL AND source_hint != '')"


def normalize_hint_filter(value: str | None) -> str:
    """空 / None 当作 all；不认识的值抛 BadFilter（不能悄悄当成 all，否则前端拼错了也看不出来）。"""
    if value is None or value == "":
        return "all"
    if value not in HINT_FILTERS:
        raise BadFilter(f"filter 必须是 {' / '.join(HINT_FILTERS)} 之一，收到 {value!r}")
    return value


def list_inbox(
    conn: sqlite3.Connection,
    *,
    offset: int = 0,
    limit: int = 100,
    hint_filter: str = "all",
) -> dict[str, Any]:
    """收件箱列表，按入库顺序（added_at, id）。返回 {filter, total, offset, limit, items}。

    hint_filter 在服务端筛选（见 HINT_FILTERS）：收件箱是分页加载的，只在前端过滤已加载的那一页
    会漏掉后面页里的图，而且"共 N 张"也会不对。
    """
    hint_filter = normalize_hint_filter(hint_filter)
    offset, limit = normalize_pagination(offset, limit)
    where = "work_id IS NULL"
    if hint_filter == "hint":
        where += f" AND {_HAS_HINT}"
    elif hint_filter == "nohint":
        where += f" AND NOT {_HAS_HINT}"
    total = conn.execute(f"SELECT COUNT(*) FROM image WHERE {where}").fetchone()[0]
    rows = conn.execute(
        f"SELECT {IMAGE_COLUMNS} FROM image WHERE {where} ORDER BY added_at, id LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return {
        "filter": hint_filter,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [image_to_dict(r) for r in rows],
    }


def count_inbox_hinted(conn: sqlite3.Connection) -> int:
    """收件箱里带来源建议的张数（给左侧导航和筛选条显示数字）。"""
    return conn.execute(
        f"SELECT COUNT(*) FROM image WHERE work_id IS NULL AND {_HAS_HINT}"
    ).fetchone()[0]
