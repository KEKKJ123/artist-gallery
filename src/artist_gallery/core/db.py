"""数据库连接、初始化与迁移。

打开已有图库一律用 `open_library()`：它负责连接、迁移、同步内置平台，调用方不必记住顺序。
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

DB_NAME = "library.db"

# 结构变更：在末尾追加 SQL 字符串，不改已有条目。
# 第 i 条（从 0 开始）把 user_version 从 i+1 升到 i+2；schema.sql 本身是版本 1。
# 注意：内置平台的规则不再通过迁移修改，见 platforms.py。
MIGRATIONS: list[str] = [
    # v1 → v2（2026-10-26）：记录原始文件名和中置信来源建议；
    # 给内置文件名正则加数字边界，避免 X 的长 ID 末尾被误认成 Pixiv ID。
    # （v4 起内置平台规则由 sync_builtin_platforms 覆盖，这里对 platform 的修改
    #   已无实际作用；按"不改已有迁移"的规则保留原样。v3 同理。）
    r"""
    ALTER TABLE image ADD COLUMN orig_name TEXT;
    ALTER TABLE image ADD COLUMN source_hint TEXT;  -- JSON: {platform, post_id, page}
    UPDATE platform SET file_regex = '(?<!\d)(?P<post_id>\d{6,10})_p(?P<page>\d+)'
      WHERE id = 'pixiv';
    UPDATE platform SET file_regex = '(?<![0-9A-Za-z])x_(?P<post_id>\d{15,20})_p(?P<page>\d+)'
      WHERE id = 'x';
    """,
    # v2 → v3（2026-10-26）：内置 Zerochan（文件名形如 `Vigna.full.3017022`、`Vigna.600.3004963`）
    r"""
    INSERT OR IGNORE INTO platform (id, name, post_url, user_url, url_regex, file_regex) VALUES
      ('zerochan', 'Zerochan',
       'https://www.zerochan.net/{post_id}',
       NULL,
       'zerochan\.net/(?P<post_id>\d+)',
       '\.(?:full|\d{3,4})\.(?P<post_id>\d{5,9})$');
    """,
    # v3 → v4（2026-10-26）：区分内置/自定义平台；同一作品同一页不允许重复登记。
    r"""
    ALTER TABLE platform ADD COLUMN builtin INTEGER NOT NULL DEFAULT 0;
    UPDATE platform SET builtin = 1 WHERE id IN ('pixiv', 'x', 'zerochan');
    CREATE INDEX IF NOT EXISTS idx_image_work_page ON image(work_id, page);
    """,
]

SCHEMA_VERSION = 1 + len(MIGRATIONS)


class NotALibraryError(FileNotFoundError):
    pass


def connect(root: Path) -> sqlite3.Connection:
    """底层连接。业务代码请用 open_library()。"""
    conn = sqlite3.connect(root / DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "PRAGMA busy_timeout = 5000"
    )  # 另一个进程（如以后的 server）在写时等待而不是立刻报错
    return conn


def open_library(root: Path) -> sqlite3.Connection:
    """打开已有图库：检查存在 → 连接 → 迁移 → 同步内置平台。"""
    if not (root / DB_NAME).is_file():
        raise NotALibraryError(f"不是图库（找不到 {DB_NAME}）：{root}")
    conn = connect(root)
    try:
        migrate(conn)
        sync_builtin_platforms(conn)
    except BaseException:
        conn.close()
        raise
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
        sync_builtin_platforms(conn)
    finally:
        conn.close()
    return db_path


def migrate(conn: sqlite3.Connection) -> int:
    """把数据库升级到最新版本，返回升级后的版本号。

    每条迁移和版本号更新在同一个事务里：中途失败会整体回滚，不会出现"改了一半"的库。
    （sqlite3 的 executescript 会先 COMMIT，所以这里手动 BEGIN/COMMIT，不依赖 with conn。）
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"数据库版本 {version} 比程序支持的 {SCHEMA_VERSION} 新，请先升级程序")
    for i in range(version - 1, len(MIGRATIONS)):
        try:
            conn.executescript(f"BEGIN;\n{MIGRATIONS[i]}\nPRAGMA user_version = {i + 2};\nCOMMIT;")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return conn.execute("PRAGMA user_version").fetchone()[0]


def sync_builtin_platforms(conn: sqlite3.Connection) -> None:
    """把代码里的内置平台定义写进 platform 表（新增或覆盖），自定义平台不动。"""
    from artist_gallery.core.platforms import BUILTIN_PLATFORMS

    with conn:
        for p in BUILTIN_PLATFORMS:
            conn.execute(
                """
                INSERT INTO platform (id, name, post_url, user_url, url_regex, file_regex, builtin)
                VALUES (?, ?, ?, ?, ?, NULL, 1)
                ON CONFLICT(id) DO UPDATE SET
                  name = excluded.name, post_url = excluded.post_url,
                  user_url = excluded.user_url, url_regex = excluded.url_regex,
                  file_regex = NULL, builtin = 1
                """,
                (p.id, p.name, p.post_url, p.user_url, p.url_regex),
            )
