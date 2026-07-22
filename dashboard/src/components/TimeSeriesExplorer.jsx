// src/components/TimeSeriesExplorer.jsx
//
// The retrospective "time-based memory reconstruction" view: real local-time
// timestamps on the x-axis, three ways to control what range is visible
// (quick presets, an exact custom from/to range, or zooming to whatever you
// just dragged-selected), and a synced cursor across every metric so the
// sensor cards above can show "what was happening at this exact moment."
//
// One drag gesture, two uses: click a chart to pin a moment, or click-drag to
// select an interval. That same selection feeds both the "Zoom to this
// range" button here and the Label Pain panel alongside it -- no separate
// brush/handle widget to learn.

import React, { useEffect, useRef, useState } from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceArea, ReferenceLine,
} from 'recharts';
import { COLORS, RANGE_PRESETS } from '../data/sensorConfig';
import {
  formatNumber, formatTimeOfDay, formatDateTimeOfDay, toDatetimeLocalValue,
} from '../utils/formatters';

const METRICS = [
  { key: 'temp', label: 'Ambient temperature', unit: '°C', color: COLORS.blue, decimals: 1 },
  { key: 'humidity', label: 'Relative humidity', unit: '%RH', color: COLORS.blue, decimals: 0 },
  { key: 'pressure', label: 'Pressure', unit: 'hPa', color: COLORS.blue, decimals: 1 },
  { key: 'co2', label: 'True CO2', unit: 'ppm', color: COLORS.green, decimals: 0 },
  { key: 'aqi', label: 'AQI', unit: '/5', color: COLORS.amber, decimals: 1 },
  { key: 'tvoc', label: 'TVOC', unit: 'ppb', color: COLORS.amber, decimals: 0 },
  { key: 'lux', label: 'Illuminance', unit: 'lux', color: COLORS.teal, decimals: 0 },
  { key: 'skin_temp', label: 'Skin temperature', unit: '°C', color: COLORS.red, decimals: 1 },
  { key: 'motion_mag', label: 'Motion magnitude', unit: 'm/s²', color: COLORS.red, decimals: 2 },
  { key: 'flex_angle', label: 'Flex bend angle', unit: '°', color: COLORS.violet, decimals: 0 },
];

const SYNC_ID = 'history-explorer';
const DRAG_THRESHOLD_FRACTION = 0.004; // below this fraction of the visible range, treat a drag as a click

export default function TimeSeriesExplorer({
  rows, range, bounds, activePreset, setPreset, setRange, onHoverChange, selection, onSelectionChange, labels,
}) {
  const dragStartRef = useRef(null);
  const [liveDragEnd, setLiveDragEnd] = useState(null);
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [customError, setCustomError] = useState(null);

  // Keep the custom from/to fields following the active preset (including on
  // mount) so they always start from a sensible baseline -- but only when a
  // preset drove the change, never on focus/typing, so editing one field
  // never silently resets the other.
  useEffect(() => {
    if (!activePreset || !range) return;
    setCustomFrom(toDatetimeLocalValue(range.start));
    setCustomTo(toDatetimeLocalValue(range.end));
    setCustomError(null);
  }, [activePreset, range]);

  if (!range) {
    return <div className="panel"><div className="empty-state">Loading history range...</div></div>;
  }

  const domain = [range.start, range.end];
  const rangeSpan = range.end - range.start;

  const handleMouseDown = (state) => {
    if (state?.activeLabel == null) return;
    dragStartRef.current = state.activeLabel;
    setLiveDragEnd(state.activeLabel);
  };

  const handleMouseMove = (state) => {
    if (state?.activeLabel == null) return;
    onHoverChange(state.activeLabel);
    if (dragStartRef.current !== null) setLiveDragEnd(state.activeLabel);
  };

  const handleMouseUp = (state) => {
    const start = dragStartRef.current;
    const end = state?.activeLabel ?? liveDragEnd;
    dragStartRef.current = null;
    setLiveDragEnd(null);
    if (start == null || end == null) return;

    if (Math.abs(end - start) > rangeSpan * DRAG_THRESHOLD_FRACTION) {
      onSelectionChange({ type: 'range', start: Math.min(start, end), end: Math.max(start, end) });
    } else {
      onSelectionChange({ type: 'moment', ts: end });
    }
  };

  const handleMouseLeave = () => {
    onHoverChange(null);
  };

  const dragPreview = dragStartRef.current !== null && liveDragEnd !== null && liveDragEnd !== dragStartRef.current
    ? { x1: Math.min(dragStartRef.current, liveDragEnd), x2: Math.max(dragStartRef.current, liveDragEnd) }
    : null;

  const applyCustomRange = () => {
    const start = new Date(customFrom).getTime();
    const end = new Date(customTo).getTime();
    if (Number.isNaN(start) || Number.isNaN(end)) {
      setCustomError('Enter both a from and to time.');
      return;
    }
    if (start >= end) {
      setCustomError('"From" must be earlier than "to".');
      return;
    }
    setCustomError(null);
    setRange({ start, end });
  };

  const zoomToSelection = () => {
    if (selection?.type !== 'range') return;
    setRange({ start: selection.start, end: selection.end });
  };

  return (
    <div className="explorer">
      <div className="range-toolbar">
        <div className="segmented">
          {RANGE_PRESETS.map((p) => (
            <button
              key={p.id}
              className={`segmented-btn${activePreset === p.id ? ' segmented-btn--active' : ''}`}
              onClick={() => setPreset(p.id)}
            >
              {p.label}
            </button>
          ))}
        </div>
        <span className="range-toolbar-label mono">
          {formatDateTimeOfDay(range.start)} &ndash; {formatDateTimeOfDay(range.end)}
        </span>
        {bounds.earliestTsMs && (
          <span className="range-toolbar-hint">
            Data available from {formatDateTimeOfDay(bounds.earliestTsMs)}
          </span>
        )}
      </div>

      <div className="custom-range-row">
        <span className="custom-range-label">Jump to a specific time:</span>
        <input
          type="datetime-local"
          value={customFrom}
          onChange={(e) => setCustomFrom(e.target.value)}
        />
        <span className="custom-range-sep">to</span>
        <input
          type="datetime-local"
          value={customTo}
          onChange={(e) => setCustomTo(e.target.value)}
        />
        <button className="btn btn--primary" onClick={applyCustomRange}>Go</button>
        {customError && <span className="custom-range-error">{customError}</span>}
      </div>

      {selection?.type === 'range' && (
        <div className="selection-zoom-row">
          <span>
            Selected: {formatTimeOfDay(selection.start, { seconds: false })} &ndash; {formatTimeOfDay(selection.end, { seconds: false })}
          </span>
          <button className="btn" onClick={zoomToSelection}>Zoom to this range</button>
        </div>
      )}

      <div className="chart-grid">
        {METRICS.map((m) => (
          <ExplorerChart
            key={m.key}
            metric={m}
            rows={rows}
            domain={domain}
            selection={selection}
            labels={labels}
            dragPreview={dragPreview}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
          />
        ))}
      </div>
    </div>
  );
}

function ExplorerChart({
  metric, rows, domain, selection, labels, dragPreview, onMouseDown, onMouseMove, onMouseUp, onMouseLeave,
}) {
  const { key, label, unit, color, decimals } = metric;

  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <div>
          <span className="chart-card-label">{label}</span>
          <span className="chart-card-unit">{unit}</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart
          data={rows}
          syncId={SYNC_ID}
          margin={{ top: 4, right: 8, bottom: 0, left: -18 }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseLeave}
        >
          <CartesianGrid stroke="var(--grid-line)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="ts"
            type="number"
            domain={domain}
            tickFormatter={(ts) => formatTimeOfDay(ts, { seconds: false })}
            stroke="var(--text-muted)"
            fontSize={10}
            tickLine={false}
            axisLine={{ stroke: 'var(--border-subtle)' }}
          />
          <YAxis
            width={44}
            stroke="var(--text-muted)"
            fontSize={10}
            tickLine={false}
            axisLine={false}
            domain={['auto', 'auto']}
            tickFormatter={(v) => formatNumber(v, decimals === 0 ? 0 : 1)}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg-panel-raised)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 6,
              fontSize: 11,
            }}
            labelFormatter={(ts) => formatTimeOfDay(ts)}
            formatter={(v) => [`${formatNumber(v, decimals)} ${unit}`, label]}
            isAnimationActive={false}
          />
          <Line type="monotone" dataKey={key} stroke={color} strokeWidth={1.75} dot={false} isAnimationActive={false} />

          {dragPreview && (
            <ReferenceArea x1={dragPreview.x1} x2={dragPreview.x2} fill="var(--accent-teal)" fillOpacity={0.12} />
          )}

          {selection?.type === 'moment' && (
            <ReferenceLine x={selection.ts} stroke="var(--accent-teal)" strokeDasharray="3 3" />
          )}
          {selection?.type === 'range' && (
            <ReferenceArea x1={selection.start} x2={selection.end} fill="var(--accent-teal)" fillOpacity={0.15} stroke="var(--accent-teal)" />
          )}

          {labels.map((l) => (l.end_ts_ms ? (
            <ReferenceArea
              key={l.id}
              x1={l.start_ts_ms}
              x2={l.end_ts_ms}
              fill="var(--accent-amber)"
              fillOpacity={0.12}
              stroke="var(--accent-amber)"
              strokeOpacity={0.4}
            />
          ) : (
            <ReferenceLine
              key={l.id}
              x={l.start_ts_ms}
              stroke="var(--accent-amber)"
              strokeDasharray="2 2"
              label={{ value: `${l.pain_level}`, position: 'top', fill: 'var(--accent-amber)', fontSize: 10 }}
            />
          )))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
