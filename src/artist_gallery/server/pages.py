"""前端页面托管，与图库查询无关。"""

from starlette.requests import Request
from starlette.responses import FileResponse, Response


def spa_fallback(request: Request) -> Response:
    """其余路径返回前端页面（前端路由）。"""
    index = request.app.state.static_dir / "index.html"
    if not index.is_file():
        return Response("前端尚未构建（缺少 static/index.html）", status_code=500)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
