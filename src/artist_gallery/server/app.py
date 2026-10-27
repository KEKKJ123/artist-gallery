"""Starlette 应用工厂。

分层规则：所有业务逻辑在 core/，server/ 只做参数解析和调用。

两个设计要点：
- 处理器写成普通 `def`，Starlette 会放进线程池运行：生成缩略图是 CPU 活，
  写成 `async def` 会卡住整个服务。
- 每个请求自己开、自己关数据库连接：SQLite 连接不能跨线程共用。
  启动时只调用一次 `open_library()` 完成迁移，请求里用轻量的 `db.connect()`。
"""

from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from artist_gallery.core import db
from artist_gallery.server import api, media, pages

STATIC_DIR = Path(__file__).parent / "static"
LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]


def create_app(library_root: Path, *, allow_any_host: bool = False) -> Starlette:
    """创建应用。library_root 必须是已有图库（否则抛 NotALibraryError）。

    默认只接受 Host 为 localhost / 127.0.0.1 的请求：本地服务没有登录，
    这样可以挡住"别的网站借你的浏览器访问本地图库"（DNS rebinding）。
    局域网模式（--host 0.0.0.0）才设 allow_any_host=True。
    """
    library_root = Path(library_root).resolve()
    db.open_library(library_root).close()  # 迁移 + 同步内置平台，只做这一次

    routes = [
        Route("/api/inbox", api.api_inbox),
        Route("/api/navigation", api.api_navigation),
        Route("/api/archived", api.api_archived),
        Route("/api/platforms", api.api_platforms),
        Route("/api/{rest:path}", api.api_not_found),
        Route("/thumbs/{sha256}", media.serve_thumb),
        Route("/images/{rel_path:path}", media.serve_image),
        Mount("/assets", StaticFiles(directory=STATIC_DIR / "assets", check_dir=False)),
        Route("/{path:path}", pages.spa_fallback),
    ]
    middleware = [
        Middleware(TrustedHostMiddleware, allowed_hosts=["*"] if allow_any_host else LOCAL_HOSTS)
    ]
    app = Starlette(routes=routes, middleware=middleware)
    app.state.library_root = library_root
    app.state.static_dir = STATIC_DIR
    return app
