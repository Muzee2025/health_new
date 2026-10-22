"""Bound multipart request bytes before FastAPI/Starlette spools upload files."""
from starlette.responses import JSONResponse

UPLOAD_REQUEST_LIMIT = 6 * 1024 * 1024
UPLOAD_PATHS = frozenset({
    "/api/teacher/upload", "/api/teacher/avatar", "/api/advanced-ai/chat/upload",
})


class UploadBodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = UPLOAD_REQUEST_LIMIT):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        root = scope.get("root_path", "")
        if root and path.startswith(root + "/"):
            path = path[len(root):]
        if scope.get("type") != "http" or path.rstrip("/") not in UPLOAD_PATHS:
            await self.app(scope, receive, send)
            return

        async def reject():
            await JSONResponse({"detail": "Upload request must be at most 6 MiB"}, status_code=413)(scope, receive, send)

        # A header can reject early, but never grants an exemption from counting.
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        await reject()
                        return
                except ValueError:
                    pass

        messages = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                await reject()
                return
            messages.append(message)
            if not message.get("more_body", False):
                break

        # Only an accepted, bounded body reaches multipart parsing. Replaying the
        # original chunks avoids an additional full-body concatenation.
        iterator = iter(messages)

        async def replay():
            try:
                return next(iterator)
            except StopIteration:
                return await receive()

        await self.app(scope, replay, send)
