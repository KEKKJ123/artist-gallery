"""按文件夹浏览已归档的图片（只读）。

"文件夹"指 `images/` 之下的目录，完全由数据库里 image.rel_path 推出来，不读磁盘：
- 数据库是唯一的事实来源（和收件箱一致），磁盘上多出来的、数据库不认识的文件不会出现。
- 路径从不拼到文件系统调用里，所以不存在目录穿越问题。

约定：
- 路径相对 `images/`，用 `/` 分隔，如 `pixiv`、`精选/红豆`。空字符串表示"全部已归档"。
- 一个文件夹包含它所有子文件夹里的图（点 `精选` 能看到 `精选/红豆` 里的）。
- `images/_inbox/` 是"收件箱"（尚未整理），不算已归档：不出现在文件夹列表里，也不计入"全部已归档"。
  收件箱有自己的视图（见 inbox.py）。
"""

from __future__ import annotations

import sqlite3
from typing import Any

from artist_gallery.core.importer import INBOX
from artist_gallery.core.inbox import IMAGE_COLUMNS, MAX_LIMIT, image_to_dict

IMAGES_DIR = "images"
INBOX_DIR = INBOX.name  # "_inbox"


class BadFolderPath(ValueError):
    """文件夹路径不合法（含 `..`、反斜杠等）。"""


def normalize_folder(path: str) -> str:
    """规整用户传来的文件夹路径：去掉首尾的 `/`，拒绝 `.`、`..`、空段、反斜杠、NUL。"""
    p = path.strip("/")
    if not p:
        return ""
    for seg in p.split("/"):
        if seg in ("", ".", "..") or "\\" in seg or "\x00" in seg:
            raise BadFolderPath(f"文件夹路径不合法：{path!r}")
    return p


def _bounds(folder: str) -> tuple[str, str]:
    """某文件夹（含子文件夹）下所有 rel_path 所在的半开区间 [lo, hi)。

    比 LIKE 'prefix%' 可靠：文件夹名里的 `%`、`_` 不会被当成通配符，
    而且 rel_path 有唯一索引，范围查询能直接用上。
    '/' 的下一个字符是 '0'，所以 'images/x/…' 恰好都落在 ['images/x/', 'images/x0') 里，
    而同名前缀的兄弟（'images/x2/'、'images/x-1/'、'images/x.png'）都不在其中。
    """
    prefix = f"{IMAGES_DIR}/{folder}/" if folder else f"{IMAGES_DIR}/"
    return prefix, prefix[:-1] + "0"


def list_folders(conn: sqlite3.Connection) -> dict[str, Any]:
    """左侧导航需要的全部信息：收件箱张数、已归档总数、文件夹树（扁平列表，父在子之前）。

    folders[i] = {path, name, depth, count, has_children}，count 含子文件夹。
    """
    inbox = conn.execute("SELECT COUNT(*) FROM image WHERE work_id IS NULL").fetchone()[0]

    lo, hi = _bounds("")
    counts: dict[str, int] = {}
    archived = 0
    for (rel,) in conn.execute(
        "SELECT rel_path FROM image WHERE rel_path >= ? AND rel_path < ?", (lo, hi)
    ):
        dirs = rel.split("/")[1:-1]  # 去掉开头的 images 和末尾的文件名
        if dirs and dirs[0] == INBOX_DIR:
            continue  # 收件箱不算已归档
        archived += 1
        for i in range(1, len(dirs) + 1):  # 每一级祖先都要计数
            key = "/".join(dirs[:i])
            counts[key] = counts.get(key, 0) + 1

    parents = {p.rpartition("/")[0] for p in counts if "/" in p}
    # 逐段不区分大小写比较：列表比较时"前缀更短的排前面"，所以父文件夹必然在子文件夹之前。
    # 第二关键字（原路径）只在两个路径仅大小写不同时打破平局，保证顺序稳定。
    ordered = sorted(counts, key=lambda p: ([s.casefold() for s in p.split("/")], p))
    folders = [
        {
            "path": p,
            "name": p.rpartition("/")[2],
            "depth": p.count("/"),
            "count": counts[p],
            "has_children": p in parents,
        }
        for p in ordered
    ]
    return {"inbox": inbox, "archived": archived, "folders": folders}


def list_folder_images(
    conn: sqlite3.Connection, folder: str, *, offset: int = 0, limit: int = 100
) -> dict[str, Any]:
    """某文件夹（含子文件夹）里的图，按路径排序（同一作品的几页会挨在一起）。

    folder 须是 normalize_folder 的结果。不存在的文件夹返回空列表，不报错
    （前端的书签或旧页面可能指向已被移走的文件夹）。
    """
    offset = max(0, offset)
    limit = min(max(1, limit), MAX_LIMIT)
    lo, hi = _bounds(folder)
    where, params = "rel_path >= ? AND rel_path < ?", [lo, hi]
    if folder == "":
        ilo, ihi = _bounds(INBOX_DIR)
        where += " AND NOT (rel_path >= ? AND rel_path < ?)"
        params += [ilo, ihi]
    total = conn.execute(f"SELECT COUNT(*) FROM image WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT {IMAGE_COLUMNS} FROM image WHERE {where} ORDER BY rel_path, id LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {
        "folder": folder,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [image_to_dict(r) for r in rows],
    }
