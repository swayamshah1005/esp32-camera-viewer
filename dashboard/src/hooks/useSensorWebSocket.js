// src/hooks/useSensorWebSocket.js
//
// Drop-in replacement for useSensorSimulator.js. Same call signature
// (`useSensorWebSocket({ onEvent })`), same returned snapshot shape
// ({ device, live, history, audio, spectro }), so App.jsx only needs to
// change which hook it imports/calls -- no component below it changes.
//
// Where useSensorSimulator.js invented values locally, this hook instead:
//   - opens a WebSocket to the FastAPI backend at /ws/sensors
//   - on every message, updates the "live" instantaneous readings directly
//   - builds the same rolling history / waterfall buffers the old hook
//     built, but driven by real incoming packets instead of a local timer
//   - polls REST /api/status every few seconds for broker health, since
//     that's not part of every single WebSocket packet

import { useEffect, useRef, useState } from 'react';
import { AS7343_CHANNELS, ROLLING_WINDOW_SECONDS } from '../data/sensorConfig';

const WS_URL = 'ws://localhost:8000/ws/sensors';
const STATUS_URL = 'http://localhost:8000/api/status';

const HISTORY_PUSH_INTERVAL_MS = 1000; // ~1 Hz, matches the old hook's rolling-chart cadence
const MAX_SLOW_POINTS = Math.ceil((ROLLING_WINDOW_SECONDS * 1000) / HISTORY_PUSH_INTERVAL_MS) + 2;
const WATERFALL_FRAMES = 32;
const RECONNECT_DELAY_MS = 2000;
const STATUS_POLL_MS = 5000;

function pushCapped(arr, point, cap) {
  const next = [...arr, point];
  if (next.length > cap) next.shift();
  return next;
}

// Real hardware comes online one sensor at a time (e.g. just BME280 today),
// so an incoming packet's `live` object won't necessarily have every sensor
// key the simulator always sent. Merge per-sensor onto the previous snapshot
// (which starts from buildInitialSnapshot's full default shape) instead of
// replacing `live` wholesale, so a sensor key that's simply absent from a
// packet doesn't turn into `undefined` and crash every `live.x.y` read below.
function mergeLive(prevLive, incomingLive = {}) {
  const merged = { ...prevLive };
  for (const key of Object.keys(prevLive)) {
    if (incomingLive[key]) {
      merged[key] = { ...prevLive[key], ...incomingLive[key] };
    }
  }
  return merged;
}

function makeEmptyHistory() {
  return {
    temp: [], humidity: [], pressure: [], co2: [], aqi: [], tvoc: [], lux: [],
    skinTemp: [], accelX: [], accelY: [], accelZ: [], gyroX: [], gyroY: [], gyroZ: [], motionMag: [],
    flexAngle: [],
  };
}

function buildInitialSnapshot() {
  const channels = AS7343_CHANNELS.map(() => 0);
  return {
    device: {
      online: false, mqttConnected: false, wsConnected: false,
      rssi: null, battery: null, batteryVoltage: null, uptimeSec: 0, lastPacketAgeMs: null,
    },
    live: {
      bme280: { temp: null, humidity: null, pressure: null },
      scd41: { co2: null },
      ens160: { aqi: null, tvoc: null, eco2: null },
      veml7700: { lux: null },
      mlx90632: { skinTemp: null },
      lsm6ds3tr: { ax: 0, ay: 0, az: 1, gx: 0, gy: 0, gz: 0, motionMag: 0 },
      flex: { angle: null },
      ics43434: { rms: 0, peakDb: -90, dominantFreq: 0 },
      as7343: { dominantChannel: null, dominantNm: null, clear: null, channels: {} },
    },
    history: makeEmptyHistory(),
    audio: { waveform: new Array(128).fill(0), spectrum: new Array(48).fill(0), waterfall: [], rms: 0, peakDb: -90, dominantFreq: 0 },
    spectro: { channels, waterfall: [], dominantIdx: -1, dominantNm: null, clear: null },
  };
}

export function useSensorWebSocket({ onEvent } = {}) {
  const [snapshot, setSnapshot] = useState(buildInitialSnapshot);

  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const lastHistoryPushRef = useRef(0);
  const lastMessageTimeRef = useRef(null);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const everConnectedRef = useRef(false);

  useEffect(() => {
    const emit = (sev, msg) => onEventRef.current && onEventRef.current(sev, msg);
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        emit('success', everConnectedRef.current ? 'WebSocket reconnected' : 'WebSocket link established');
        everConnectedRef.current = true;
        setSnapshot((prev) => ({ ...prev, device: { ...prev.device, online: true, wsConnected: true } }));
      };

      ws.onmessage = (event) => {
        let payload;
        try {
          payload = JSON.parse(event.data);
        } catch (err) {
          console.error('[useSensorWebSocket] bad JSON from server:', err);
          return;
        }
        handlePacket(payload);
      };

      ws.onerror = () => {
        // onclose fires right after, which handles reconnect + event logging.
      };

      ws.onclose = () => {
        setSnapshot((prev) => ({
          ...prev,
          device: { ...prev.device, online: false, wsConnected: false },
        }));
        if (!cancelled) {
          emit('warning', 'WebSocket disconnected, retrying...');
          reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };
    }

    function handlePacket(payload) {
      const now = Date.now();
      lastMessageTimeRef.current = now;
      const { device = {}, live: incomingLive, audio, spectro } = payload;
      if (!incomingLive) return; // ignore anything that isn't a sensor snapshot

      const pushHistory = now - lastHistoryPushRef.current >= HISTORY_PUSH_INTERVAL_MS;
      if (pushHistory) lastHistoryPushRef.current = now;

      setSnapshot((prev) => {
        const live = mergeLive(prev.live, incomingLive);

        const motionMag = live.lsm6ds3tr
          ? Math.sqrt(
              live.lsm6ds3tr.ax ** 2 + live.lsm6ds3tr.ay ** 2 + (live.lsm6ds3tr.az - 1) ** 2
            ) * 9.81
          : 0;

        const history = pushHistory
          ? {
              temp: pushCapped(prev.history.temp, { t: now, v: live.bme280.temp }, MAX_SLOW_POINTS),
              humidity: pushCapped(prev.history.humidity, { t: now, v: live.bme280.humidity }, MAX_SLOW_POINTS),
              pressure: pushCapped(prev.history.pressure, { t: now, v: live.bme280.pressure }, MAX_SLOW_POINTS),
              co2: pushCapped(prev.history.co2, { t: now, v: live.scd41.co2 }, MAX_SLOW_POINTS),
              aqi: pushCapped(prev.history.aqi, { t: now, v: live.ens160.aqi }, MAX_SLOW_POINTS),
              tvoc: pushCapped(prev.history.tvoc, { t: now, v: live.ens160.tvoc }, MAX_SLOW_POINTS),
              lux: pushCapped(prev.history.lux, { t: now, v: live.veml7700.lux }, MAX_SLOW_POINTS),
              skinTemp: pushCapped(prev.history.skinTemp, { t: now, v: live.mlx90632.skinTemp }, MAX_SLOW_POINTS),
              accelX: pushCapped(prev.history.accelX, { t: now, v: live.lsm6ds3tr.ax }, MAX_SLOW_POINTS),
              accelY: pushCapped(prev.history.accelY, { t: now, v: live.lsm6ds3tr.ay }, MAX_SLOW_POINTS),
              accelZ: pushCapped(prev.history.accelZ, { t: now, v: live.lsm6ds3tr.az }, MAX_SLOW_POINTS),
              gyroX: pushCapped(prev.history.gyroX, { t: now, v: live.lsm6ds3tr.gx }, MAX_SLOW_POINTS),
              gyroY: pushCapped(prev.history.gyroY, { t: now, v: live.lsm6ds3tr.gy }, MAX_SLOW_POINTS),
              gyroZ: pushCapped(prev.history.gyroZ, { t: now, v: live.lsm6ds3tr.gz }, MAX_SLOW_POINTS),
              motionMag: pushCapped(prev.history.motionMag, { t: now, v: motionMag }, MAX_SLOW_POINTS),
              flexAngle: pushCapped(prev.history.flexAngle, { t: now, v: live.flex?.angle }, MAX_SLOW_POINTS),
            }
          : prev.history;

        const spectrum = audio?.spectrum || prev.audio.spectrum;
        // Firmware publishes as7343 channels as a named object ({F1: .., F2: ..}),
        // not an array -- reorder into AS7343_CHANNELS' canonical (wavelength-
        // ascending) order so every waterfall frame lines up the same way.
        const channels = live.as7343?.channels
          ? AS7343_CHANNELS.map((c) => live.as7343.channels[c.id] ?? 0)
          : (spectro?.channels || prev.spectro.channels);

        const audioWaterfall = audio?.spectrum
          ? pushCapped(prev.audio.waterfall, audio.spectrum, WATERFALL_FRAMES)
          : prev.audio.waterfall;
        const spectroWaterfall = channels
          ? pushCapped(prev.spectro.waterfall, channels, WATERFALL_FRAMES)
          : prev.spectro.waterfall;

        return {
          device: {
            ...prev.device,
            online: true,
            wsConnected: true,
            rssi: device.rssi ?? prev.device.rssi,
            battery: device.battery ?? prev.device.battery,
            batteryVoltage: device.batteryVoltage ?? prev.device.batteryVoltage,
            uptimeSec: device.uptimeSec ?? prev.device.uptimeSec,
            lastPacketAgeMs: 0,
          },
          live,
          history,
          audio: {
            waveform: audio?.waveform || prev.audio.waveform,
            spectrum,
            waterfall: audioWaterfall,
            rms: live.ics43434?.rms ?? prev.audio.rms,
            peakDb: live.ics43434?.peakDb ?? prev.audio.peakDb,
            dominantFreq: live.ics43434?.dominantFreq ?? prev.audio.dominantFreq,
          },
          spectro: {
            channels,
            waterfall: spectroWaterfall,
            dominantIdx: live.as7343?.dominantChannel
              ? AS7343_CHANNELS.findIndex((c) => c.id === live.as7343.dominantChannel)
              : prev.spectro.dominantIdx,
            dominantNm: live.as7343?.dominantNm ?? prev.spectro.dominantNm,
            clear: live.as7343?.clear ?? prev.spectro.clear,
          },
        };
      });
    }

    connect();

    // Keep the "packet age" ticking even between messages, and periodically
    // check REST /api/status for broker connectivity (not carried on every
    // WebSocket packet).
    const ageTimer = setInterval(() => {
      if (lastMessageTimeRef.current === null) return;
      setSnapshot((prev) => ({
        ...prev,
        device: { ...prev.device, lastPacketAgeMs: Date.now() - lastMessageTimeRef.current },
      }));
    }, 1000);

    const pollStatus = async () => {
      try {
        const res = await fetch(STATUS_URL);
        const data = await res.json();
        setSnapshot((prev) => ({
          ...prev,
          device: { ...prev.device, mqttConnected: !!data.mqtt_connected },
        }));
      } catch {
        setSnapshot((prev) => ({ ...prev, device: { ...prev.device, mqttConnected: false } }));
      }
    };
    pollStatus(); // don't wait a full STATUS_POLL_MS for the first check on page load
    const statusTimer = setInterval(pollStatus, STATUS_POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(ageTimer);
      clearInterval(statusTimer);
      clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return snapshot;
}