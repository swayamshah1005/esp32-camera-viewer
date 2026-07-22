// src/components/BodyMap.jsx
// Simple front-view body silhouette with clickable hotspot regions for the
// pain-location picker. Multi-select: click a region to toggle it.

import React from 'react';
import { BODY_REGIONS } from '../data/sensorConfig';

export default function BodyMap({ selected = [], onToggle }) {
  return (
    <div className="body-map">
      <svg className="body-map-svg" viewBox="0 0 200 400" role="group" aria-label="Body location picker">
        <g className="body-figure">
          {/* legs, drawn first so the torso overlaps their tops cleanly */}
          <polyline className="body-figure-limb" points="88,158 83,286 80,370" />
          <polyline className="body-figure-limb" points="112,158 117,286 120,370" />
          {/* arms */}
          <polyline className="body-figure-limb" points="72,68 44,148 31,213" />
          <polyline className="body-figure-limb" points="128,68 156,148 169,213" />
          {/* torso + neck + head */}
          <rect className="body-figure-torso" x="76" y="58" width="48" height="100" rx="20" />
          <rect className="body-figure-neck" x="93" y="46" width="14" height="12" />
          <circle className="body-figure-head" cx="100" cy="32" r="16" />
        </g>
        {BODY_REGIONS.map((region) => {
          const isSelected = selected.includes(region.id);
          return (
            <circle
              key={region.id}
              className={`body-region${isSelected ? ' body-region--selected' : ''}`}
              cx={region.cx}
              cy={region.cy}
              r={region.r}
              onClick={() => onToggle(region.id)}
              role="button"
              aria-pressed={isSelected}
              aria-label={region.label}
            >
              <title>{region.label}</title>
            </circle>
          );
        })}
      </svg>
      <div className="body-map-selected">
        {selected.length === 0 && <span className="body-map-selected-empty">No location selected</span>}
        {selected.map((id) => {
          const region = BODY_REGIONS.find((r) => r.id === id);
          return (
            <span className="chip chip--active" key={id} onClick={() => onToggle(id)}>
              {region ? region.label : id}
            </span>
          );
        })}
      </div>
    </div>
  );
}
