import json
from typing import Dict, List, Any
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # {user_id: [websocket1, websocket2, ...]}
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # teacher websockets (user_id -> websockets)
        self.teacher_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, role: str):
        await websocket.accept()
        if role == "teacher":
            if user_id not in self.teacher_connections:
                self.teacher_connections[user_id] = []
            self.teacher_connections[user_id].append(websocket)
        else:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int, role: str):
        if role == "teacher":
            if user_id in self.teacher_connections and websocket in self.teacher_connections[user_id]:
                self.teacher_connections[user_id].remove(websocket)
                if not self.teacher_connections[user_id]:
                    del self.teacher_connections[user_id]
        else:
            if user_id in self.active_connections and websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: int, role: str):
        msg_str = json.dumps(message, ensure_ascii=False)
        connections = self.teacher_connections.get(user_id, []) if role == "teacher" else self.active_connections.get(user_id, [])
        for connection in connections:
            try:
                await connection.send_text(msg_str)
            except Exception:
                pass

    async def broadcast_to_teachers(self, message: dict):
        msg_str = json.dumps(message, ensure_ascii=False)
        for user_id, connections in self.teacher_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(msg_str)
                except Exception:
                    pass

manager = ConnectionManager()
