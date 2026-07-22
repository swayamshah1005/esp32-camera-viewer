// src/components/SensorCard.jsx
import React from 'react';

export default function SensorCard({ icon: Icon, title, subtitle, accentColor, readings, footer }) {
  return (
    <div className="sensor-card" style={{ '--accent': accentColor }}>
      <div className="sensor-card-header">
        <div className="sensor-card-icon">
          <Icon size={16} strokeWidth={2} />
        </div>
        <div className="sensor-card-title">
          <span className="sensor-card-name">{title}</span>
          <span className="sensor-card-sub">{subtitle}</span>
        </div>
      </div>

      <div className="sensor-card-readings">
        {readings.map((r) => (
          <div className="sensor-reading" key={r.label}>
            <span className="sensor-reading-value mono">
              {r.value}
              <span className="sensor-reading-unit">{r.unit}</span>
            </span>
            <span className="sensor-reading-label">{r.label}</span>
          </div>
        ))}
      </div>

      {footer && <div className="sensor-card-footer">{footer}</div>}
    </div>
  );
}
