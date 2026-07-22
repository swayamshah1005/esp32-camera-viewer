// src/components/LabelPainPanel.jsx
// Persistent "Label pain" panel for retrospective annotation. Applies to
// either a single pinned moment (click on a chart) or a dragged interval
// (click-drag on a chart), whichever the TimeSeriesExplorer last reported
// via the `selection` prop.

import React, { useState } from 'react';
import { Tag, X } from 'lucide-react';
import BodyMap from './BodyMap.jsx';
import {
  PAIN_QUALITIES, ACTIVITIES, ONSET_OPTIONS, CONFIDENCE_OPTIONS,
} from '../data/sensorConfig';
import { formatTimeOfDay } from '../utils/formatters';

const LABELS_URL = 'http://localhost:8000/api/labels';

const emptyForm = {
  painLevel: 5,
  locations: [],
  quality: [],
  activity: '',
  onset: '',
  confidence: '',
  comment: '',
};

export default function LabelPainPanel({ selection, onClearSelection, onSaved, deviceId = 'esp32_01' }) {
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null); // { kind: 'success' | 'error', message } | null

  const toggleFrom = (key, value) => {
    setForm((prev) => {
      const list = prev[key];
      const next = list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
      return { ...prev, [key]: next };
    });
  };

  const canSave = !!selection && !saving;

  const handleSave = async () => {
    if (!selection) return;
    setSaving(true);
    setStatus(null);
    const body = {
      device_id: deviceId,
      start_ts_ms: selection.type === 'range' ? Math.round(selection.start) : Math.round(selection.ts),
      end_ts_ms: selection.type === 'range' ? Math.round(selection.end) : null,
      pain_level: form.painLevel,
      locations: form.locations,
      quality: form.quality,
      activity: form.activity || null,
      onset: form.onset || null,
      confidence: form.confidence || null,
      comment: form.comment || null,
    };
    try {
      const res = await fetch(LABELS_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`save failed (${res.status})`);
      const saved = await res.json();
      onSaved?.(saved);
      setStatus({ kind: 'success', message: `Saved: ${form.painLevel}/10 at ${describeSelection(selection)}` });
      setForm(emptyForm);
      onClearSelection?.();
    } catch (err) {
      setStatus({ kind: 'error', message: `Could not save: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel label-panel">
      <div className="panel-header">
        <h2><Tag size={15} /> Label pain</h2>
      </div>

      <div className={`selection-banner${selection ? '' : ' selection-banner--empty'}`}>
        <span>{selection ? `Labeling: ${describeSelection(selection)}` : 'Click a chart to pin a moment, or drag to select an interval'}</span>
        {selection && (
          <button className="btn btn--ghost btn--icon" onClick={onClearSelection} title="Clear selection">
            <X size={13} />
          </button>
        )}
      </div>

      <div className="label-panel-section">
        <label>Pain level: <span className="mono">{form.painLevel}</span> / 10</label>
        <input
          type="range"
          min={0}
          max={10}
          step={1}
          value={form.painLevel}
          onChange={(e) => setForm((p) => ({ ...p, painLevel: Number(e.target.value) }))}
        />
      </div>

      <div className="label-panel-section">
        <label>Pain location</label>
        <BodyMap selected={form.locations} onToggle={(id) => toggleFrom('locations', id)} />
      </div>

      <div className="label-panel-section">
        <label>Pain quality</label>
        <div className="chip-group">
          {PAIN_QUALITIES.map((q) => (
            <span
              key={q.id}
              className={`chip${form.quality.includes(q.id) ? ' chip--active' : ''}`}
              onClick={() => toggleFrom('quality', q.id)}
            >
              {q.label}
            </span>
          ))}
        </div>
      </div>

      <div className="label-panel-section">
        <label>Activity</label>
        <select
          value={form.activity}
          onChange={(e) => setForm((p) => ({ ...p, activity: e.target.value }))}
        >
          <option value="">Not specified</option>
          {ACTIVITIES.map((a) => (
            <option key={a.id} value={a.id}>{a.label}</option>
          ))}
        </select>
      </div>

      <div className="label-panel-section">
        <label>Onset</label>
        <div className="radio-group">
          {ONSET_OPTIONS.map((o) => (
            <label key={o.id} className="radio-option">
              <input
                type="radio"
                name="onset"
                checked={form.onset === o.id}
                onChange={() => setForm((p) => ({ ...p, onset: o.id }))}
              />
              {o.label}
            </label>
          ))}
        </div>
      </div>

      <div className="label-panel-section">
        <label>Confidence in memory</label>
        <div className="radio-group">
          {CONFIDENCE_OPTIONS.map((c) => (
            <label key={c.id} className="radio-option">
              <input
                type="radio"
                name="confidence"
                checked={form.confidence === c.id}
                onChange={() => setForm((p) => ({ ...p, confidence: c.id }))}
              />
              {c.label}
            </label>
          ))}
        </div>
      </div>

      <div className="label-panel-section">
        <label>Comment (optional)</label>
        <textarea
          rows={2}
          placeholder="Anything else worth remembering about this moment..."
          value={form.comment}
          onChange={(e) => setForm((p) => ({ ...p, comment: e.target.value }))}
        />
      </div>

      <button className="btn btn--primary label-panel-save" onClick={handleSave} disabled={!canSave}>
        {saving ? 'Saving...' : 'Save label'}
      </button>

      {status && (
        <div className={`label-panel-status label-panel-status--${status.kind}`}>{status.message}</div>
      )}
    </section>
  );
}

function describeSelection(selection) {
  if (!selection) return '';
  if (selection.type === 'moment') return formatTimeOfDay(selection.ts);
  return `${formatTimeOfDay(selection.start, { seconds: false })} – ${formatTimeOfDay(selection.end, { seconds: false })}`;
}
