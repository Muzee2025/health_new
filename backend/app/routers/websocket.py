import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.websocket_manager import manager
from app.utils.jwt_tokens import decode_access_token
from app.models import User

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_user_from_token(token: str, db: Session) -> User:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            return None
        # 兼容两种 token 形态：
        # 1) sub 为用户 ID（数字）
        # 2) sub 为用户名（当前登录接口默认）
        user = None
        try:
            user = db.query(User).filter(User.id == int(subject)).first()
        except (TypeError, ValueError):
            user = db.query(User).filter(User.username == str(subject)).first()
        return user
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        return None

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    user = await get_user_from_token(token, db)
    if not user:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user.id, user.role)
    try:
        while True:
            data = await websocket.receive_text()
            # 可以在这里处理前端发送的 ping
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id, user.role)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, user.id, user.role)
