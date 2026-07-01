from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import paho.mqtt.client as mqtt
import json
import time
import asyncio

app = FastAPI()

latest_status = {
    "message": "No MQTT status received yet"
}

connected_websockets = []

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/status"


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


@app.get("/")
def root():
    return {"status": "FastAPI MQTT WebSocket backend running"}


@app.get("/status")
def get_status():
    return latest_status


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