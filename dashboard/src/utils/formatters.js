// src/utils/formatters.js
// Small, dependency-free formatting helpers shared across dashboard components.

export function formatNumber(value, decimals = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  return Number(value).toFixed(decimals);
}

export function formatSigned(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  const n = Number(value);
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(decimals)}`;
}

export function formatDuration(totalSeconds) {
  if (!totalSeconds || totalSeconds < 0) totalSeconds = 0;
  const s = Math.floor(totalSeconds % 60);
  const m = Math.floor((totalSeconds / 60) % 60);
  const h = Math.floor(totalSeconds / 3600);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

export function formatClock(date) {
  if (!date) return '--:--:--';
  const d = date instanceof Date ? date : new Date(date);
  return d.toLocaleTimeString('en-US', { hour12: false });
}

// 12-hour local-time-of-day formatting, for the human-facing retrospective
// labeling UI (e.g. "3:42:15 PM") as opposed to formatClock's 24h instrument readout.
export function formatTimeOfDay(ts, { seconds = true } = {}) {
  if (ts === null || ts === undefined) return '--';
  const d = new Date(ts);
  return d.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    second: seconds ? '2-digit' : undefined,
    hour12: true,
  });
}

// Converts a ms timestamp to the local-time string an <input type="datetime-local">
// expects/emits ("YYYY-MM-DDTHH:mm"). Pairs with `new Date(value).getTime()`
// to parse the input's value back into a ms timestamp -- both sides interpret
// the string as local time, so no timezone math is needed.
export function toDatetimeLocalValue(ts) {
  if (ts === null || ts === undefined) return '';
  const d = new Date(ts);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatDateTimeOfDay(ts) {
  if (ts === null || ts === undefined) return '--';
  const d = new Date(ts);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  const time = formatTimeOfDay(ts, { seconds: false });
  return sameDay ? time : `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${time}`;
}

export function formatRelativeAge(ms) {
  if (ms === null || ms === undefined) return '--';
  if (ms < 900) return 'just now';
  if (ms < 60000) return `${Math.round(ms / 1000)}s ago`;
  if (ms < 3600000) return `${Math.round(ms / 60000)}m ago`;
  return `${Math.round(ms / 3600000)}h ago`;
}

export function formatFrequency(hz) {
  if (hz === null || hz === undefined || Number.isNaN(hz)) return '--';
  if (hz >= 1000) return `${(hz / 1000).toFixed(2)} kHz`;
  return `${Math.round(hz)} Hz`;
}

export function formatDb(db) {
  if (db === null || db === undefined || Number.isNaN(db)) return '--';
  return `${db.toFixed(1)} dB`;
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

// Nearest-timestamp row lookup for scrubbing history rows -- e.g. driving the
// sensor-card readouts from wherever the cursor sits on the history charts.
export function findNearestRow(rows, ts) {
  if (!rows || !rows.length || ts === null || ts === undefined) return null;
  let best = rows[0];
  let bestDiff = Math.abs(rows[0].ts - ts);
  for (let i = 1; i < rows.length; i += 1) {
    const diff = Math.abs(rows[i].ts - ts);
    if (diff < bestDiff) {
      best = rows[i];
      bestDiff = diff;
    }
  }
  return best;
}

export function shortId(prefix = 'SES') {
  const rand = Math.random().toString(36).slice(2, 7).toUpperCase();
  const stamp = Date.now().toString(36).slice(-4).toUpperCase();
  return `${prefix}-${stamp}${rand}`;
}
