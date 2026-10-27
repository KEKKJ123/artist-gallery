"""原图与缩略图响应；保留独立的路径访问边界。"""

from starlette.requests import Request
from starlette.responses import FileResponse, Response

from artist_gallery.core.images import find_image_by_sha
from artist_gallery.core.thumbnail import get_or_create
from artist_gallery.server.context import connection, library_root


def serve_thumb(request: Request) -> Response:
    """GET /thumbs/{sha256} — 懒生成缩略图。无缩略图（视频、损坏文件）返回 204。"""
    sha256 = request.path_params["sha256"]
    with connection(request) as conn:
        rel_path = find_image_by_sha(conn, sha256)
    if rel_path is None:
        return Response(status_code=404)
    root = library_root(request)
    source = (root / rel_path).resolve()
    if not source.is_relative_to(root / "images"):
        return Response(status_code=403)
    dest = get_or_create(root, sha256, source)
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
    base = library_root(request) / "images"
    target = (base / request.path_params["rel_path"]).resolve()
    if not target.is_relative_to(base):  # 挡住 ../ 和指向外部的符号链接
        return Response(status_code=403)
    if not target.is_file():
        return Response(status_code=404)
    return FileResponse(target)
