# backend/websocket_broadcast.py

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import List

# Router for WebSocket-endepunkt
api = APIRouter()

# Liste over aktive tilkoblinger
connected_websockets: List[WebSocket] = []

# === Koble til klient ===
async def connect_client(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)

# === Koble fra klient ===
async def disconnect_client(websocket: WebSocket):
    if websocket in connected_websockets:
        connected_websockets.remove(websocket)

# === Send melding til ALLE tilkoblede klienter ===
async def broadcast_message(message: str):
    disconnected = []
    for ws in connected_websockets:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        await disconnect_client(ws)

# === WebSocket-endepunkt ===
@api.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    await connect_client(websocket)
    try:
        while True:
            await websocket.receive_text()  # Kan eventuelt håndtere meldinger senere
    except WebSocketDisconnect:
        await disconnect_client(websocket)
