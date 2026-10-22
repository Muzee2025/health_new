import logging
import json
import asyncio
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.websocket_manager import manager
from app.security import resolve_access_user, decode_access_token, cors_origins
from app.models import User

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_user_from_token(token: str, db: Session) -> User:
    try:
        return resolve_access_user(token, db)
    except Exception:
        logger.warning("WebSocket authentication rejected")
        return None

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    # Browser WebSocket cannot set Authorization. Keep credentials out of URLs
    # and access logs; echo only the fixed protocol marker, never the JWT.
    protocols = [item.strip() for item in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    origin = websocket.headers.get("origin")
    if ("token" in websocket.query_params or len(protocols) != 2
            or protocols[0] != "access_token" or not protocols[1] or len(protocols[1]) > 4096
            or (origin is not None and origin not in cors_origins())):
        await websocket.close(code=1008)
        return
    token = protocols[1]
    user = await get_user_from_token(token, db)
    if not user:
        await websocket.close(code=1008)
        return

    expires_at = decode_access_token(token)["exp"]
    await manager.connect(websocket, user.id, user.role, subprotocol="access_token")
    try:
        while True:
            remaining = expires_at - time.time()
            if remaining <= 0:
                await websocket.close(code=1008)
                break
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=remaining)
            except asyncio.TimeoutError:
                await websocket.close(code=1008)
                break
            # 可以在这里处理前端发送的 ping
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id, user.role)
    except Exception as e:
        logger.error("WebSocket receive failed error_type=%s", type(e).__name__)
    finally:
        manager.disconnect(websocket, user.id, user.role)
