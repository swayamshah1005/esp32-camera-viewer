# backend/mqtt_bridge.py
#
# Small wrapper around paho-mqtt. Its only job is:
#   1. Connect to the Mosquitto broker
#   2. Subscribe to aether/+/sensor  (the "+" matches any device id)
#   3. Parse each incoming message as JSON
#   4. Hand the parsed dict to whatever callback main.py gave it
#
# paho-mqtt runs its own background network thread (started by loop_start()),
# so on_message fires on a *different* thread than FastAPI's asyncio event
# loop. We can't directly call `await websocket.send(...)` from that thread,
# so we hand data off using asyncio.run_coroutine_threadsafe.

import json
import threading
import paho.mqtt.client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "aether/+/sensor"  # + wildcard matches any device id, e.g. aether/esp32_01/sensor


class MQTTBridge:
    def __init__(self, on_message_callback, on_status_change=None):
        """
        on_message_callback(payload: dict) -> called for every valid JSON
            message received on the sensor topic.
        on_status_change(connected: bool) -> called whenever the broker
            connection goes up or down (optional).
        """
        self._on_message_callback = on_message_callback
        self._on_status_change = on_status_change
        self.connected = False

        self.client = mqtt.Client(client_id="aether-fastapi-backend")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self):
        """Connect and start the background network thread. Non-blocking."""
        self.client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    # ---- paho-mqtt callbacks (run on the paho network thread) ----

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"[mqtt] connected to {MQTT_HOST}:{MQTT_PORT}")
            client.subscribe(MQTT_TOPIC)
            print(f"[mqtt] subscribed to {MQTT_TOPIC}")
        else:
            self.connected = False
            print(f"[mqtt] connect failed, rc={rc}")
        if self._on_status_change:
            self._on_status_change(self.connected)

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        print(f"[mqtt] disconnected (rc={rc})")
        if self._on_status_change:
            self._on_status_change(False)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"[mqtt] ignoring malformed message on {msg.topic}: {exc}")
            return

        # topic looks like: aether/esp32_01/sensor
        parts = msg.topic.split("/")
        device_id = parts[1] if len(parts) > 1 else "unknown"
        payload.setdefault("device_id", device_id)

        self._on_message_callback(payload)
