# backend/main.py
#
# Run with:  uvicorn main:app --reload --port 8000
#
# Data flow:
#   simulator.py (or real ESP32-S3 firmware later)
#     --publishes JSON-->  Mosquitto broker  (topic: aether/esp32_01/sensor)
#         --MQTTBridge subscribes-->  this FastAPI process
#             --stores latest snapshot, broadcasts--> every connected browser
#                 over ws://localhost:8000/ws/sensors

import asyncio
import time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import storage
from mqtt_bridge import MQTTBridge

app = FastAPI(title="Aether Lab Sensor Backend")

# Allow the Vite dev server to call this API / open a WebSocket to it. Vite
# auto-increments to :5174, :5175, etc. when :5173 is already taken (e.g. a
# second `npm run dev` left running), so allow any localhost port rather than
# hardcoding one -- a stray extra dev server should just work, not silently
# fail every REST call with a CORS error.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- shared in-memory state ----
# For a single wearable prototype, "the latest snapshot" is enough. If you
# add more devices later, key this dict by device_id instead of overwriting.
from typing import Optional

latest_snapshot: Optional[dict] = None
last_packet_time: Optional[float] = None
mqtt_connected = False

# Every currently-open browser WebSocket connection.
connected_clients: set[WebSocket] = set()

# Filled in on startup so the MQTT thread can safely schedule work
# on FastAPI's asyncio event loop.
main_event_loop: Optional[asyncio.AbstractEventLoop] = None


def handle_mqtt_message(payload: dict):
    """Called on the MQTT network thread whenever a sensor message arrives."""
    global latest_snapshot, last_packet_time
    latest_snapshot = payload
    last_packet_time = time.time()
    storage.insert_reading(payload)

    if main_event_loop is not None:
        asyncio.run_coroutine_threadsafe(broadcast(payload), main_event_loop)


def handle_mqtt_status(connected: bool):
    global mqtt_connected
    mqtt_connected = connected


async def broadcast(payload: dict):
    """Send a JSON payload to every connected browser."""
    dead_clients = []
    for ws in connected_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead_clients.append(ws)
    for ws in dead_clients:
        connected_clients.discard(ws)


mqtt_bridge = MQTTBridge(
    on_message_callback=handle_mqtt_message,
    on_status_change=handle_mqtt_status,
)


@app.on_event("startup")
async def on_startup():
    global main_event_loop
    main_event_loop = asyncio.get_event_loop()
    storage.init_db()
    mqtt_bridge.start()


@app.on_event("shutdown")
async def on_shutdown():
    mqtt_bridge.stop()


@app.get("/api/status")
async def get_status():
    """Simple REST snapshot of backend + broker + device health."""
    age_ms = None
    if last_packet_time is not None:
        age_ms = round((time.time() - last_packet_time) * 1000)

    return {
        "mqtt_connected": mqtt_connected,
        "connected_ws_clients": len(connected_clients),
        "last_packet_age_ms": age_ms,
        "latest_snapshot": latest_snapshot,
    }


@app.get("/api/history/range")
async def get_history_range():
    """Earliest/latest timestamps we have data for -- drives the "All" preset
    and keeps the UI from letting you zoom past available data."""
    return storage.get_range_bounds()


@app.get("/api/history")
async def get_history(start_ms: int, end_ms: int, max_points: int = 2000):
    """Row-oriented sensor history for a time range, one row per timestamp
    with every metric -- lets the frontend derive any sensor card's value
    at an arbitrary moment from a single dataset."""
    return {"points": storage.query_readings(start_ms, end_ms, max_points)}


class LabelIn(BaseModel):
    device_id: str = "esp32_01"
    start_ts_ms: int
    end_ts_ms: Optional[int] = None
    pain_level: int
    locations: List[str] = []
    quality: List[str] = []
    activity: Optional[str] = None
    onset: Optional[str] = None
    confidence: Optional[str] = None
    comment: Optional[str] = None


@app.post("/api/labels")
async def create_label(label: LabelIn):
    if not 0 <= label.pain_level <= 10:
        raise HTTPException(status_code=422, detail="pain_level must be between 0 and 10")
    return storage.insert_label(
        device_id=label.device_id,
        start_ts_ms=label.start_ts_ms,
        end_ts_ms=label.end_ts_ms,
        pain_level=label.pain_level,
        locations=label.locations,
        quality=label.quality,
        activity=label.activity,
        onset=label.onset,
        confidence=label.confidence,
        comment=label.comment,
    )


@app.get("/api/labels")
async def get_labels(start_ms: Optional[int] = None, end_ms: Optional[int] = None):
    return {"labels": storage.list_labels(start_ms, end_ms)}


@app.websocket("/ws/sensors")
async def ws_sensors(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    print(f"[ws] client connected, total={len(connected_clients)}")

    # Send whatever we already have immediately, so the UI isn't blank
    # while waiting for the next 5 Hz MQTT tick.
    if latest_snapshot is not None:
        await websocket.send_json(latest_snapshot)

    try:
        while True:
            # We don't expect the browser to send anything, but await
            # receive() so we notice immediately when it disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[ws] client disconnected, total={len(connected_clients)}")
