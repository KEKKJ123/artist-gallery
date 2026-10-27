"""Starlette 应用工厂。

分层规则：所有业务逻辑在 core/，server/ 只做参数解析和调用。

两个设计要点：
- 处理器写成普通 `def`，Starlette 会放进线程池运行：生成缩略图是 CPU 活，
  写成 `async def` 会卡住整个服务。
- 每个请求自己开、自己关数据库连接：SQLite 连接不能跨线程共用。
  启动时只调用一次 `open_library()` 完成迁移，请求里用轻量的 `db.connect()`。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from artist_gallery.core import browse, db, inbox
from artist_gallery.core.thumbnail import get_or_create

STATIC_DIR = Path(__file__).parent / "static"
LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]


@contextmanager
def _conn(request: Request) -> Iterator[sqlite3.Connection]:
    with closing(db.connect(request.app.state.library_root)) as conn:
        yield conn


def _root(request: Request) -> Path:
    return request.app.state.library_root


def api_inbox(request: Request) -> Response:
    """GET /api/inbox?offset=0&limit=100"""
    try:
        offset = int(request.query_params.get("offset", 0))
        limit = int(request.query_params.get("limit", 100))
    except ValueError:
        return JSONResponse({"error": "offset 和 limit 必须是整数"}, status_code=400)
    with _conn(request) as conn:
        return JSONResponse(inbox.list_inbox(conn, offset=offset, limit=limit))


def api_folders(request: Request) -> Response:
    """GET /api/folders — 左侧导航：收件箱张数、已归档总数、文件夹树。"""
    with _conn(request) as conn:
        return JSONResponse(browse.list_folders(conn))


def api_folder_images(request: Request) -> Response:
    """GET /api/folder?path=pixiv&offset=0&limit=100 — 某文件夹（含子文件夹）里的图。

    path 为空表示"全部已归档"。用查询参数而不是路径参数：文件夹名可以含中文、空格、`%`，
    放进 URL 路径里要处理多层转义，放进查询参数由浏览器和 Starlette 统一编解码。
    """
    try:
        offset = int(request.query_params.get("offset", 0))
        limit = int(request.query_params.get("limit", 100))
    except ValueError:
        return JSONResponse({"error": "offset 和 limit 必须是整数"}, status_code=400)
    try:
        folder = browse.normalize_folder(request.query_params.get("path", ""))
    except browse.BadFolderPath as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    with _conn(request) as conn:
        return JSONResponse(browse.list_folder_images(conn, folder, offset=offset, limit=limit))


def api_platforms(request: Request) -> Response:
    """GET /api/platforms"""
    with _conn(request) as conn:
        return JSONResponse(inbox.list_platforms(conn))


def api_not_found(request: Request) -> Response:
    """未知的 /api/* 一律 404（不能落到前端页面上返回 200）。"""
    return JSONResponse({"error": "接口不存在"}, status_code=404)


def serve_thumb(request: Request) -> Response:
    """GET /thumbs/{sha256} — 懒生成缩略图。无缩略图（视频、损坏文件）返回 204。"""
    sha256 = request.path_params["sha256"]
    with _conn(request) as conn:
        rel_path = inbox.find_image_by_sha(conn, sha256)
    if rel_path is None:
        return Response(status_code=404)
    root = _root(request)
    dest = get_or_create(root, sha256, root / rel_path)
    if dest is None:
        return Response(status_code=204)
    # 缩略图按内容哈希命名，内容永不改变，可以放心长期缓存
    return FileResponse(
        dest,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


def serve_image(request: Request) -> Response:
    """GET /images/{rel_path} — 原图。只允许访问图库的 images/ 目录。"""
    base = (_root(request) / "images").resolve()
    target = (base / request.path_params["rel_path"]).resolve()
    if not target.is_relative_to(base):  # 挡住 ../ 和指向外部的符号链接
        return Response(status_code=403)
    if not target.is_file():
        return Response(status_code=404)
    return FileResponse(target)


def spa_fallback(request: Request) -> Response:
    """其余路径返回前端页面（前端路由）。"""
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        return Response("前端尚未构建（缺少 static/index.html）", status_code=500)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app(library_root: Path, *, allow_any_host: bool = False) -> Starlette:
    """创建应用。library_root 必须是已有图库（否则抛 NotALibraryError）。

    默认只接受 Host 为 localhost / 127.0.0.1 的请求：本地服务没有登录，
    这样可以挡住"别的网站借你的浏览器访问本地图库"（DNS rebinding）。
    局域网模式（--host 0.0.0.0）才设 allow_any_host=True。
    """
    library_root = Path(library_root).resolve()
    db.open_library(library_root).close()  # 迁移 + 同步内置平台，只做这一次

    routes = [
        Route("/api/inbox", api_inbox),
        Route("/api/folders", api_folders),
        Route("/api/folder", api_folder_images),
        Route("/api/platforms", api_platforms),
        Route("/api/{rest:path}", api_not_found),
        Route("/thumbs/{sha256}", serve_thumb),
        Route("/images/{rel_path:path}", serve_image),
        Mount("/assets", StaticFiles(directory=STATIC_DIR / "assets", check_dir=False)),
        Route("/{path:path}", spa_fallback),
    ]
    middleware = [
        Middleware(TrustedHostMiddleware, allowed_hosts=["*"] if allow_any_host else LOCAL_HOSTS)
    ]
    app = Starlette(routes=routes, middleware=middleware)
    app.state.library_root = library_root
    return app
