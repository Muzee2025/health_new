from fastapi import HTTPException, Request

from .. import models


def check_teacher_role(user: models.User):
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")
    return user


def _build_avatar_url(request: Request | None, relative_path: str) -> str:
    clean = (relative_path or "").replace("\\", "/").strip("/")
    static_path = f"/static/{clean}"
    if request is None:
        return f"http://127.0.0.1:8000{static_path}"
    return str(request.base_url).rstrip("/") + static_path
