"""写接口边界：同源、自定义头、JSON 和长度限制；不从网页文本推断授权。"""

import json

from starlette.responses import JSONResponse

MAX_BODY = 1024 * 1024


class WriteGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, send)
        headers = {k.decode("latin1"): v.decode("latin1") for k, v in scope["headers"]}
        origin = headers.get("origin")
        same_origin = not origin or origin == f"{scope['scheme']}://{headers.get('host', '')}"
        if not same_origin or headers.get("x-artist-gallery") != "1":
            return await JSONResponse(
                {"error": "写操作只接受本图库页面的同源请求"}, status_code=403
            )(scope, receive, send)
        if headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            return await JSONResponse({"error": "写操作需要 JSON"}, status_code=415)(
                scope, receive, send
            )
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY:
                return await JSONResponse({"error": "请求内容过长"}, status_code=413)(
                    scope, receive, send
                )
            if not message.get("more_body"):
                break
        try:

            def invalid_constant(value: str) -> None:
                raise ValueError("JSON 不接受 NaN 或 Infinity")

            payload = json.loads(body, parse_constant=invalid_constant)
            if not isinstance(payload, dict):
                raise ValueError
        except (ValueError, UnicodeError):
            return await JSONResponse({"error": "JSON 格式无效"}, status_code=400)(
                scope, receive, send
            )
        scope.setdefault("state", {})["payload"] = payload
        await self.app(scope, receive, send)
