"""当前格式初始化、按版本校验与事务升级；不保留改路线前旧库识别逻辑。"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

DB_NAME = "library.db"
APPLICATION_ID = 0x41475259  # AGRY
BASE_VERSION = 5  # 当前格式的起始版本
# 第 i 条升级 BASE_VERSION+i → BASE_VERSION+i+1；不改写基线 5。
MIGRATIONS: list[str] = [
    """
    CREATE TABLE library_meta (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
    INSERT INTO library_meta(key,value) VALUES ('id',lower(hex(randomblob(16))));
    CREATE TABLE review_draft (
      image_id INTEGER PRIMARY KEY REFERENCES image(id) ON DELETE CASCADE,
      payload TEXT NOT NULL,
      revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    ALTER TABLE source_evidence ADD COLUMN dismissed INTEGER NOT NULL DEFAULT 0
      CHECK(dismissed IN (0,1));
    """,
]
SCHEMA_VERSION = BASE_VERSION + len(MIGRATIONS)
_BASE_REQUIRED = {
    "image": {"id", "state", "artist_id", "added_at"},
    "image_file": {
        "id",
        "image_id",
        "rel_path",
        "sha256",
        "is_display",
        "orig_name",
        "width",
        "height",
        "missing",
        "added_at",
    },
    "platform": {"id", "name", "post_url", "user_url", "url_regex", "builtin", "file_regex"},
    "artist": {"id", "name", "note"},
    "account": {"id", "artist_id", "platform", "uid", "handle"},
    "tag": {"id", "ns", "name"},
    "image_tag": {"image_id", "tag_id"},
    "post": {"id", "platform", "post_id", "posted_at"},
    "image_source": {"id", "image_id", "post_id", "page", "status", "confirmed_at"},
    "source_evidence": {
        "id",
        "image_id",
        "file_id",
        "source_id",
        "platform",
        "post_id",
        "page",
        "input_kind",
        "input_text",
        "rule_key",
        "confidence",
        "evidence_key",
        "added_at",
    },
    "import_record": {"id", "batch_id", "file_id", "orig_name", "added_at"},
    "op_log": {"id", "batch_id", "kind", "payload", "at"},
}
# 每个版本记录其自身的必需结构；追加迁移时同时追加目标版本校验，不能改写基线。
REQUIRED_SCHEMAS: dict[int, dict[str, set[str]]] = {
    BASE_VERSION: _BASE_REQUIRED,
    6: {
        **_BASE_REQUIRED,
        "library_meta": {"key", "value"},
        "review_draft": {"image_id", "payload", "revision", "updated_at"},
        "source_evidence": _BASE_REQUIRED["source_evidence"] | {"dismissed"},
    },
}


class NotALibraryError(FileNotFoundError):
    pass


class LibraryFormatError(RuntimeError):
    pass


def connect(root: Path, *, readonly: bool = False) -> sqlite3.Connection:
    """仅连接已有文件，绝不因路径拼错创建空库；请求使用已经启动校验的库。"""
    path = (root / DB_NAME).resolve()
    if not path.is_file():
        raise NotALibraryError(f"不是图库（找不到 {DB_NAME}）：{root}")
    conn = sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _validate_format(conn: sqlite3.Connection) -> int:
    """仅识别本项目格式和支持版本，不用最新字段误拦升级入口。"""
    app_id = conn.execute("PRAGMA application_id").fetchone()[0]
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if app_id != APPLICATION_ID or version < BASE_VERSION:
        raise LibraryFormatError("无法识别的图库格式，不会清空或重建数据库")
    if version > SCHEMA_VERSION:
        raise LibraryFormatError(
            f"数据库版本 {version} 比程序支持的 {SCHEMA_VERSION} 新，请先升级程序"
        )
    return version


def _validate_schema(conn: sqlite3.Connection, version: int) -> None:
    required_schema = REQUIRED_SCHEMAS.get(version)
    if required_schema is None:
        raise LibraryFormatError(f"程序缺少图库版本 {version} 的结构校验，未执行升级")
    for table, required in required_schema.items():
        columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not required <= columns:
            raise LibraryFormatError(f"图库结构不完整（v{version} {table}），不会自动重建")
    if "library_meta" in required_schema:
        identity = conn.execute("SELECT value FROM library_meta WHERE key='id'").fetchone()
        if (
            identity is None
            or not isinstance(identity[0], str)
            or len(identity[0]) != 32
            or any(c not in "0123456789abcdef" for c in identity[0])
        ):
            raise LibraryFormatError("图库身份标识缺失或损坏，不会重新生成或写入")


def open_library(root: Path, *, readonly: bool = False) -> sqlite3.Connection:
    """先只读识别再写入；预演使用 readonly，不迁移或同步平台。"""
    probe = connect(root, readonly=True)
    try:
        version = _validate_format(probe)
        _validate_schema(probe, version)
        if readonly:
            if version != SCHEMA_VERSION:
                raise LibraryFormatError("图库需要升级，请先正常打开后再预演")
            return probe
    except BaseException:
        probe.close()
        raise
    probe.close()
    conn = connect(root)
    try:
        migrate(conn)
        sync_builtin_platforms(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def init_library(root: Path) -> Path:
    """只在空目录创建，已有文件／库／符号链接不覆盖。"""
    if root.is_symlink() or (root.exists() and (not root.is_dir() or any(root.iterdir()))):
        raise FileExistsError(f"目录非空，请选择新的空目录：{root}")
    root.mkdir(parents=True, exist_ok=True)
    path = root / DB_NAME
    with path.open("xb"):
        pass
    conn = None
    try:
        conn = connect(root)
        schema = resources.files(__package__).joinpath("schema.sql").read_text("utf-8")
        conn.executescript(
            f"BEGIN;\n{schema}\nPRAGMA application_id={APPLICATION_ID};\n"
            f"PRAGMA user_version={BASE_VERSION};\nCOMMIT;"
        )
        migrate(conn)
        sync_builtin_platforms(conn)
        for sub in ("images/_inbox", "images/archived", ".cache/thumbs"):
            (root / sub).mkdir(parents=True, exist_ok=True)
    except BaseException:
        if conn is not None:
            conn.close()
            conn = None
        path.unlink(missing_ok=True)  # 只清理本次独占创建的数据库，不触碰既有文件
        raise
    finally:
        if conn is not None:
            conn.close()
    return path


def migrate(conn: sqlite3.Connection) -> int:
    """按输入版本检查，再逐条升级；目标结构检查和版本号也在同一事务中。"""
    version = _validate_format(conn)
    _validate_schema(conn, version)
    # 缺少任何中间校验时在第一笔写入前失败，避免升级到一半才发现程序配置遗漏。
    for target in range(version + 1, SCHEMA_VERSION + 1):
        if target not in REQUIRED_SCHEMAS:
            raise LibraryFormatError(f"程序缺少图库版本 {target} 的结构校验，未执行升级")
    for i in range(version - BASE_VERSION, len(MIGRATIONS)):
        target = BASE_VERSION + i + 1
        try:
            conn.executescript(f"BEGIN;\n{MIGRATIONS[i]}\nPRAGMA user_version={target};")
            _validate_schema(conn, target)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
    return conn.execute("PRAGMA user_version").fetchone()[0]


def sync_builtin_platforms(conn: sqlite3.Connection) -> None:
    """同步内置定义，自定义资料不动；只在格式识别成功后调用。"""
    from artist_gallery.core.platforms import BUILTIN_PLATFORMS

    with conn:
        for p in BUILTIN_PLATFORMS:
            conn.execute(
                """
                INSERT INTO platform (id, name, post_url, user_url, url_regex, file_regex, builtin)
                VALUES (?, ?, ?, ?, ?, NULL, 1)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name, post_url=excluded.post_url,
                  user_url=excluded.user_url, url_regex=excluded.url_regex,
                  file_regex=NULL, builtin=1
                """,
                (p.id, p.name, p.post_url, p.user_url, p.url_regex),
            )
