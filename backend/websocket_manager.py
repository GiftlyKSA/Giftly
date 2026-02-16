from fastapi import WebSocket
from typing import Dict, Set


class ConnectionManager:
    def __init__(self):
        # user_id -> websocket
        self.active_connections: Dict[int, WebSocket] = {}
        # room -> set of user_ids
        self.rooms: Dict[str, Set[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        # Remove user from all rooms
        rooms_to_delete = []
        for room in self.rooms:
            self.rooms[room].discard(user_id)
            if not self.rooms[room]:
                rooms_to_delete.append(room)
        for room in rooms_to_delete:
            del self.rooms[room]

    async def join_room(self, user_id: int, room: str):
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(user_id)

    async def leave_room(self, user_id: int, room: str):
        if room in self.rooms:
            self.rooms[room].discard(user_id)
            if not self.rooms[room]:
                del self.rooms[room]

    async def broadcast_to_room(self, message: dict, room: str, exclude_user_id: int = None):
        if room in self.rooms:
            for user_id in self.rooms[room]:
                if user_id != exclude_user_id and user_id in self.active_connections:
                    try:
                        await self.active_connections[user_id].send_json(message)
                    except:
                        # Connection might be closed, remove it
                        del self.active_connections[user_id]
                        self.rooms[room].discard(user_id)

    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except:
                # Connection might be closed, remove it
                del self.active_connections[user_id]
                # Remove from rooms
                rooms_to_delete = []
                for room in self.rooms:
                    self.rooms[room].discard(user_id)
                    if not self.rooms[room]:
                        rooms_to_delete.append(room)
                for room in rooms_to_delete:
                    del self.rooms[room]


# Global instance
manager = ConnectionManager()