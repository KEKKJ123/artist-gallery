"""只读列表 API：解析 HTTP 参数后调用 core，不处理文件托管。"""

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from artist_gallery.core import browse, inbox, platforms
from artist_gallery.server.context import connection, pagination


def api_inbox(request: Request) -> Response:
    """GET /api/inbox?offset=0&limit=100&filter=all|hint|nohint"""
    try:
        offset, limit = pagination(request)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    try:
        hint_filter = inbox.normalize_hint_filter(request.query_params.get("filter"))
    except inbox.BadFilter as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    with connection(request) as conn:
        return JSONResponse(
            inbox.list_inbox(conn, offset=offset, limit=limit, hint_filter=hint_filter)
        )


def api_folders(request: Request) -> Response:
    """GET /api/folders — 左侧导航：收件箱张数、已归档总数、文件夹树。"""
    with connection(request) as conn:
        return JSONResponse(browse.list_folders(conn))


def api_folder_images(request: Request) -> Response:
    """GET /api/folder?path=pixiv&offset=0&limit=100 — 某文件夹（含子文件夹）里的图。

    path 为空表示"全部已归档"。用查询参数而不是路径参数：文件夹名可以含中文、空格、`%`，
    放进 URL 路径里要处理多层转义，放进查询参数由浏览器和 Starlette 统一编解码。
    """
    try:
        offset, limit = pagination(request)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    try:
        folder = browse.normalize_folder(request.query_params.get("path", ""))
    except browse.BadFolderPath as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    with connection(request) as conn:
        return JSONResponse(browse.list_folder_images(conn, folder, offset=offset, limit=limit))


def api_platforms(request: Request) -> Response:
    """GET /api/platforms"""
    with connection(request) as conn:
        return JSONResponse(platforms.list_platforms(conn))


def api_not_found(request: Request) -> Response:
    """未知的 /api/* 一律 404（不能落到前端页面上返回 200）。"""
    return JSONResponse({"error": "接口不存在"}, status_code=404)
