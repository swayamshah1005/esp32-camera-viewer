from flask import Flask, request, send_file, render_template_string
from flask_cors import CORS
import os
import time

app = Flask(__name__)
CORS(app)

LATEST_IMAGE = "latest.jpg"
last_upload_time = None
frame_count = 0
server_start_time = time.time()  # used to expose real, non-fabricated uptime

DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ESP32 Environmental Sensor Bundle</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --bg-0:#08090b;
    --bg-1:#0e1013;
    --panel:#131519;
    --line:rgba(255,255,255,0.07);
    --line-strong:rgba(255,255,255,0.14);
    --text-hi:#eceef1;
    --text-mid:#9497a1;
    --text-lo:#5b5e68;
    --blue:#3b82f6;
    --blue-glow:rgba(59,130,246,0.35);
    --cyan:#38bdf8;
    --green:#2fd47a;
    --red:#f0475a;
    --amber:#f5a524;
    --radius-lg:18px;
    --radius-md:12px;
    --radius-sm:8px;
    --font-display:'Space Grotesk', sans-serif;
    --font-mono:'IBM Plex Mono', monospace;
  }

  *{ box-sizing:border-box; margin:0; padding:0; }
  html,body{ height:100%; background:var(--bg-0); color:var(--text-hi); font-family:var(--font-display); -webkit-font-smoothing:antialiased; }

  body{
    background-image:
      radial-gradient(circle at 12% -10%, rgba(59,130,246,0.10), transparent 45%),
      radial-gradient(circle at 100% 0%, rgba(56,189,248,0.06), transparent 40%),
      linear-gradient(180deg, var(--bg-1), var(--bg-0) 60%);
    background-attachment:fixed;
    min-height:100vh;
    position:relative;
    overflow-x:hidden;
  }
  body::before{
    content:"";
    position:fixed; inset:0; pointer-events:none;
    background-image:
      linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
    background-size:42px 42px;
    mask-image:radial-gradient(circle at 50% 0%, black 0%, transparent 70%);
    z-index:0;
  }
  ::selection{ background:var(--blue-glow); color:#fff; }
  ::-webkit-scrollbar{ width:8px; height:8px; }
  ::-webkit-scrollbar-track{ background:transparent; }
  ::-webkit-scrollbar-thumb{ background:var(--line-strong); border-radius:8px; }
  ::-webkit-scrollbar-thumb:hover{ background:rgba(255,255,255,0.25); }

  .shell{ position:relative; z-index:1; max-width:1520px; margin:0 auto; padding:20px 28px 40px; }

  /* ================= TOP NAV ================= */
  .topnav{
    display:flex; align-items:center; justify-content:space-between;
    padding:14px 22px; border-radius:var(--radius-md);
    background:rgba(19,21,25,0.65);
    backdrop-filter:blur(18px) saturate(140%);
    -webkit-backdrop-filter:blur(18px) saturate(140%);
    border:1px solid var(--line);
    box-shadow:0 10px 30px rgba(0,0,0,0.35);
    margin-bottom:22px;
  }
  .brand{ display:flex; align-items:center; gap:12px; }
  .brand-mark{
    width:38px; height:38px; border-radius:10px;
    background:linear-gradient(145deg, var(--blue), #1d4ed8);
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 0 0 1px rgba(255,255,255,0.08), 0 6px 18px var(--blue-glow);
    position:relative; overflow:hidden;
  }
  .brand-mark::after{
    content:""; position:absolute; inset:0;
    background:linear-gradient(120deg, transparent 30%, rgba(255,255,255,0.35) 50%, transparent 70%);
    transform:translateX(-120%); animation:sheen 5s ease-in-out infinite;
  }
  @keyframes sheen{ 0%,60%{ transform:translateX(-120%); } 100%{ transform:translateX(120%); } }
  .brand-mark svg{ width:20px; height:20px; }
  .brand-text .title{ font-size:15.5px; font-weight:600; letter-spacing:0.2px; }
  .brand-text .subtitle{ font-family:var(--font-mono); font-size:11px; color:var(--text-lo); letter-spacing:0.08em; text-transform:uppercase; margin-top:1px; }
  .nav-right{ display:flex; align-items:center; gap:22px; }
  .clock{ font-family:var(--font-mono); font-size:13px; color:var(--text-mid); text-align:right; line-height:1.35; }
  .clock .date-line{ color:var(--text-lo); font-size:11px; letter-spacing:0.04em; }
  .clock .time-line{ color:var(--text-hi); font-size:14.5px; font-weight:500; letter-spacing:0.03em; }
  .conn-pill{
    display:flex; align-items:center; gap:9px; padding:8px 14px; border-radius:999px;
    border:1px solid var(--line-strong); background:rgba(255,255,255,0.02);
    font-family:var(--font-mono); font-size:12px; letter-spacing:0.03em; color:var(--text-mid);
    transition:border-color .3s ease, background .3s ease;
  }
  .dot{ width:8px; height:8px; border-radius:50%; background:var(--red); box-shadow:0 0 0 3px rgba(240,71,90,0.18); transition:background .3s ease, box-shadow .3s ease; }
  .dot.on{ background:var(--green); box-shadow:0 0 0 3px rgba(47,212,122,0.18); animation:pulse-dot 2s ease-in-out infinite; }
  @keyframes pulse-dot{ 0%,100%{ box-shadow:0 0 0 3px rgba(47,212,122,0.18); } 50%{ box-shadow:0 0 0 6px rgba(47,212,122,0.10); } }

  /* ================= LAYOUT ================= */
  .grid{ display:grid; grid-template-columns:minmax(0,1.65fr) minmax(300px,1fr); gap:20px; }
  .panel{
    background:linear-gradient(180deg, rgba(23,25,30,0.75), rgba(15,16,19,0.75));
    backdrop-filter:blur(16px) saturate(140%);
    -webkit-backdrop-filter:blur(16px) saturate(140%);
    border:1px solid var(--line); border-radius:var(--radius-lg);
    box-shadow:0 12px 34px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.03);
    animation:rise .5s ease both;
  }
  @keyframes rise{ from{ opacity:0; transform:translateY(10px); } to{ opacity:1; transform:translateY(0); } }
  .panel-head{ display:flex; align-items:center; justify-content:space-between; padding:16px 20px; border-bottom:1px solid var(--line); }
  .panel-head h2{ font-size:12.5px; font-weight:600; letter-spacing:0.09em; text-transform:uppercase; color:var(--text-mid); }
  .panel-head h2 span{ color:var(--text-hi); }
  .panel-tag{ font-family:var(--font-mono); font-size:10.5px; color:var(--text-lo); letter-spacing:0.05em; padding:3px 9px; border:1px solid var(--line-strong); border-radius:999px; }

  /* ================= CAMERA PANEL ================= */
  .camera-panel{ padding:16px; }
  .camera-frame{
    position:relative; width:100%; aspect-ratio:16/10; border-radius:var(--radius-md); overflow:hidden;
    background:radial-gradient(circle at 50% 40%, #14161a, #0a0b0d 75%);
    border:1px solid var(--line-strong);
  }
  .camera-frame img{ width:100%; height:100%; object-fit:cover; display:block; opacity:0; transition:opacity .35s ease; }
  .camera-frame img.ready{ opacity:1; }
  .hud-corner{ position:absolute; width:26px; height:26px; border:2px solid var(--blue); opacity:0.85; z-index:3; filter:drop-shadow(0 0 4px var(--blue-glow)); }
  .hud-corner.tl{ top:12px; left:12px; border-right:none; border-bottom:none; border-radius:6px 0 0 0; }
  .hud-corner.tr{ top:12px; right:12px; border-left:none; border-bottom:none; border-radius:0 6px 0 0; }
  .hud-corner.bl{ bottom:12px; left:12px; border-right:none; border-top:none; border-radius:0 0 0 6px; }
  .hud-corner.br{ bottom:12px; right:12px; border-left:none; border-top:none; border-radius:0 0 6px 0; }
  .scanline{
    position:absolute; left:0; right:0; height:2px;
    background:linear-gradient(90deg, transparent, var(--cyan), transparent);
    box-shadow:0 0 12px 2px var(--cyan); opacity:0.55; z-index:2; animation:scan 3.6s linear infinite;
  }
  @keyframes scan{ 0%{ top:4%; opacity:0; } 8%{ opacity:0.55; } 92%{ opacity:0.55; } 100%{ top:96%; opacity:0; } }
  .rec-badge{
    position:absolute; top:14px; left:50%; transform:translateX(-50%);
    display:flex; align-items:center; gap:7px; padding:5px 12px; border-radius:999px;
    background:rgba(10,11,13,0.6); border:1px solid var(--line-strong);
    font-family:var(--font-mono); font-size:10.5px; letter-spacing:0.08em; color:var(--text-mid); z-index:3;
  }
  .rec-badge .dot{ width:6px; height:6px; }
  .feed-caption{
    position:absolute; bottom:12px; left:14px; font-family:var(--font-mono); font-size:10.5px;
    color:rgba(236,238,241,0.65); letter-spacing:0.04em; z-index:3; text-shadow:0 1px 4px rgba(0,0,0,0.6);
  }
  .no-signal{
    position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center;
    gap:14px; color:var(--text-lo); z-index:1; transition:opacity .3s ease;
  }
  .spinner{ width:34px; height:34px; border-radius:50%; border:2.5px solid rgba(255,255,255,0.08); border-top-color:var(--blue); animation:spin 0.9s linear infinite; }
  @keyframes spin{ to{ transform:rotate(360deg); } }
  .no-signal .label{ font-family:var(--font-mono); font-size:11.5px; letter-spacing:0.08em; text-transform:uppercase; }
  .camera-footer{
    display:flex; flex-wrap:wrap; gap:8px 18px; justify-content:space-between; align-items:center;
    padding:14px 8px 4px; font-family:var(--font-mono); font-size:11px; color:var(--text-lo); letter-spacing:0.04em;
  }
  .camera-footer b{ color:var(--text-mid); font-weight:500; }

  /* ================= RIGHT COLUMN ================= */
  .right-col{ display:flex; flex-direction:column; gap:20px; }
  .stat-list{ padding:6px 20px 16px; }
  .stat-row{ display:flex; align-items:center; justify-content:space-between; padding:12px 0; border-bottom:1px solid var(--line); }
  .stat-row:last-child{ border-bottom:none; }
  .stat-row .k{ font-size:12.5px; color:var(--text-mid); display:flex; align-items:center; gap:9px; }
  .stat-row .v{ font-family:var(--font-mono); font-size:12.5px; color:var(--text-hi); font-weight:500; }
  .badge{ display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-family:var(--font-mono); font-size:11px; letter-spacing:0.03em; border:1px solid var(--line-strong); }
  .badge .dot{ width:6px; height:6px; }
  .badge.ok{ color:var(--green); border-color:rgba(47,212,122,0.3); background:rgba(47,212,122,0.08); }
  .badge.bad{ color:var(--red); border-color:rgba(240,71,90,0.3); background:rgba(240,71,90,0.08); }
  .badge.neutral{ color:var(--text-mid); }

  /* ================= SENSOR "NOT INSTALLED" GRID ================= */
  .sensor-grid{ display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:16px 20px 20px; }
  .sensor-cell{
    padding:13px 14px; border-radius:var(--radius-sm);
    background:rgba(255,255,255,0.012); border:1px dashed var(--line-strong);
    opacity:0.55; filter:grayscale(0.4);
    transition:opacity .25s ease, filter .25s ease;
  }
  .sensor-cell:hover{ opacity:0.8; filter:grayscale(0); }
  .sensor-cell .s-label{
    font-size:10.5px; color:var(--text-lo); letter-spacing:0.07em; text-transform:uppercase;
    display:flex; align-items:center; gap:6px; margin-bottom:9px;
  }
  .sensor-cell .s-label svg{ width:12px; height:12px; opacity:0.7; }
  .sensor-cell .s-value{ font-family:var(--font-mono); font-size:12px; color:var(--text-lo); font-weight:500; letter-spacing:0.02em; }
  .sensor-cell .s-value .not-installed-dot{
    display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--text-lo); margin-right:7px;
  }

  /* ================= BOTTOM SECTION ================= */
  .bottom-grid{ display:grid; grid-template-columns:1.7fr 1fr; gap:20px; margin-top:20px; }
  .log-window{ height:250px; overflow-y:auto; padding:6px 20px 16px; font-family:var(--font-mono); font-size:12px; }
  .log-entry{ display:flex; gap:12px; padding:8px 0; border-bottom:1px solid var(--line); animation:log-in .35s ease both; align-items:baseline; }
  @keyframes log-in{ from{ opacity:0; transform:translateX(-6px); } to{ opacity:1; transform:translateX(0); } }
  .log-entry .t{ color:var(--text-lo); flex-shrink:0; }
  .log-entry .m{ color:var(--text-mid); flex:1; }
  .log-entry.evt-good .m{ color:var(--green); }
  .log-entry.evt-info .m{ color:var(--text-hi); }
  .log-entry.evt-warn .m{ color:var(--amber); }
  .log-entry.evt-bad .m{ color:var(--red); }
  .log-empty{ color:var(--text-lo); font-size:12px; padding:14px 0; }

  /* ================= FUTURE FEATURES ================= */
  .feature-list{ display:flex; flex-direction:column; gap:9px; padding:14px 18px 18px; }
  .feature-row{
    display:flex; align-items:center; justify-content:space-between; padding:11px 13px;
    border-radius:var(--radius-sm); background:rgba(255,255,255,0.015); border:1px solid var(--line);
  }
  .feature-row.done{ border-color:rgba(47,212,122,0.22); background:rgba(47,212,122,0.05); }
  .feature-row.pending{ opacity:0.6; }
  .feature-row .f-name{ display:flex; align-items:center; gap:10px; font-size:12.5px; color:var(--text-mid); }
  .feature-row.done .f-name{ color:var(--text-hi); }
  .feature-row .f-icon{ width:16px; height:16px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
  .feature-row.done .f-icon svg{ stroke:var(--green); }
  .feature-row.pending .f-icon svg{ stroke:var(--text-lo); }
  .feature-row .f-status{
    font-family:var(--font-mono); font-size:10px; letter-spacing:0.08em; text-transform:uppercase;
    padding:3px 9px; border:1px solid var(--line-strong); border-radius:999px; color:var(--text-lo);
  }
  .feature-row.done .f-status{ color:var(--green); border-color:rgba(47,212,122,0.3); }

  footer.foot{ text-align:center; padding:26px 0 6px; font-family:var(--font-mono); font-size:10.5px; letter-spacing:0.08em; color:var(--text-lo); text-transform:uppercase; }

  /* ================= RESPONSIVE ================= */
  @media (max-width: 980px){
    .grid{ grid-template-columns:1fr; }
    .bottom-grid{ grid-template-columns:1fr; }
    .nav-right{ gap:12px; }
    .clock{ display:none; }
  }
  @media (max-width: 560px){
    .shell{ padding:14px 14px 30px; }
    .sensor-grid{ grid-template-columns:1fr 1fr; }
    .topnav{ flex-wrap:wrap; gap:10px; }
  }
</style>
</head>
<body>
<div class="shell">

  <!-- ================= TOP NAV ================= -->
  <div class="topnav">
    <div class="brand">
      <div class="brand-mark">
        <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/>
          <circle cx="12" cy="12" r="3.2"/>
        </svg>
      </div>
      <div class="brand-text">
        <div class="title">ESP32 Environmental Sensor Bundle</div>
        <div class="subtitle">Telemetry &amp; Vision Console</div>
      </div>
    </div>
    <div class="nav-right">
      <div class="clock">
        <div class="date-line" id="dateLine">—</div>
        <div class="time-line" id="timeLine">--:--:--</div>
      </div>
      <div class="conn-pill">
        <span class="dot" id="connDot"></span>
        <span id="connText">CONNECTING…</span>
      </div>
    </div>
  </div>

  <!-- ================= MAIN GRID ================= -->
  <div class="grid">

    <!-- LEFT: CAMERA -->
    <div class="panel camera-panel">
      <div class="camera-frame" id="cameraFrame">
        <div class="hud-corner tl"></div>
        <div class="hud-corner tr"></div>
        <div class="hud-corner bl"></div>
        <div class="hud-corner br"></div>
        <div class="scanline" id="scanline"></div>
        <div class="rec-badge"><span class="dot on"></span>LIVE FEED</div>
        <img id="camera" src="/latest" alt="ESP32 camera feed">
        <div class="no-signal" id="noSignal">
          <div class="spinner"></div>
          <div class="label">Awaiting Signal</div>
        </div>
        <div class="feed-caption" id="feedCaption">CAM-01 · /latest</div>
      </div>
      <div class="camera-footer">
        <span>STREAM &nbsp;<b id="streamState">INITIALIZING</b></span>
        <span>RESOLUTION &nbsp;<b id="resolution">—</b></span>
        <span>LAST UPDATE &nbsp;<b id="lastUploadFooter">Never</b></span>
        <span>FRAMES &nbsp;<b id="frameCountFooter">0</b></span>
      </div>
    </div>

    <!-- RIGHT COLUMN -->
    <div class="right-col">

      <!-- SYSTEM STATUS -->
      <div class="panel">
        <div class="panel-head">
          <h2>System <span>Status</span></h2>
          <div class="panel-tag">CORE</div>
        </div>
        <div class="stat-list">
          <div class="stat-row">
            <span class="k">ESP32 Connected</span>
            <span class="badge bad" id="espBadge"><span class="dot"></span>OFFLINE</span>
          </div>
          <div class="stat-row">
            <span class="k">Flask Server</span>
            <span class="badge ok" id="serverBadge"><span class="dot on"></span>RUNNING</span>
          </div>
          <div class="stat-row">
            <span class="k">WiFi Link</span>
            <span class="badge bad" id="wifiBadge">UNKNOWN</span>
          </div>
          <div class="stat-row">
            <span class="k">Server Time</span>
            <span class="v" id="serverTime">—</span>
          </div>
          <div class="stat-row">
            <span class="k">Server Uptime</span>
            <span class="v" id="uptime">—</span>
          </div>
        </div>
      </div>

      <!-- CAMERA STATISTICS -->
      <div class="panel">
        <div class="panel-head">
          <h2>Camera <span>Statistics</span></h2>
          <div class="panel-tag">CAM-01</div>
        </div>
        <div class="stat-list">
          <div class="stat-row">
            <span class="k">Frames Received</span>
            <span class="v" id="frameCount">0</span>
          </div>
          <div class="stat-row">
            <span class="k">Last Upload</span>
            <span class="v" id="lastUpload">Never</span>
          </div>
          <div class="stat-row">
            <span class="k">Image Resolution</span>
            <span class="v" id="resolutionRow">—</span>
          </div>
        </div>
      </div>

      <!-- ENVIRONMENTAL SENSORS (NOT INSTALLED) -->
      <div class="panel">
        <div class="panel-head">
          <h2>Environmental <span>Sensors</span></h2>
          <div class="panel-tag">HARDWARE PENDING</div>
        </div>
        <div class="sensor-grid" id="sensorGrid">
          <!-- populated by JS from a single source-of-truth list, all "Sensor Not Installed" -->
        </div>
      </div>

    </div>
  </div>

  <!-- ================= BOTTOM SECTION ================= -->
  <div class="bottom-grid">

    <!-- SYSTEM EVENT LOG -->
    <div class="panel">
      <div class="panel-head">
        <h2>System <span>Event Log</span></h2>
        <div class="panel-tag" id="logCount">0 EVENTS</div>
      </div>
      <div class="log-window" id="logWindow">
        <div class="log-empty">No events recorded yet.</div>
      </div>
    </div>

    <!-- FUTURE FEATURES -->
    <div class="panel">
      <div class="panel-head">
        <h2>Future <span>Features</span></h2>
        <div class="panel-tag">ROADMAP</div>
      </div>
      <div class="feature-list" id="featureList"></div>
    </div>

  </div>

  <footer class="foot">ESP32 Environmental Sensor Bundle · Local Telemetry Console</footer>
</div>

<script>
(function(){
  "use strict";

// ================= WebSocket =================
const ws = new WebSocket(`ws://${window.location.hostname}:8001/ws`);

ws.onopen = () => {
  console.log("✅ WebSocket Connected");
  addLog("WebSocket Connected", "good");
};

ws.onerror = (err) => {
  console.error(err);
  addLog("WebSocket Error", "bad");
};

ws.onclose = () => {
  console.log("❌ WebSocket Closed");
  addLog("WebSocket Disconnected", "bad");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  console.log("MQTT Status:", data);

  setConn(true);
  setEspBadge(true);

  els.wifiBadge.className = "badge ok";
  els.wifiBadge.innerHTML = `<span class="dot on"></span>RSSI ${data.wifi_rssi} dBm`;

  els.frameCount.textContent = data.frames_uploaded;
  els.frameCountFooter.textContent = data.frames_uploaded;

  els.lastUpload.textContent = data.received_at;
  els.lastUploadFooter.textContent = data.received_at;

  els.serverTime.textContent = data.received_at;

  if (typeof data.uptime_seconds === "number") {
    els.uptime.textContent =
      Math.floor(data.uptime_seconds / 3600).toString().padStart(2, "0") +
      ":" +
      Math.floor((data.uptime_seconds % 3600) / 60).toString().padStart(2, "0") +
      ":" +
      (data.uptime_seconds % 60).toString().padStart(2, "0");
  }

  // MQTT updates are continuous; don't log every message.
};

  // ---------- icon library (minimal inline SVGs, no external deps) ----------
  var ICON = {
    check: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    circle: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/></svg>',
    thermometer: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 14.76V3.5a2 2 0 0 0-4 0v11.26a4 4 0 1 0 4 0Z"/></svg>',
    droplet: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.7s6 6.2 6 10.6a6 6 0 1 1-12 0c0-4.4 6-10.6 6-10.6Z"/></svg>',
    wind: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8h9.5a2.5 2.5 0 1 0-2.4-3.2M3 12h13a2.5 2.5 0 1 1-2.4 3.2M3 16h7"/></svg>',
    sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/></svg>',
    wave: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h2l2-7 3 14 3-10 2 6 2-4h6"/></svg>',
    chip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/></svg>'
  };

  // ---------- state ----------
  var lastFrameCount = 0;
  var everConnected = false;
  var serverEverSeen = false;
  var logs = [];
  var MAX_LOGS = 60;
  var resolutionKnown = false;

  var els = {
    dateLine: document.getElementById('dateLine'),
    timeLine: document.getElementById('timeLine'),
    connDot: document.getElementById('connDot'),
    connText: document.getElementById('connText'),
    camera: document.getElementById('camera'),
    noSignal: document.getElementById('noSignal'),
    streamState: document.getElementById('streamState'),
    espBadge: document.getElementById('espBadge'),
    wifiBadge: document.getElementById('wifiBadge'),
    serverBadge: document.getElementById('serverBadge'),
    serverTime: document.getElementById('serverTime'),
    uptime: document.getElementById('uptime'),
    frameCount: document.getElementById('frameCount'),
    frameCountFooter: document.getElementById('frameCountFooter'),
    lastUpload: document.getElementById('lastUpload'),
    lastUploadFooter: document.getElementById('lastUploadFooter'),
    resolution: document.getElementById('resolution'),
    resolutionRow: document.getElementById('resolutionRow'),
    logWindow: document.getElementById('logWindow'),
    logCount: document.getElementById('logCount'),
    sensorGrid: document.getElementById('sensorGrid'),
    featureList: document.getElementById('featureList'),
  };

  // ---------- clock (local browser time, used only for the top-right display) ----------
  function pad(n){ return n < 10 ? '0' + n : '' + n; }

  function updateClock(){
    var now = new Date();
    var days = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
    var months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
    els.dateLine.textContent = days[now.getDay()] + ' ' + now.getDate() + ' ' + months[now.getMonth()] + ' ' + now.getFullYear();
    els.timeLine.textContent = pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
  }

  function formatUptime(totalSeconds){
    var s = Math.max(0, Math.floor(totalSeconds));
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    return pad(h) + ':' + pad(m) + ':' + pad(sec);
  }

  // ---------- event log (only ever fed real, observed state transitions) ----------
  function addLog(message, kind){
    var now = new Date();
    logs.unshift({ time: pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds()), message: message, kind: kind || 'info' });
    if (logs.length > MAX_LOGS) logs.pop();
    renderLogs();
  }

  function renderLogs(){
    if (logs.length === 0){
      els.logWindow.innerHTML = '<div class="log-empty">No events recorded yet.</div>';
      els.logCount.textContent = '0 EVENTS';
      return;
    }
    var html = '';
    for (var i = 0; i < logs.length; i++){
      var l = logs[i];
      html += '<div class="log-entry evt-' + l.kind + '">' +
                '<span class="t">' + l.time + '</span>' +
                '<span class="m">' + l.message + '</span>' +
              '</div>';
    }
    els.logWindow.innerHTML = html;
    els.logCount.textContent = logs.length + ' EVENT' + (logs.length === 1 ? '' : 'S');
  }

  // ---------- sensor cards: no fabricated readings, ever ----------
  var SENSORS = [
    { name: 'Temperature', icon: ICON.thermometer },
    { name: 'Humidity', icon: ICON.droplet },
    { name: 'Air Quality', icon: ICON.wind },
    { name: 'Light Sensor', icon: ICON.sun },
    { name: 'Noise Level', icon: ICON.wave },
    { name: 'IMU', icon: ICON.chip }
  ];

  function renderSensorGrid(){
    var html = '';
    for (var i = 0; i < SENSORS.length; i++){
      var s = SENSORS[i];
      html += '<div class="sensor-cell">' +
                '<div class="s-label">' + s.icon + s.name + '</div>' +
                '<div class="s-value"><span class="not-installed-dot"></span>Sensor Not Installed</div>' +
              '</div>';
    }
    els.sensorGrid.innerHTML = html;
  }

  // ---------- future features: real project status only ----------
  var FEATURES = [
    { name: 'Camera Streaming', done: true },
    { name: 'HTTP Upload', done: true },
    { name: 'Flask Backend', done: true },
    { name: 'MQTT', done: false },
    { name: 'WebSockets', done: false },
    { name: 'Environmental Sensors', done: false },
    { name: 'FastAPI', done: false },
    { name: 'React Dashboard', done: false },
    { name: 'Custom PCB', done: false }
  ];

  function renderFeatureList(){
    var html = '';
    for (var i = 0; i < FEATURES.length; i++){
      var f = FEATURES[i];
      html += '<div class="feature-row ' + (f.done ? 'done' : 'pending') + '">' +
                '<span class="f-name"><span class="f-icon">' + (f.done ? ICON.check : ICON.circle) + '</span>' + f.name + '</span>' +
                '<span class="f-status">' + (f.done ? 'Active' : 'Planned') + '</span>' +
              '</div>';
    }
    els.featureList.innerHTML = html;
  }

  // ---------- camera feed ----------
  function refreshCamera(){
    var img = new Image();
    img.onload = function(){
      els.camera.src = img.src;
      els.camera.classList.add('ready');
      els.noSignal.style.display = 'none';
      els.streamState.textContent = 'ACTIVE';

      // real resolution, read directly from the decoded image — never guessed
      if (img.naturalWidth && img.naturalHeight){
        var res = img.naturalWidth + ' × ' + img.naturalHeight;
        els.resolution.textContent = res;
        els.resolutionRow.textContent = res;
        resolutionKnown = true;
      }
    };
    img.onerror = function(){
      els.camera.classList.remove('ready');
      els.noSignal.style.display = 'flex';
      els.streamState.textContent = 'NO SIGNAL';
    };
    img.src = '/latest?t=' + Date.now();
  }

  // ---------- status polling (/status is the single source of truth) ----------
  function setConn(reachable){
    els.connDot.classList.toggle('on', reachable);
    els.connText.textContent = reachable ? 'LINK ESTABLISHED' : 'NO LINK';
  }

  function setEspBadge(online){
    els.espBadge.className = 'badge ' + (online ? 'ok' : 'bad');
    els.espBadge.innerHTML = '<span class="dot' + (online ? ' on' : '') + '"></span>' + (online ? 'ONLINE' : 'OFFLINE');
  }

  async function pollStatus(){
    try {
      var res = await fetch('/status');
      if (!res.ok) throw new Error('bad status ' + res.status);
      var data = await res.json();

      setConn(true);

      if (!serverEverSeen){
        addLog('Server Link Established', 'info');
        serverEverSeen = true;
      }

      els.serverBadge.innerHTML = '<span class="dot on"></span>RUNNING';

      var online = !!data.online;
      setEspBadge(online);

      // WiFi link is not separately telemetered by the ESP32 — an uploaded
      // frame within the online window is itself proof the WiFi link is up,
      // so this reuses that same real signal rather than adding a fake one.
      els.wifiBadge.className = 'badge ' + (online ? 'ok' : 'bad');
      els.wifiBadge.innerHTML = online ? 'CONNECTED' : 'NO LINK';

      if (data.server_time){
        els.serverTime.textContent = data.server_time;
      }
      if (typeof data.server_uptime_seconds === 'number'){
        els.uptime.textContent = formatUptime(data.server_uptime_seconds);
      } else {
        els.uptime.textContent = 'Not Available';
      }

      var newCount = data.frame_count || 0;
      els.frameCount.textContent = newCount;
      els.frameCountFooter.textContent = newCount;

      var lastUploadText = data.last_upload_time || 'Never';
      els.lastUpload.textContent = lastUploadText;
      els.lastUploadFooter.textContent = lastUploadText;

      if (!resolutionKnown){
        els.resolution.textContent = '—';
        els.resolutionRow.textContent = '—';
      }

      if (newCount > lastFrameCount){
        addLog('Image Uploaded', 'good');
        addLog('HTTP 200', 'info');
      }
      lastFrameCount = newCount;

      if (online && !everConnected){
        addLog('ESP32 Connected', 'good');
        everConnected = true;
      } else if (!online && everConnected){
        addLog('ESP32 Disconnected', 'bad');
        everConnected = false;
      }

    } catch (err) {
      setConn(false);
      setEspBadge(false);
      els.wifiBadge.className = 'badge neutral';
      els.wifiBadge.textContent = 'UNKNOWN';
      els.serverBadge.innerHTML = '<span class="dot"></span>UNREACHABLE';
      if (serverEverSeen){
        addLog('Server Unreachable', 'bad');
      }
    }
  }

  // ---------- init ----------
  renderSensorGrid();
  renderFeatureList();
  updateClock();
  pollStatus();
  refreshCamera();

  setInterval(updateClock, 1000);
  setInterval(refreshCamera, 1000);
})();
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(DASHBOARD)

@app.route("/upload", methods=["POST"])
def upload():
    global last_upload_time, frame_count

    with open(LATEST_IMAGE, "wb") as f:
        f.write(request.data)

    frame_count += 1
    last_upload_time = time.strftime("%Y-%m-%d %H:%M:%S")

    return {"status": "ok"}, 200

@app.route("/latest")
def latest():
    if not os.path.exists(LATEST_IMAGE):
        return {"error": "No image uploaded yet"}, 404
    return send_file(LATEST_IMAGE, mimetype="image/jpeg")

@app.route("/status")
def status():
    online = False

    if last_upload_time is not None:
        online = time.time() - os.path.getmtime(LATEST_IMAGE) < 5

    return {
        # --- existing fields, unchanged, for backward compatibility ---
        "frame_count": frame_count,
        "last_upload_time": last_upload_time,
        "online": online,
        # --- new fields: real, server-side data only ---
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server_uptime_seconds": int(time.time() - server_start_time),
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
