// src/hooks/useHistory.js
//
// Backs the History & Labels page. Fetches a time range of persisted sensor
// readings from the FastAPI backend (see backend/storage.py + the
// /api/history* endpoints in backend/main.py), independent of the live
// 60-second snapshot useSensorWebSocket keeps for the Overview page.

import { useCallback, useEffect, useRef, useState } from 'react';
import { RANGE_PRESETS } from '../data/sensorConfig';

const HISTORY_URL = 'http://localhost:8000/api/history';
const RANGE_URL = 'http://localhost:8000/api/history/range';
const AUTO_REFRESH_MS = 5000;

export function useHistory() {
  const [bounds, setBounds] = useState({ earliestTsMs: null, latestTsMs: null });
  const [range, setRangeState] = useState(null); // { start, end } in ms
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activePreset, setActivePreset] = useState('1h');

  const rangeRef = useRef(range);
  rangeRef.current = range;

  const refreshBounds = useCallback(async () => {
    try {
      const res = await fetch(RANGE_URL);
      const data = await res.json();
      setBounds({ earliestTsMs: data.earliest_ts_ms, latestTsMs: data.latest_ts_ms });
      return data;
    } catch {
      return null;
    }
  }, []);

  const setRange = useCallback((next, presetId = null) => {
    setActivePreset(presetId);
    setRangeState(next);
  }, []);

  const setPreset = useCallback(async (presetId) => {
    const preset = RANGE_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    const data = (await refreshBounds()) || {};
    const latest = data.latest_ts_ms ?? Date.now();
    const earliest = data.earliest_ts_ms ?? latest;
    const start = preset.ms === null ? earliest : Math.max(earliest, latest - preset.ms);
    setRange({ start, end: latest }, presetId);
  }, [refreshBounds, setRange]);

  const fetchRows = useCallback(async () => {
    const current = rangeRef.current;
    if (!current) return;
    setLoading(true);
    try {
      const url = `${HISTORY_URL}?start_ms=${Math.round(current.start)}&end_ms=${Math.round(current.end)}&max_points=2000`;
      const res = await fetch(url);
      const data = await res.json();
      setRows(data.points || []);
    } catch {
      // leave previous rows in place on a transient fetch failure
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load: pull bounds, default to the 1h preset.
  useEffect(() => {
    setPreset('1h');
  }, [setPreset]);

  // Re-fetch rows whenever the selected range changes, and poll while a
  // preset (rather than a manual zoom) is active so the "live tail" grows.
  useEffect(() => {
    fetchRows();
    if (!activePreset) return undefined;
    const timer = setInterval(() => {
      setPreset(activePreset);
    }, AUTO_REFRESH_MS);
    return () => clearInterval(timer);
  }, [range, activePreset, fetchRows, setPreset]);

  return {
    bounds,
    range,
    rows,
    loading,
    activePreset,
    setPreset,
    setRange,
  };
}
