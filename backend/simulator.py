# backend/simulator.py
#
# Stands in for the real ESP32-S3 firmware while it's still being developed.
# Publishes the same JSON shape the firmware will eventually send, at 5 Hz,
# to the Mosquitto broker. Run this in its own terminal:
#
#   python simulator.py
#
# Swapping this out for real hardware later just means pointing an ESP32-S3
# MQTT client at the same broker/topic with the same JSON shape -- nothing
# on the FastAPI or React side needs to change.

import json
import math
import random
import time

import paho.mqtt.client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1883
DEVICE_ID = "esp32_01"
TOPIC = f"aether/{DEVICE_ID}/sensor"
PUBLISH_HZ = 5
PERIOD_SEC = 1.0 / PUBLISH_HZ

AS7343_CHANNEL_COUNT = 14
AUDIO_SAMPLES = 128
AUDIO_BINS = 48


def noise(amount):
    return random.uniform(-amount, amount)


class Simulator:
    """Holds slowly-drifting internal state, same idea as the old JS hook."""

    def __init__(self):
        self.start_time = time.time()
        self.temp = 22.4
        self.humidity = 44.0
        self.pressure = 1013.2
        self.co2 = 620.0
        self.aqi = 2.0
        self.tvoc = 110.0
        self.lux = 340.0
        self.skin_temp = 33.6
        self.battery = 87.0
        self.rssi = -54
        self.audio_freq = 220.0
        self.audio_freq_target = 220.0
        self.audio_amp = 0.15
        self.audio_phase = 0.0
        self.motion_burst = 0.0
        self.flex_angle = 15.0
        self.spec_shape = [0.3 + 0.5 * math.sin(i) for i in range(AS7343_CHANNEL_COUNT)]

    def step(self):
        t = time.time()
        elapsed = t - self.start_time

        # Occasional motion burst, decays each tick (mirrors the IMU behavior
        # from the original browser-side simulator).
        if random.random() < 0.01:
            self.motion_burst = 1 + random.random() * 2.5
        self.motion_burst *= 0.85

        # Slow environmental drift.
        self.temp += (22.2 + math.sin(elapsed / 90) * 0.6 - self.temp) * 0.02 + noise(0.03)
        self.humidity += (44 + math.sin(elapsed / 70 + 1) * 3 - self.humidity) * 0.02 + noise(0.08)
        self.pressure += (1013 + math.sin(elapsed / 240) * 1.2 - self.pressure) * 0.01 + noise(0.02)
        self.co2 += (600 + max(0, math.sin(elapsed / 150)) * 260 - self.co2) * 0.015 + noise(3)
        self.aqi = max(1, min(5, self.aqi + (2 + math.sin(elapsed / 200) - self.aqi) * 0.03 + noise(0.05)))
        self.tvoc += (100 + max(0, math.sin(elapsed / 130)) * 180 - self.tvoc) * 0.02 + noise(2)
        eco2 = self.co2 * 1.02 + noise(4)
        self.lux = max(0, self.lux + (320 + math.sin(elapsed / 40) * 180 + math.sin(elapsed / 500) * 60 - self.lux) * 0.05 + noise(4))
        self.skin_temp += (33.5 + math.sin(elapsed / 300) * 0.3 + self.motion_burst * 0.05 - self.skin_temp) * 0.02 + noise(0.02)

        # IMU.
        ax = math.sin(elapsed * 1.3) * 0.05 + noise(0.4) * self.motion_burst
        ay = math.cos(elapsed * 1.1) * 0.05 + noise(0.4) * self.motion_burst
        az = 1 + math.sin(elapsed * 0.7) * 0.03 + noise(0.3) * self.motion_burst
        gx = noise(2) * (0.3 + self.motion_burst)
        gy = noise(2) * (0.3 + self.motion_burst)
        gz = noise(2) * (0.3 + self.motion_burst)
        motion_mag = math.sqrt(ax ** 2 + ay ** 2 + (az - 1) ** 2) * 9.81

        # Flex sensor placeholder (e.g. a knee-bend goniometer) -- standing in
        # until the real hardware/data shape from the flex sensor is wired in.
        # Slow walking-cadence bend cycle, plus a sharper kick during motion bursts.
        flex_target = 20 + max(0, math.sin(elapsed / 2.2)) * 70 + self.motion_burst * 15
        self.flex_angle += (flex_target - self.flex_angle) * 0.15 + noise(1.5)
        self.flex_angle = max(0, min(130, self.flex_angle))

        # Microphone: waveform + FFT-style magnitude spectrum with a moving peak.
        if random.random() < 0.02:
            self.audio_freq_target = 140 + random.random() * 2600
        self.audio_freq += (self.audio_freq_target - self.audio_freq) * 0.05
        self.audio_amp = max(0.03, self.audio_amp + (0.1 + random.random() * 0.25 - self.audio_amp) * 0.1)
        self.audio_phase += (self.audio_freq / 8000) * 2 * math.pi * PERIOD_SEC * 20

        waveform = []
        for i in range(AUDIO_SAMPLES):
            p = self.audio_phase + (i / AUDIO_SAMPLES) * 2 * math.pi * 6
            waveform.append(math.sin(p) * self.audio_amp + math.sin(p * 2.7) * self.audio_amp * 0.3 + noise(0.02))

        dominant_bin = round((self.audio_freq / 4000) * AUDIO_BINS)
        spectrum = []
        for i in range(AUDIO_BINS):
            dist = abs(i - dominant_bin)
            peak = math.exp(-(dist ** 2) / 6) * (0.6 + self.audio_amp * 2)
            harmonic_bin = (dominant_bin * 2) % AUDIO_BINS
            harmonic = math.exp(-((i - harmonic_bin) ** 2) / 4) * 0.25
            spectrum.append(max(0, peak + harmonic + random.random() * 0.05))

        rms = math.sqrt(sum(v * v for v in waveform) / len(waveform))
        peak_db = 20 * math.log10(max(0.001, max(abs(v) for v in waveform))) + 90

        # AS7343 spectral channels, correlated via a shared drifting shape.
        shape_shift = math.sin(elapsed / 20) * 0.15
        light_gain = self.lux / 400
        channels = []
        for i, base in enumerate(self.spec_shape):
            v = max(0, (base + shape_shift * math.sin(i)) * light_gain * 100 + noise(2))
            channels.append(v)
        dominant_idx = channels.index(max(channels))
        total_intensity = sum(channels) or 1
        # Approximate wavelength weighting for a plausible centroid value.
        wavelengths = [405, 425, 450, 475, 495, 515, 555, 550, 600, 640, 690, 745, 830, 850]
        centroid = sum(v * wavelengths[i] for i, v in enumerate(channels)) / total_intensity

        # Device housekeeping.
        self.battery = max(0, self.battery - 0.0006)
        self.rssi = round(self.rssi + (-54 + noise(6) - self.rssi) * 0.1)
        uptime_sec = int(elapsed)

        return {
            "device_id": DEVICE_ID,
            "ts": int(time.time() * 1000),
            "device": {
                "battery": round(self.battery, 1),
                "batteryVoltage": round(3.3 + (self.battery / 100) * 0.9, 2),
                "rssi": self.rssi,
                "uptimeSec": uptime_sec,
            },
            "live": {
                "bme280": {"temp": self.temp, "humidity": self.humidity, "pressure": self.pressure},
                "scd41": {"co2": self.co2},
                "ens160": {"aqi": self.aqi, "tvoc": self.tvoc, "eco2": eco2},
                "veml7700": {"lux": self.lux},
                "mlx90632": {"skinTemp": self.skin_temp},
                "lsm6ds3tr": {"ax": ax, "ay": ay, "az": az, "gx": gx, "gy": gy, "gz": gz, "motionMag": motion_mag},
                "flex": {"angle": self.flex_angle},
                "ics43434": {"rms": rms, "peakDb": peak_db, "dominantFreq": self.audio_freq},
                "as7343": {"channels": channels, "dominantIdx": dominant_idx, "centroid": centroid},
            },
            "audio": {"waveform": waveform, "spectrum": spectrum},
            "spectro": {"channels": channels},
        }


def main():
    client = mqtt.Client(client_id="aether-simulator")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()

    sim = Simulator()
    print(f"[simulator] publishing to {TOPIC} at {PUBLISH_HZ} Hz. Ctrl+C to stop.")

    try:
        while True:
            payload = sim.step()
            client.publish(TOPIC, json.dumps(payload), qos=0)
            time.sleep(PERIOD_SEC)
    except KeyboardInterrupt:
        print("\n[simulator] stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
