# backend/storage.py
#
# Thin sqlite3 wrapper -- the persistence layer the live dashboard never had.
# Every incoming MQTT packet gets a row in `readings`, and every saved pain
# annotation gets a row in `labels`. No ORM, to match the project's
# minimal-dependency style (see requirements.txt).
#
# Writes happen on the paho-mqtt network thread (see mqtt_bridge.py), reads
# happen on FastAPI's asyncio thread -- both go through one connection guarded
# by a lock, since sqlite3 connections aren't safe to share across threads
# without `check_same_thread=False` + external serialization.

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "sensor_data.db"

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

READING_COLUMNS = [
    "temp", "humidity", "pressure", "co2", "aqi", "tvoc", "eco2", "lux", "skin_temp",
    "accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z", "motion_mag", "flex_angle",
]


def init_db(path: Path = DB_PATH):
    global _conn
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    columns_sql = ",\n            ".join(f"{col} REAL" for col in READING_COLUMNS)
    _conn.execute(f"""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            ts_ms INTEGER NOT NULL,
            {columns_sql}
        )
    """)
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts_ms)")
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            start_ts_ms INTEGER NOT NULL,
            end_ts_ms INTEGER,
            pain_level INTEGER NOT NULL,
            locations_json TEXT,
            quality_json TEXT,
            activity TEXT,
            onset TEXT,
            confidence TEXT,
            comment TEXT,
            created_at_ms INTEGER NOT NULL
        )
    """)
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_labels_start ON labels(start_ts_ms)")
    _conn.commit()


def _get(d: dict, *path):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def insert_reading(payload: dict):
    """Extract the scalar fields we chart from a raw MQTT sensor payload and store them."""
    live = payload.get("live") or {}
    values = {
        "temp": _get(live, "bme280", "temp"),
        "humidity": _get(live, "bme280", "humidity"),
        "pressure": _get(live, "bme280", "pressure"),
        "co2": _get(live, "scd41", "co2"),
        "aqi": _get(live, "ens160", "aqi"),
        "tvoc": _get(live, "ens160", "tvoc"),
        "eco2": _get(live, "ens160", "eco2"),
        "lux": _get(live, "veml7700", "lux"),
        "skin_temp": _get(live, "mlx90632", "skinTemp"),
        "accel_x": _get(live, "lsm6ds3tr", "ax"),
        "accel_y": _get(live, "lsm6ds3tr", "ay"),
        "accel_z": _get(live, "lsm6ds3tr", "az"),
        "gyro_x": _get(live, "lsm6ds3tr", "gx"),
        "gyro_y": _get(live, "lsm6ds3tr", "gy"),
        "gyro_z": _get(live, "lsm6ds3tr", "gz"),
        "motion_mag": _get(live, "lsm6ds3tr", "motionMag"),
        "flex_angle": _get(live, "flex", "angle"),
    }
    ts_ms = payload.get("ts") or int(time.time() * 1000)
    device_id = payload.get("device_id", "unknown")

    cols = ", ".join(["device_id", "ts_ms"] + READING_COLUMNS)
    placeholders = ", ".join(["?"] * (2 + len(READING_COLUMNS)))
    row = [device_id, ts_ms] + [values[c] for c in READING_COLUMNS]

    with _lock:
        _conn.execute(f"INSERT INTO readings ({cols}) VALUES ({placeholders})", row)
        _conn.commit()


def query_readings(start_ms: int, end_ms: int, max_points: int = 2000):
    """Row-oriented history for a time range, stride-downsampled to max_points."""
    with _lock:
        cur = _conn.execute(
            "SELECT COUNT(*) FROM readings WHERE ts_ms >= ? AND ts_ms <= ?",
            (start_ms, end_ms),
        )
        total = cur.fetchone()[0]
        stride = max(1, total // max_points) if total else 1

        cols = ", ".join(["ts_ms"] + READING_COLUMNS)
        cur = _conn.execute(
            f"""
            SELECT {cols} FROM (
                SELECT {cols}, ROW_NUMBER() OVER (ORDER BY ts_ms) AS rn
                FROM readings WHERE ts_ms >= ? AND ts_ms <= ?
            ) WHERE (rn - 1) % ? = 0
            ORDER BY ts_ms
            """,
            (start_ms, end_ms, stride),
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        point = {"ts": row[0]}
        for i, col in enumerate(READING_COLUMNS):
            point[col] = row[i + 1]
        result.append(point)
    return result


def get_range_bounds():
    with _lock:
        cur = _conn.execute("SELECT MIN(ts_ms), MAX(ts_ms) FROM readings")
        earliest, latest = cur.fetchone()
    return {"earliest_ts_ms": earliest, "latest_ts_ms": latest}


def insert_label(
    device_id: str,
    start_ts_ms: int,
    end_ts_ms: Optional[int],
    pain_level: int,
    locations: list,
    quality: list,
    activity: Optional[str],
    onset: Optional[str],
    confidence: Optional[str],
    comment: Optional[str],
):
    created_at_ms = int(time.time() * 1000)
    with _lock:
        cur = _conn.execute(
            """
            INSERT INTO labels (
                device_id, start_ts_ms, end_ts_ms, pain_level, locations_json,
                quality_json, activity, onset, confidence, comment, created_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id, start_ts_ms, end_ts_ms, pain_level, json.dumps(locations),
                json.dumps(quality), activity, onset, confidence, comment, created_at_ms,
            ),
        )
        _conn.commit()
        label_id = cur.lastrowid
    return get_label(label_id)


def get_label(label_id: int):
    with _lock:
        cur = _conn.execute("SELECT * FROM labels WHERE id = ?", (label_id,))
        row = cur.fetchone()
        col_names = [d[0] for d in cur.description]
    return _row_to_label(row, col_names) if row else None


def list_labels(start_ms: Optional[int] = None, end_ms: Optional[int] = None):
    query = "SELECT * FROM labels"
    params = []
    if start_ms is not None and end_ms is not None:
        # Overlaps the requested range: a point label's end_ts_ms is NULL,
        # so treat it as equal to its start for overlap purposes.
        query += " WHERE start_ts_ms <= ? AND COALESCE(end_ts_ms, start_ts_ms) >= ?"
        params = [end_ms, start_ms]
    query += " ORDER BY start_ts_ms"

    with _lock:
        cur = _conn.execute(query, params)
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description]
    return [_row_to_label(row, col_names) for row in rows]


def _row_to_label(row, col_names):
    d = dict(zip(col_names, row))
    d["locations"] = json.loads(d.pop("locations_json") or "[]")
    d["quality"] = json.loads(d.pop("quality_json") or "[]")
    return d
