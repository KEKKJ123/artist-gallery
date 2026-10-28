"""核查、草稿、归档与撤销接口；参数解析留在 Web，规则和事务在 core。"""

from __future__ import annotations

import sqlite3
from functools import wraps

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from artist_gallery.core import archiving, drafts, operations, review
from artist_gallery.server.context import connection, library_root


def endpoint(handler):
    @wraps(handler)
    def handle(request: Request) -> Response:
        try:
            with connection(request) as conn:
                if (
                    request.method not in {"GET", "HEAD"}
                    and request.url.path != "/api/review/parse"
                ):
                    if request.headers.get("x-gallery-library") != drafts.library_id(conn):
                        raise operations.ConflictError(
                            "服务对应的图库已改变，请重新读取；未向另一图库写入"
                        )
                result = handler(request, conn)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except operations.ConflictError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        except (operations.OperationError, TypeError, KeyError) as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except (OSError, sqlite3.Error) as e:
            return JSONResponse({"error": f"读写失败，未确认完成：{e}"}, status_code=409)

    return handle


def _id(request: Request) -> int:
    return int(request.path_params["image_id"])


@endpoint
def metadata(request: Request, conn: sqlite3.Connection) -> dict:
    return {"library_id": drafts.library_id(conn), "operations": operations.latest(conn)}


@endpoint
def image_detail(request: Request, conn: sqlite3.Connection) -> dict:
    return review.detail(conn, _id(request))


@endpoint
def file_size(request: Request, conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT id,rel_path,missing FROM image_file WHERE image_id=? AND is_display=1",
        (_id(request),),
    ).fetchone()
    if row is None:
        raise operations.OperationError("展示文件待设置，无法读取大小")
    if row["missing"]:
        raise operations.OperationError("展示文件已标记缺失，无法读取大小")
    path = archiving.media_path(library_root(request), row["rel_path"])
    return {"file_id": row["id"], "bytes": path.stat().st_size}


@endpoint
def get_draft(request: Request, conn: sqlite3.Connection) -> dict:
    return drafts.load(conn, _id(request))


@endpoint
def put_draft(request: Request, conn: sqlite3.Connection) -> dict:
    data = request.state.payload
    return drafts.save(conn, _id(request), data.get("payload"), data.get("revision"))


@endpoint
def parse(request: Request, conn: sqlite3.Connection) -> dict:
    return {"lines": review.parse_links(conn, request.state.payload.get("text", ""))}


@endpoint
def save_review(request: Request, conn: sqlite3.Connection) -> dict:
    data = request.state.payload
    return review.save(
        conn,
        data.get("ids"),
        data.get("revisions"),
        text=data.get("text", ""),
        edits=data.get("edits"),
        evidence_edits=data.get("evidence_edits"),
        confirm_scope=data.get("confirm_scope") is True,
    )


@endpoint
def archive_plan(request: Request, conn: sqlite3.Connection) -> dict:
    data = request.state.payload
    return archiving.preview(
        conn, library_root(request), data.get("ids"), force=data.get("force") is True
    )


@endpoint
def archive(request: Request, conn: sqlite3.Connection) -> dict:
    data = request.state.payload
    return archiving.archive(
        conn,
        library_root(request),
        data.get("ids"),
        data.get("token"),
        force=data.get("force") is True,
        confirmed=data.get("confirmed") is True,
    )


@endpoint
def undo(request: Request, conn: sqlite3.Connection) -> dict:
    value = request.state.payload.get("id")
    if type(value) is not int:
        raise operations.OperationError("撤销编号无效")
    return archiving.undo(conn, library_root(request), value)


@endpoint
def recover(request: Request, conn: sqlite3.Connection) -> dict:
    data = request.state.payload
    if type(data.get("id")) is not int:
        raise operations.OperationError("恢复编号无效")
    return archiving.recover(
        conn,
        library_root(request),
        data["id"],
        action=data.get("action"),
        confirmed=data.get("confirmed") is True,
    )
