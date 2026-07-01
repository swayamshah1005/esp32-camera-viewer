from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import paho.mqtt.client as mqtt
import json
import time
import os
import asyncio

app = FastAPI()

LATEST_IMAGE = "latest.jpg"
server_start_time = time.time()
last_upload_time = None
frame_count = 0

latest_status = {"message": "No MQTT status received yet"}
connected_websockets = []

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/status"


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h1>FastAPI Backend Running</h1>
    <p>Image: <a href="/latest">/latest</a></p>
    <p>Status: <a href="/status">/status</a></p>
    """


@app.post("/upload")
async def upload(request: Request):
    global last_upload_time, frame_count

    body = await request.body()

    with open(LATEST_IMAGE, "wb") as f:
        f.write(body)

    frame_count += 1
    last_upload_time = time.strftime("%Y-%m-%d %H:%M:%S")

    return {"status": "ok"}


@app.get("/latest")
def latest():
    if not os.path.exists(LATEST_IMAGE):
        return JSONResponse({"error": "No image uploaded yet"}, status_code=404)

    return FileResponse(LATEST_IMAGE, media_type="image/jpeg")


@app.get("/status")
def status():
    image_online = False

    if os.path.exists(LATEST_IMAGE):
        image_online = time.time() - os.path.getmtime(LATEST_IMAGE) < 5

    return {
        "image_status": {
            "frame_count": frame_count,
            "last_upload_time": last_upload_time,
            "online": image_online,
        },
        "mqtt_status": latest_status,
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server_uptime_seconds": int(time.time() - server_start_time),
    }


async def broadcast_status():
    disconnected = []

    for websocket in connected_websockets:
        try:
            await websocket.send_json(latest_status)
        except Exception:
            disconnected.append(websocket)

    for websocket in disconnected:
        connected_websockets.remove(websocket)


def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with code:", rc)
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    global latest_status

    payload = msg.payload.decode()
    print("MQTT received:", payload)

    try:
        latest_status = json.loads(payload)
        latest_status["received_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        latest_status = {
            "raw": payload,
            "received_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(broadcast_status())
    loop.close()


mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


@app.on_event("startup")
def startup_event():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)

    try:
        await websocket.send_json(latest_status)

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        connected_websockets.remove(websocket)