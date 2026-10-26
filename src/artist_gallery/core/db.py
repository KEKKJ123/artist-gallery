"""数据库连接、初始化与迁移。"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

DB_NAME = "library.db"

# 结构变更：在末尾追加 SQL 字符串，不改已有条目。
# 第 i 条（从 0 开始）把 user_version 从 i+1 升到 i+2；schema.sql 本身是版本 1。
MIGRATIONS: list[str] = []

SCHEMA_VERSION = 1 + len(MIGRATIONS)


def connect(root: Path) -> sqlite3.Connection:
    """打开图库根目录下的数据库。"""
    conn = sqlite3.connect(root / DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_library(root: Path) -> Path:
    """在 root 下新建图库；已存在则报错，不覆盖。"""
    root.mkdir(parents=True, exist_ok=True)
    db_path = root / DB_NAME
    if db_path.exists():
        raise FileExistsError(f"图库已存在：{db_path}")
    for sub in ("images/_inbox", ".cache/thumbs"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    schema = resources.files(__package__).joinpath("schema.sql").read_text("utf-8")
    conn = connect(root)
    try:
        with conn:
            conn.executescript(schema)
            conn.execute("PRAGMA user_version = 1")
        migrate(conn)
    finally:
        conn.close()
    return db_path


def migrate(conn: sqlite3.Connection) -> int:
    """把数据库升级到最新版本，返回升级后的版本号。"""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"数据库版本 {version} 比程序支持的 {SCHEMA_VERSION} 新，请先升级程序")
    for i in range(version - 1, len(MIGRATIONS)):
        with conn:
            conn.executescript(MIGRATIONS[i])
            conn.execute(f"PRAGMA user_version = {i + 2}")
    return conn.execute("PRAGMA user_version").fetchone()[0]
