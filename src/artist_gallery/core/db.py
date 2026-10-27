"""新格式初始化、只读预检与版本升级。旧开发库在写入前拒绝。"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

DB_NAME = "library.db"
APPLICATION_ID = 0x41475259  # AGRY；与旧格式的 application_id=0 区分
BASE_VERSION = 5  # 旧程序最多支持 4，不能把新库误认为旧 v1
MIGRATIONS: list[str] = []  # 第 i 条升级 BASE_VERSION+i → BASE_VERSION+i+1
SCHEMA_VERSION = BASE_VERSION + len(MIGRATIONS)
_REQUIRED = {
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


def _validate(conn: sqlite3.Connection) -> int:
    app_id = conn.execute("PRAGMA application_id").fetchone()[0]
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if app_id == 0 and 1 <= version <= 4:
        raise LibraryFormatError("不支持旧开发库；请在新目录建库并重新导入，原库未修改")
    if app_id != APPLICATION_ID or version < BASE_VERSION:
        raise LibraryFormatError("无法识别的图库格式，不会清空或重建数据库")
    if version > SCHEMA_VERSION:
        raise LibraryFormatError(
            f"数据库版本 {version} 比程序支持的 {SCHEMA_VERSION} 新，请先升级程序"
        )
    for table, required in _REQUIRED.items():
        columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not required <= columns:
            raise LibraryFormatError(f"图库结构不完整（{table}），不会自动重建")
    return version


def open_library(root: Path, *, readonly: bool = False) -> sqlite3.Connection:
    """先只读识别再写入；预演使用 readonly，不迁移或同步平台。"""
    probe = connect(root, readonly=True)
    try:
        version = _validate(probe)
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
    """新格式后续升级；每一条及其版本号是同一事务，不存在旧库升级桥。"""
    version = _validate(conn)
    for i in range(version - BASE_VERSION, len(MIGRATIONS)):
        try:
            conn.executescript(
                f"BEGIN;\n{MIGRATIONS[i]}\nPRAGMA user_version={BASE_VERSION + i + 1};\nCOMMIT;"
            )
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
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
