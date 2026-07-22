// src/components/SpectralWaterfall.jsx
//
// Spectrogram/waterfall view of the AS7343's 12 spectral channels: each new
// reading is one column, each channel is one row, color = intensity. This is
// the "high-frequency, many-channel" signal in the sensor set -- unlike
// single-value low-frequency signals (temperature, motion, ...) which stay
// as ordinary time-series line charts elsewhere, a multi-channel spectrum is
// best read as a heatmap over time, the way synthetic-sensor spectrograms
// (accelerometer/mic/EMI) are usually plotted.

import React, { useEffect, useRef } from 'react';
import { AS7343_CHANNELS } from '../data/sensorConfig';

const LABEL_GUTTER = 56;
const ROW_HEIGHT = 13;
const CANVAS_HEIGHT = ROW_HEIGHT * AS7343_CHANNELS.length;

// Approximation of matplotlib's "magma" colormap -- black/purple at low
// intensity, through magenta/orange, to pale yellow at peak. Matches the
// reference spectrogram's palette.
const MAGMA_STOPS = [
  [0, 0, 4],
  [81, 18, 124],
  [183, 55, 121],
  [252, 137, 97],
  [252, 253, 191],
];

function magma(t) {
  const clamped = Math.max(0, Math.min(1, t));
  const scaled = clamped * (MAGMA_STOPS.length - 1);
  const i = Math.min(MAGMA_STOPS.length - 2, Math.floor(scaled));
  const frac = scaled - i;
  const [r0, g0, b0] = MAGMA_STOPS[i];
  const [r1, g1, b1] = MAGMA_STOPS[i + 1];
  const r = Math.round(r0 + (r1 - r0) * frac);
  const g = Math.round(g0 + (g1 - g0) * frac);
  const b = Math.round(b0 + (b1 - b0) * frac);
  return `rgb(${r},${g},${b})`;
}

export default function SpectralWaterfall({ frames, height = CANVAS_HEIGHT }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const width = container.clientWidth;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    // Label gutter
    ctx.fillStyle = '#0d0f14';
    ctx.fillRect(0, 0, LABEL_GUTTER, height);
    ctx.font = '9.5px "IBM Plex Mono", monospace';
    ctx.fillStyle = '#8891a0';
    ctx.textBaseline = 'middle';
    AS7343_CHANNELS.forEach((c, i) => {
      ctx.fillText(`${c.id} ${c.nm}`, 4, i * ROW_HEIGHT + ROW_HEIGHT / 2);
    });

    const plotWidth = width - LABEL_GUTTER;
    if (!frames.length) return;

    // Auto-scale against the current buffer so the display stays readable
    // regardless of ambient light level.
    let maxVal = 1;
    frames.forEach((frame) => frame.forEach((v) => { if (v > maxVal) maxVal = v; }));

    const colWidth = plotWidth / frames.length;
    frames.forEach((frame, col) => {
      frame.forEach((v, row) => {
        ctx.fillStyle = magma(v / maxVal);
        ctx.fillRect(
          LABEL_GUTTER + col * colWidth, row * ROW_HEIGHT,
          Math.ceil(colWidth) + 1, ROW_HEIGHT
        );
      });
    });
  }, [frames, height]);

  return (
    <div className="waterfall-container" ref={containerRef}>
      <canvas ref={canvasRef} className="waterfall-canvas" />
    </div>
  );
}
