"""请求级资源与参数解析，不持有跨线程共享的数据库连接。"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from starlette.requests import Request

from artist_gallery.core import db


def library_root(request: Request) -> Path:
    """应用启动时已经校验过的图库根目录。"""
    return request.app.state.library_root


@contextmanager
def connection(request: Request) -> Iterator[sqlite3.Connection]:
    """每次请求自己开关连接，包括处理器抛出异常的情况。"""
    with closing(db.connect(library_root(request))) as conn:
        yield conn


def pagination(request: Request) -> tuple[int, int]:
    """解析分页参数；范围限制仍由 core 统一负责。"""
    try:
        return int(request.query_params.get("offset", 0)), int(
            request.query_params.get("limit", 100)
        )
    except ValueError as e:
        raise ValueError("offset 和 limit 必须是整数") from e
