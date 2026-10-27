"""只读列表 API，解析参数并调用 core。"""

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from artist_gallery.core import browse, inbox, platforms
from artist_gallery.server.context import connection, pagination


def api_inbox(request: Request) -> Response:
    try:
        offset, limit = pagination(request)
        hint_filter = inbox.normalize_hint_filter(request.query_params.get("filter"))
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    with connection(request) as conn:
        return JSONResponse(
            inbox.list_inbox(conn, offset=offset, limit=limit, hint_filter=hint_filter)
        )


def api_navigation(request: Request) -> Response:
    with connection(request) as conn:
        return JSONResponse(browse.navigation(conn))


def api_archived(request: Request) -> Response:
    try:
        offset, limit = pagination(request)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    with connection(request) as conn:
        return JSONResponse(browse.list_archived(conn, offset=offset, limit=limit))


def api_platforms(request: Request) -> Response:
    with connection(request) as conn:
        return JSONResponse(platforms.list_platforms(conn))


def api_not_found(request: Request) -> Response:
    return JSONResponse({"error": "接口不存在"}, status_code=404)
