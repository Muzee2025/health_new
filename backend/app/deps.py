"""
认证相关依赖。

支持：
- `Authorization: Bearer <JWT>`（与前端登录一致）
- 或开发用请求头 `X-User-Id`（便于无 token 联调）
"""
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.utils.jwt_tokens import decode_access_token

security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)] = None,
    x_user_id: Annotated[Optional[int], Header(alias="X-User-Id")] = None,
) -> models.User:
    user_id: Optional[int] = None

    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
        try:
            payload = decode_access_token(token)
            sub = payload.get("sub")
            if sub is not None:
                user_id = int(sub)
        except (JWTError, ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效或过期的登录凭证",
            ) from None
    elif x_user_id is not None:
        user_id = x_user_id

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证：请登录（Bearer Token）或提供 X-User-Id",
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user


def require_roles(*roles: str):
    allowed = {r.lower() for r in roles}

    def checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role.lower() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前账号无权限访问该资源",
            )
        return current_user

    return checker
