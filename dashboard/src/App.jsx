// src/App.jsx
import React, { useCallback, useEffect, useState } from 'react';
import {
  Thermometer, Wind, Leaf, SunMedium, Radar, Activity, Waves, Rainbow,
} from 'lucide-react';

import TopStatusBar from './components/TopStatusBar.jsx';
import SensorCard from './components/SensorCard.jsx';
import SpectralWaterfall from './components/SpectralWaterfall.jsx';
import TimeSeriesExplorer from './components/TimeSeriesExplorer.jsx';
import LabelPainPanel from './components/LabelPainPanel.jsx';

import { useSensorWebSocket } from './hooks/useSensorWebSocket';
import { useHistory } from './hooks/useHistory.js';
import { SENSORS } from './data/sensorConfig.js';
import { formatNumber, formatTimeOfDay, findNearestRow } from './utils/formatters.js';

const LABELS_URL = 'http://localhost:8000/api/labels';

// One entry per sensor the hardware plan supports. All of these always show,
// even before the sensor is physically wired up (reading "--" until then) --
// this is the full sensor roadmap, not just what's connected today.
const SENSOR_CARDS = [
  {
    key: 'bme280', icon: Thermometer, title: 'BME280', subtitle: 'Environmental',
    readings: (live, val) => [
      { label: 'Temperature', value: formatNumber(val('temp', live.bme280.temp), 1), unit: '°C' },
      { label: 'Humidity', value: formatNumber(val('humidity', live.bme280.humidity), 0), unit: '%RH' },
      { label: 'Pressure', value: formatNumber(val('pressure', live.bme280.pressure), 1), unit: 'hPa' },
    ],
  },
  {
    key: 'scd41', icon: Wind, title: 'SCD41', subtitle: 'True CO2 (NDIR)',
    readings: (live, val) => [{ label: 'CO2 concentration', value: formatNumber(val('co2', live.scd41.co2), 0), unit: 'ppm' }],
  },
  {
    key: 'ens160', icon: Leaf, title: 'ENS160', subtitle: 'Air quality index',
    readings: (live, val) => [
      { label: 'AQI', value: formatNumber(val('aqi', live.ens160.aqi), 0), unit: '/5' },
      { label: 'TVOC', value: formatNumber(val('tvoc', live.ens160.tvoc), 0), unit: 'ppb' },
    ],
  },
  {
    key: 'veml7700', icon: SunMedium, title: 'VEML7700', subtitle: 'Ambient light',
    readings: (live, val) => [{ label: 'Illuminance', value: formatNumber(val('lux', live.veml7700.lux), 0), unit: 'lux' }],
  },
  {
    key: 'mlx90632', icon: Radar, title: 'MLX90632', subtitle: 'Non-contact IR',
    readings: (live, val) => [{ label: 'Skin/body surface proxy', value: formatNumber(val('skin_temp', live.mlx90632.skinTemp), 1), unit: '°C' }],
  },
  {
    key: 'lsm6ds3tr', icon: Activity, title: 'LSM6DS3TR-C', subtitle: 'Inertial (accel + gyro)',
    readings: (live, val) => [{ label: 'Motion magnitude', value: formatNumber(val('motion_mag', live.lsm6ds3tr.motionMag), 2), unit: 'm/s²' }],
  },
  {
    // Not part of the persisted history schema (spectral data isn't stored
    // to SQLite), so this always shows the live value directly -- no
    // hover-scrubbing on this one.
    key: 'as7343', icon: Rainbow, title: 'AS7343', subtitle: 'Spectral (14-channel)',
    readings: (live) => [
      { label: 'Dominant channel', value: live.as7343.dominantChannel ?? '--', unit: '' },
      { label: 'Wavelength', value: formatNumber(live.as7343.dominantNm, 0), unit: 'nm' },
      { label: 'Clear', value: formatNumber(live.as7343.clear, 0), unit: '' },
    ],
  },
  {
    key: 'flex', icon: Waves, title: 'Flex Sensor', subtitle: 'Biomechanical',
    readings: (live, val) => [{ label: 'Bend angle', value: formatNumber(val('flex_angle', live.flex.angle), 0), unit: '°' }],
  },
];

export default function App() {
  const snapshot = useSensorWebSocket();
  const { device, live, spectro } = snapshot;

  const historyState = useHistory();
  const { range, rows } = historyState;
  const [hoverTs, setHoverTs] = useState(null);
  const [selection, setSelection] = useState(null);
  const [labels, setLabels] = useState([]);

  const fetchLabels = useCallback(async () => {
    if (!range) return;
    try {
      const res = await fetch(`${LABELS_URL}?start_ms=${Math.round(range.start)}&end_ms=${Math.round(range.end)}`);
      const data = await res.json();
      setLabels(data.labels || []);
    } catch {
      // leave previously loaded labels in place on a transient fetch failure
    }
  }, [range]);

  useEffect(() => {
    fetchLabels();
  }, [fetchLabels]);

  const displayRow = hoverTs !== null ? findNearestRow(rows, hoverTs) : null;
  const val = (key, liveVal) => (displayRow ? displayRow[key] : liveVal);

  return (
    <div className="app-shell">
      <div className="app-main">
        <TopStatusBar device={device} />

        <div className="app-content">
          <div className="section-title">
            Sensor readout {displayRow ? `at ${formatTimeOfDay(displayRow.ts)}` : '(live)'}
          </div>

          <div className="sensor-grid">
            {SENSOR_CARDS.map((c) => (
              <SensorCard
                key={c.key}
                icon={c.icon}
                title={c.title}
                subtitle={c.subtitle}
                accentColor={SENSORS[c.key].color}
                readings={c.readings(live, val)}
              />
            ))}
          </div>

          <section className="panel">
            <div className="panel-header">
              <h2>AS7343 Spectral Waterfall</h2>
              <span className="panel-header-stats">
                {spectro.dominantNm
                  ? `Dominant: ${formatNumber(spectro.dominantNm, 0)}nm`
                  : 'Waiting for data...'}
              </span>
            </div>
            <SpectralWaterfall frames={spectro.waterfall} />
            <div className="waterfall-footer">
              <span className="waterfall-caption">&larr; older &middot; newer &rarr;</span>
              <span className="waterfall-legend">
                <span>Low</span>
                <span className="waterfall-legend-gradient" />
                <span>High</span>
              </span>
            </div>
          </section>

          <div className="two-col">
            <TimeSeriesExplorer
              rows={rows}
              range={range}
              bounds={historyState.bounds}
              activePreset={historyState.activePreset}
              setPreset={historyState.setPreset}
              setRange={historyState.setRange}
              onHoverChange={setHoverTs}
              selection={selection}
              onSelectionChange={setSelection}
              labels={labels}
            />
            <LabelPainPanel
              selection={selection}
              onClearSelection={() => setSelection(null)}
              onSaved={fetchLabels}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
