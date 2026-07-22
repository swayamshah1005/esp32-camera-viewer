// src/components/TopStatusBar.jsx
import React from 'react';
import { Wifi, WifiOff, Radio, Radar } from 'lucide-react';
import { formatRelativeAge } from '../utils/formatters';

function Pill({ ok, okLabel, badLabel, Icon }) {
  return (
    <div className={`status-pill ${ok ? 'status-pill--ok' : 'status-pill--bad'}`}>
      <Icon size={14} strokeWidth={2.2} />
      <span>{ok ? okLabel : badLabel}</span>
    </div>
  );
}

export default function TopStatusBar({ device }) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <Radar size={17} strokeWidth={2.2} />
        <span>Pain Tracker</span>
      </div>

      <div className="topbar-device">
        <span className={`device-dot ${device.online ? 'device-dot--online' : 'device-dot--offline'}`} />
        <span className="topbar-device-caption">{device.online ? 'Online' : 'Offline'}</span>
      </div>

      <div className="topbar-pills">
        <Pill ok={device.mqttConnected} okLabel="MQTT" badLabel="MQTT down" Icon={Radio} />
        <Pill ok={device.wsConnected} okLabel="WebSocket" badLabel="WS down" Icon={device.wsConnected ? Wifi : WifiOff} />
        <div className="status-pill">
          <span>pkt {formatRelativeAge(device.lastPacketAgeMs)}</span>
        </div>
      </div>
    </header>
  );
}
