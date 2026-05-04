"""
Foto-EXIF zu interaktiver Reisekarte – Cinematic Travel Journal Edition

Liest GPS-Daten aus Fotos und rendert ein self-contained reisekarte.html mit:
  - Split-Layout: links große Foto-Stage, rechts kompakter 3D-Globus (MapLibre)
  - Tag-Pills (eine Farbe pro Tag), Heatmap-Toggle, Auto-Play, Style-Toggle
  - Tastatur-Navigation (← / →) und klickbare Chevron-Buttons
  - Dunkles, elegantes "Travel-Magazine"-Design

Standard-Nutzung:
  python foto_karte.py
  → liest aus ./fotos/ (relativ zum Skript)
  → schreibt ./reisekarte.html (relativ zum Skript)

Optionaler Override:
  python foto_karte.py /pfad/zu/anderem/ordner
"""

import sys
import base64
import json
from io import BytesIO
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from jinja2 import Template
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    print("Hinweis: 'pillow-heif' nicht installiert – HEIC-Dateien werden übersprungen.")

DAY_COLORS = [
    "#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#9A6324", "#800000", "#808000",
    "#000075", "#469990", "#bfef45", "#fabed4", "#dcbeff",
]
UNTIMED_COLOR = "#64748b"
SCRIPT_VERSION = "1.0.0"


INDEX_TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{{ ctx.title }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400;1,9..144,500&family=Manrope:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" />
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  :root {
    --bg: #0b0d12;
    --bg-soft: #11141b;
    --panel: #15181f;
    --panel-hi: #1c2029;
    --line: rgba(255, 255, 255, 0.06);
    --line-strong: rgba(255, 255, 255, 0.12);
    --text: #eef0f4;
    --text-dim: #8b93a4;
    --text-faint: #5a6273;
    --accent: #f5c469;
    --accent-soft: rgba(245, 196, 105, 0.18);
    --shadow-near: 0 4px 14px rgba(0, 0, 0, 0.35);
    --shadow-far: 0 24px 60px rgba(0, 0, 0, 0.5);
    --radius-lg: 22px;
    --radius-md: 14px;
    --radius-sm: 10px;
    --pad: 28px;
    --font-display: "Fraunces", "Iowan Old Style", "Times New Roman", serif;
    --font-ui: "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
  }

  * { box-sizing: border-box; }

  html, body {
    height: 100%;
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-ui);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    overflow: hidden;
  }

  /* ambient gradient backdrop */
  body::before {
    content: "";
    position: fixed;
    inset: -10%;
    z-index: 0;
    background:
      radial-gradient(ellipse 60% 50% at 20% 10%, rgba(67, 99, 216, 0.12), transparent 60%),
      radial-gradient(ellipse 50% 50% at 90% 100%, rgba(245, 196, 105, 0.08), transparent 60%),
      radial-gradient(ellipse 80% 60% at 50% 50%, rgba(20, 25, 35, 0.6), transparent 70%);
    pointer-events: none;
  }

  /* film grain overlay */
  body::after {
    content: "";
    position: fixed;
    inset: 0;
    z-index: 9999;
    pointer-events: none;
    opacity: 0.05;
    mix-blend-mode: overlay;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='180' height='180' filter='url(%23n)' opacity='0.85'/></svg>");
  }

  .app {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-rows: auto 1fr;
    height: 100vh;
  }

  /* =========================== TOP BAR =========================== */
  .topbar {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 10px 20px;
    border-bottom: 1px solid var(--line);
    background: linear-gradient(180deg, rgba(11, 13, 18, 0.92), rgba(11, 13, 18, 0.78));
    backdrop-filter: blur(12px);
    z-index: 5;
  }

  .brand {
    display: flex;
    align-items: baseline;
    gap: 14px;
    flex-shrink: 0;
  }
  .brand .mark {
    font-family: var(--font-display);
    font-style: italic;
    font-weight: 400;
    font-size: 21px;
    letter-spacing: -0.02em;
    line-height: 1;
    color: var(--text);
  }
  .brand .stats {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-faint);
    padding-left: 14px;
    border-left: 1px solid var(--line-strong);
  }
  .brand .stats span { color: var(--text-dim); }

  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
    overflow-x: auto;
    flex: 1;
    min-width: 0;
    scrollbar-width: thin;
    scrollbar-color: var(--line-strong) transparent;
  }
  .pills::-webkit-scrollbar { height: 4px; }
  .pills::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 2px; }

  .pill {
    --pill-color: #888;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 3px 8px 3px 7px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--line);
    color: var(--text-dim);
    font-family: var(--font-ui);
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 0.01em;
    cursor: pointer;
    white-space: nowrap;
    transition: background 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
    user-select: none;
  }
  .pill::before {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--pill-color);
    box-shadow: 0 0 0 0 var(--pill-color);
    flex-shrink: 0;
  }
  .pill[data-active="true"] {
    color: var(--text);
    background: rgba(255, 255, 255, 0.06);
    border-color: var(--line-strong);
  }
  .pill[data-active="true"]::before {
    box-shadow: 0 0 8px 0 var(--pill-color);
  }
  .pill[data-active="false"] {
    color: var(--text-faint);
    opacity: 0.55;
    text-decoration: line-through;
    text-decoration-color: var(--text-faint);
    text-decoration-thickness: 1px;
  }
  .pill:hover { transform: translateY(-1px); }

  .pill .count {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-faint);
  }

  .tools {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
    padding-left: 12px;
    border-left: 1px solid var(--line);
  }
  .tool {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 12px;
    border-radius: 999px;
    background: transparent;
    border: 1px solid var(--line);
    color: var(--text-dim);
    font-family: var(--font-ui);
    font-size: 11.5px;
    font-weight: 500;
    letter-spacing: 0.02em;
    cursor: pointer;
    transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
  }
  .tool:hover {
    color: var(--text);
    border-color: var(--line-strong);
    background: rgba(255, 255, 255, 0.03);
  }
  .tool[data-active="true"] {
    color: var(--bg);
    background: var(--accent);
    border-color: var(--accent);
  }
  .tool .ico {
    font-size: 13px;
    line-height: 1;
  }

  /* =========================== MAIN =========================== */
  main {
    display: grid;
    grid-template-columns: minmax(0, 1.85fr) minmax(340px, 1fr);
    height: 100%;
    overflow: hidden;
  }

  /* =========================== PHOTO STAGE =========================== */
  .stage {
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 36px 44px 32px;
    min-width: 0;
    overflow: hidden;
  }

  .stage-frame {
    position: relative;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 0;
  }

  .photo-wrap {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .photo {
    position: absolute;
    inset: 0;
    margin: auto;
    max-width: 100%;
    max-height: 100%;
    width: auto;
    height: auto;
    object-fit: contain;
    border-radius: 6px;
    box-shadow:
      0 4px 12px rgba(0, 0, 0, 0.35),
      0 24px 60px rgba(0, 0, 0, 0.5);
    opacity: 0;
    transition: opacity 280ms cubic-bezier(0.4, 0, 0.2, 1);
  }
  .photo.show { opacity: 1; }
  /* placeholder spacer keeps the wrapper sized */
  .photo-spacer {
    visibility: hidden;
    width: min(100%, calc((100vh - 160px) * 1.6));
    height: calc(100vh - 160px);
  }

  .nav-btn {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: rgba(20, 24, 32, 0.7);
    border: 1px solid var(--line-strong);
    color: var(--text);
    cursor: pointer;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    box-shadow: var(--shadow-near);
    display: grid;
    place-items: center;
    transition: background 200ms ease, border-color 200ms ease, transform 200ms ease, color 200ms ease;
    z-index: 3;
  }
  .nav-btn:hover {
    background: rgba(28, 32, 41, 0.9);
    border-color: var(--accent);
    color: var(--accent);
    transform: translateY(-50%) scale(1.06);
  }
  .nav-btn:active { transform: translateY(-50%) scale(0.96); }
  .nav-btn.prev { left: -8px; }
  .nav-btn.next { right: -8px; }
  .nav-btn svg { width: 20px; height: 20px; stroke: currentColor; fill: none; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; }

  /* meta strip below photo */
  .meta {
    margin-top: 24px;
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 24px;
  }
  .meta .left {
    text-align: left;
    min-width: 0;
  }
  .meta .center {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-dim);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .meta .center .num { color: var(--accent); font-weight: 500; }
  .meta .right {
    text-align: right;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-faint);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .file {
    font-family: var(--font-display);
    font-style: italic;
    font-weight: 400;
    font-size: 22px;
    letter-spacing: -0.01em;
    color: var(--text);
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .when {
    margin-top: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-faint);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  /* =========================== MAP PANEL =========================== */
  .map-panel {
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 36px 36px 32px 12px;
    min-width: 0;
    overflow: hidden;
  }

  .globe-card {
    position: relative;
    flex: 1;
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: #05070d;
    border: 1px solid var(--line);
    box-shadow:
      inset 0 0 0 1px rgba(255, 255, 255, 0.02),
      var(--shadow-far);
  }
  #globe {
    position: absolute;
    inset: 0;
  }
  /* MapLibre overrides for dark theme */
  .maplibregl-ctrl-attrib {
    background: rgba(11, 13, 18, 0.7) !important;
    color: var(--text-faint) !important;
    font-family: var(--font-mono) !important;
    font-size: 9px !important;
    letter-spacing: 0.04em !important;
  }
  .maplibregl-ctrl-attrib a { color: var(--text-dim) !important; }
  .maplibregl-canvas:focus { outline: none; }

  /* vignette over globe */
  .globe-card::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    box-shadow: inset 0 0 80px 10px rgba(0, 0, 0, 0.5);
    border-radius: var(--radius-lg);
  }

  /* day badge top-left of globe */
  .globe-badge {
    position: absolute;
    top: 14px;
    left: 14px;
    z-index: 4;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px 6px 10px;
    background: rgba(11, 13, 18, 0.7);
    border: 1px solid var(--line-strong);
    border-radius: 999px;
    backdrop-filter: blur(10px);
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
  }
  .globe-badge .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
  }

  /* coords below globe */
  .coords {
    margin-top: 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-dim);
    letter-spacing: 0.05em;
  }
  .coords .pin {
    color: var(--accent);
    font-size: 13px;
  }
  .coords .label {
    color: var(--text-faint);
    text-transform: uppercase;
    font-size: 10px;
  }

  /* keyboard hint */
  .kbd-hint {
    position: fixed;
    bottom: 18px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    background: rgba(11, 13, 18, 0.85);
    border: 1px solid var(--line);
    border-radius: 999px;
    backdrop-filter: blur(10px);
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--text-faint);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    pointer-events: none;
    opacity: 0;
    transition: opacity 600ms ease;
    z-index: 50;
  }
  .kbd-hint.show { opacity: 1; }
  .kbd-hint kbd {
    font-family: var(--font-mono);
    background: var(--panel);
    border: 1px solid var(--line-strong);
    border-radius: 4px;
    padding: 1px 6px;
    color: var(--text-dim);
    font-size: 10px;
  }

  .tool-slider {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 0 10px;
    border-left: 1px solid var(--line);
  }
  .speed-label {
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--text-faint);
    letter-spacing: 0.06em;
    min-width: 28px;
    text-align: right;
  }
  input[type="range"]#speed-slider {
    -webkit-appearance: none;
    appearance: none;
    width: 80px;
    height: 3px;
    background: var(--line-strong);
    border-radius: 99px;
    outline: none;
    cursor: pointer;
  }
  input[type="range"]#speed-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 6px var(--accent);
    cursor: pointer;
  }
  input[type="range"]#speed-slider::-moz-range-thumb {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--accent);
    border: none;
    cursor: pointer;
  }

  @media (max-width: 1100px) {
    main { grid-template-columns: 1.4fr 1fr; }
    .stage { padding: 28px 28px 20px; }
    .map-panel { padding: 28px 24px 20px 8px; }
  }
</style>
</head>
<body>
<div class="app">
  <header class="topbar">
    <div class="brand">
      <span class="mark">Reisekarte</span>
      <span class="stats">
        <span>{{ ctx.stats.photos }}</span> Fotos · <span>{{ ctx.stats.days }}</span> Tage · <span>{{ ctx.stats.date_range }}</span>
      </span>
    </div>

    <div class="pills" id="pills">
      {% for d in ctx.days %}
      <button class="pill" data-day="{{ d.iso or 'untimed' }}" data-active="true" style="--pill-color: {{ d.color }};">
        {{ d.label }}<span class="count">{{ d.count }}</span>
      </button>
      {% endfor %}
    </div>

    <div class="tools">
      <button class="tool" id="btn-heatmap" data-active="false" title="Heatmap">
        <span class="ico">◐</span><span>Heat</span>
      </button>
      <button class="tool" id="btn-autoplay" data-active="false" title="Auto-Play">
        <span class="ico" id="autoplay-ico">▶</span><span>Auto</span>
      </button>
      <div class="tool-slider" id="speed-wrap">
        <input type="range" id="speed-slider" min="1" max="10" step="0.5" value="3.5">
        <span class="speed-label" id="speed-label">3.5s</span>
      </div>
      <button class="tool" id="btn-style" data-active="false" title="Karten-Stil">
        <span class="ico">◓</span><span id="style-label">Satellit</span>
      </button>
    </div>
  </header>

  <main>
    <section class="stage">
      <div class="stage-frame">
        <button class="nav-btn prev" id="btn-prev" aria-label="Vorheriges Foto">
          <svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"/></svg>
        </button>

        <div class="photo-wrap">
          <div class="photo-spacer"></div>
          <img class="photo" id="photo-a" alt="">
          <img class="photo" id="photo-b" alt="">
        </div>

        <button class="nav-btn next" id="btn-next" aria-label="Nächstes Foto">
          <svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
      </div>

      <div class="meta">
        <div class="left">
          <div class="file" id="meta-file">—</div>
          <div class="when" id="meta-when">—</div>
        </div>
        <div class="center">
          <span class="num" id="meta-num">00</span>
          <span>/</span>
          <span id="meta-total">{{ ctx.points|length }}</span>
        </div>
        <div class="right" id="meta-day">—</div>
      </div>
    </section>

    <aside class="map-panel">
      <div class="globe-card">
        <div class="globe-badge">
          <span class="dot"></span>
          <span id="badge-text">—</span>
        </div>
        <div id="globe"></div>
      </div>
      <div class="coords">
        <div><span class="pin">◉</span> <span class="label">Koordinaten</span></div>
        <div id="coord-text">— · —</div>
      </div>
    </aside>
  </main>
</div>

<div class="kbd-hint" id="kbd-hint">
  <kbd>←</kbd><kbd>→</kbd> <span>blättern</span>
</div>

<script>
(function() {
  const DATA = {{ ctx_json | safe }};
  const points = DATA.points;
  if (!points.length) { console.warn("Keine Punkte – nichts zu rendern."); return; }

  // ===================================================================
  // Map style URLs — OpenFreeMap is key-free
  // ===================================================================
  const STYLE_DARK = "https://tiles.openfreemap.org/styles/dark";
  const STYLE_SAT = {
    version: 8,
    sources: {
      esri: {
        type: "raster",
        tiles: [
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ],
        tileSize: 256,
        attribution: "© Esri · World Imagery",
        maxzoom: 19
      }
    },
    layers: [
      { id: "esri", type: "raster", source: "esri" }
    ]
  };

  // ===================================================================
  // MapLibre globe init (gracefully degrades if WebGL/maplibre unavailable)
  // ===================================================================
  const avgLon = points.reduce((s, p) => s + p.lon, 0) / points.length;
  const avgLat = points.reduce((s, p) => s + p.lat, 0) / points.length;

  let map = null;
  try {
    if (typeof maplibregl === "undefined") throw new Error("maplibre-gl not loaded");
    map = new maplibregl.Map({
      container: "globe",
      style: STYLE_DARK,
      center: [avgLon, avgLat],
      zoom: 1.4,
      pitch: 0,
      bearing: 0,
      attributionControl: { compact: true },
      fadeDuration: 200,
    });
    map.scrollZoom.enable();
    map.dragRotate.enable();
    map.touchZoomRotate.enable();
  } catch (e) {
    console.warn("[Reisekarte] Globe disabled:", e.message);
    const card = document.querySelector(".globe-card");
    if (card) {
      card.innerHTML = '<div style="position:absolute;inset:0;display:grid;place-items:center;color:var(--text-faint);font-family:var(--font-mono);font-size:11px;letter-spacing:0.06em;text-transform:uppercase;">Globus nicht verfügbar</div>';
    }
  }

  let currentStyle = "dark";
  let currentIndex = 0;
  let activeDays = new Set(DATA.days.map(d => d.iso || "untimed"));
  let heatmapOn = false;
  let autoplayOn = false;
  let autoplayTimer = null;

  // ===================================================================
  // Layer setup — re-runnable after style switches
  // ===================================================================
  function buildGeoJson(filterDays) {
    const features = points
      .filter(p => filterDays.has(p.day_iso || "untimed"))
      .map(p => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        properties: {
          idx: p.idx,
          color: p.color,
          day: p.day_iso || "untimed",
          file: p.file,
        }
      }));
    return { type: "FeatureCollection", features };
  }

  function buildPathFeatures(filterDays) {
    const byDay = {};
    points.forEach(p => {
      const key = p.day_iso || "untimed";
      if (!filterDays.has(key)) return;
      if (!p.day_iso) return; // no path for untimed
      (byDay[key] = byDay[key] || []).push(p);
    });
    const features = [];
    Object.keys(byDay).forEach(day => {
      const seq = byDay[day];
      if (seq.length < 2) return;
      features.push({
        type: "Feature",
        geometry: { type: "LineString", coordinates: seq.map(p => [p.lon, p.lat]) },
        properties: { day, color: seq[0].color }
      });
    });
    return { type: "FeatureCollection", features };
  }

  function refreshPaths() {
    if (!map || !map.getSource("paths")) return;
    const key = points[currentIndex]?.day_iso;
    const filter = key ? new Set([key]) : new Set();
    map.getSource("paths").setData(buildPathFeatures(filter));
  }

  function addLayers() {
    if (!map) return;
    // Tear down stale layers/sources before re-adding (handles style.load timing race with inline styles)
    ["active-core", "active-glow", "points-base", "heatmap", "path-lines"].forEach(id => {
      try { if (map.getLayer(id)) map.removeLayer(id); } catch(e) {}
    });
    ["points", "paths", "active"].forEach(id => {
      try { if (map.getSource(id)) map.removeSource(id); } catch(e) {}
    });

    try { map.setProjection({ type: "globe" }); } catch (e) { /* older versions */ }

    if (currentStyle === "dark") {
      try {
        map.setSky({
          "sky-color": "#05070d",
          "sky-horizon-blend": 0.5,
          "horizon-color": "#1a1f2e",
          "horizon-fog-blend": 0.6,
          "fog-color": "#0b0d12",
          "fog-ground-blend": 0.05
        });
      } catch (e) { /* older MapLibre — ignore */ }
    }

    map.addSource("points", { type: "geojson", data: buildGeoJson(activeDays) });
    map.addSource("paths", { type: "geojson", data: buildPathFeatures(activeDays) });
    map.addSource("active", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] }
    });

    // animated path lines per day
    map.addLayer({
      id: "path-lines",
      type: "line",
      source: "paths",
      paint: {
        "line-color": ["get", "color"],
        "line-width": 2,
        "line-opacity": 0.55,
        "line-dasharray": [2, 3]
      },
      layout: { "line-cap": "round", "line-join": "round" }
    });

    // heatmap (hidden by default)
    map.addLayer({
      id: "heatmap",
      type: "heatmap",
      source: "points",
      layout: { visibility: heatmapOn ? "visible" : "none" },
      paint: {
        "heatmap-weight": 1,
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 0, 0.4, 9, 1.6],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 0, 14, 9, 30],
        "heatmap-opacity": 0.85,
        "heatmap-color": [
          "interpolate", ["linear"], ["heatmap-density"],
          0, "rgba(11,13,18,0)",
          0.2, "rgba(67,99,216,0.4)",
          0.5, "rgba(245,196,105,0.7)",
          0.8, "rgba(230,25,75,0.9)",
          1, "rgba(255,255,255,1)"
        ]
      }
    });

    // base point markers
    map.addLayer({
      id: "points-base",
      type: "circle",
      source: "points",
      layout: { visibility: heatmapOn ? "none" : "visible" },
      paint: {
        "circle-color": ["get", "color"],
        "circle-radius": 5,
        "circle-stroke-width": 1.5,
        "circle-stroke-color": "#0b0d12",
        "circle-opacity": 0.95
      }
    });

    // active marker glow
    map.addLayer({
      id: "active-glow",
      type: "circle",
      source: "active",
      paint: {
        "circle-color": "#f5c469",
        "circle-radius": 22,
        "circle-blur": 0.8,
        "circle-opacity": 0.35
      }
    });
    map.addLayer({
      id: "active-core",
      type: "circle",
      source: "active",
      paint: {
        "circle-color": "#f5c469",
        "circle-radius": 8,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#0b0d12",
        "circle-opacity": 1
      }
    });

  }

  // animate dasharray for "ant-path" feel — module-level so it survives style swaps
  let dashStep = 0;
  setInterval(() => {
    if (!map || !map.getLayer || !map.getLayer("path-lines")) return;
    dashStep = (dashStep + 1) % 8;
    const dashArrays = [
      [2, 3], [2.2, 3], [2.4, 3], [2.6, 3],
      [2.8, 3], [3, 2.8], [3, 2.6], [3, 2.4]
    ];
    map.setPaintProperty("path-lines", "line-dasharray", dashArrays[dashStep]);
  }, 90);

  // ===================================================================
  // Render: switch photo + meta + globe
  // ===================================================================
  const photoA = document.getElementById("photo-a");
  const photoB = document.getElementById("photo-b");
  let frontIsA = true;

  const fmtCoord = (lat, lon) => {
    const ns = lat >= 0 ? "N" : "S";
    const ew = lon >= 0 ? "E" : "W";
    return `${Math.abs(lat).toFixed(4)}° ${ns} · ${Math.abs(lon).toFixed(4)}° ${ew}`;
  };

  function setActiveOnMap(point) {
    const src = map.getSource("active");
    if (!src) return;
    src.setData({
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        geometry: { type: "Point", coordinates: [point.lon, point.lat] },
        properties: {}
      }]
    });
  }

  function flyToPoint(point, dramatic) {
    if (!map) return;
    map.flyTo({
      center: [point.lon, point.lat],
      zoom: dramatic ? 10 : 13,
      speed: dramatic ? 0.7 : 1.2,
      curve: 1.6,
      essential: true,
    });
  }

  let lastDayIso = null;
  function render(idx, immediate) {
    const point = points[idx];
    if (!point) return;

    // crossfade photos
    const front = frontIsA ? photoA : photoB;
    const back = frontIsA ? photoB : photoA;
    let committed = false;
    const commitPhoto = () => {
      if (committed) return;
      committed = true;
      back.classList.add("show");
      front.classList.remove("show");
      frontIsA = !frontIsA;
    };
    back.onload = commitPhoto;
    back.onerror = commitPhoto;
    back.src = point.thumb_data_uri;
    back.alt = point.file;
    if (back.complete && back.naturalWidth > 0) commitPhoto();

    // meta
    document.getElementById("meta-file").textContent = point.file;
    document.getElementById("meta-when").textContent = point.time_label;
    document.getElementById("meta-num").textContent = String(idx + 1).padStart(2, "0");
    document.getElementById("meta-day").textContent = point.day_label || "ohne Datum";

    // globe badge + coords
    document.getElementById("badge-text").textContent = point.day_label || "ohne Datum";
    document.getElementById("coord-text").textContent = fmtCoord(point.lat, point.lon);

    // map (no-op if map unavailable)
    setActiveOnMap(point);
    const dayChanged = lastDayIso !== null && lastDayIso !== (point.day_iso || "untimed");
    lastDayIso = point.day_iso || "untimed";
    if (map) {
      if (immediate) {
        map.jumpTo({ center: [point.lon, point.lat], zoom: 13 });
      } else {
        flyToPoint(point, dayChanged);
      }
      refreshPaths();
    }
  }

  function visibleIndices() {
    return points
      .map((p, i) => ({ i, day: p.day_iso || "untimed" }))
      .filter(o => activeDays.has(o.day))
      .map(o => o.i);
  }

  function jumpTo(idx, fly) {
    currentIndex = idx;
    render(idx, !fly);
  }

  function step(delta) {
    const visible = visibleIndices();
    if (!visible.length) return;
    let pos = visible.indexOf(currentIndex);
    if (pos === -1) {
      currentIndex = visible[0];
    } else {
      pos = (pos + delta + visible.length) % visible.length;
      currentIndex = visible[pos];
    }
    render(currentIndex, false);
  }

  // ===================================================================
  // Wire up controls
  // ===================================================================
  document.getElementById("btn-prev").addEventListener("click", () => step(-1));
  document.getElementById("btn-next").addEventListener("click", () => step(1));

  // day pills
  document.querySelectorAll(".pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const key = pill.dataset.day;
      if (activeDays.has(key)) {
        if (activeDays.size <= 1) return; // never deactivate last
        activeDays.delete(key);
        pill.dataset.active = "false";
      } else {
        activeDays.add(key);
        pill.dataset.active = "true";
      }
      // refresh data
      if (map && map.getSource("points")) {
        map.getSource("points").setData(buildGeoJson(activeDays));
      }
      // if currentIndex is in a hidden day, jump to next visible
      const cur = points[currentIndex];
      if (cur && !activeDays.has(cur.day_iso || "untimed")) {
        step(1);
      }
    });
  });

  // heatmap
  const btnHeat = document.getElementById("btn-heatmap");
  btnHeat.addEventListener("click", () => {
    heatmapOn = !heatmapOn;
    btnHeat.dataset.active = heatmapOn ? "true" : "false";
    if (!map) return;
    if (map.getLayer("heatmap")) {
      map.setLayoutProperty("heatmap", "visibility", heatmapOn ? "visible" : "none");
    }
    if (map.getLayer("points-base")) {
      map.setLayoutProperty("points-base", "visibility", heatmapOn ? "none" : "visible");
    }
  });

  // autoplay
  const btnAuto = document.getElementById("btn-autoplay");
  const autoIco = document.getElementById("autoplay-ico");
  const speedSlider = document.getElementById("speed-slider");
  const speedLabel  = document.getElementById("speed-label");
  let autoplayInterval = parseFloat(speedSlider.value) * 1000;

  speedSlider.addEventListener("input", () => {
    const sec = parseFloat(speedSlider.value);
    autoplayInterval = sec * 1000;
    speedLabel.textContent = Number.isInteger(sec) ? sec + "s" : sec.toFixed(1) + "s";
    if (autoplayOn) {
      clearInterval(autoplayTimer);
      autoplayTimer = setInterval(() => step(1), autoplayInterval);
    }
  });

  btnAuto.addEventListener("click", () => {
    autoplayOn = !autoplayOn;
    btnAuto.dataset.active = autoplayOn ? "true" : "false";
    autoIco.textContent = autoplayOn ? "⏸" : "▶";
    if (autoplayOn) {
      autoplayTimer = setInterval(() => step(1), autoplayInterval);
    } else {
      clearInterval(autoplayTimer);
      autoplayTimer = null;
    }
  });

  // style toggle
  const btnStyle = document.getElementById("btn-style");
  const styleLabel = document.getElementById("style-label");
  function reapplyMapState() {
    if (!map) return;
    addLayers();
    const cur = points[currentIndex];
    if (cur) setActiveOnMap(cur);
  }

  btnStyle.addEventListener("click", () => {
    if (!map) return;
    if (currentStyle === "dark") {
      currentStyle = "satellite";
      styleLabel.textContent = "Dark";
      btnStyle.dataset.active = "true";
      map.setStyle(STYLE_SAT);
    } else {
      currentStyle = "dark";
      styleLabel.textContent = "Satellit";
      btnStyle.dataset.active = "false";
      map.setStyle(STYLE_DARK);
    }
    // MapLibre 4.7 doesn't emit style.load for diffed inline JSON setStyle (fixed in 5.16).
    // idle fires when new style + tiles are fully ready — works for both URL and inline styles.
    map.once("idle", reapplyMapState);
  });
  if (map) {
    map.on("style.load", reapplyMapState);
  }

  // keyboard
  function isEditable(t) {
    if (!t) return false;
    const tag = (t.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || Boolean(t.isContentEditable);
  }
  document.addEventListener("keydown", (e) => {
    if (isEditable(e.target)) return;
    if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
    else if (e.key === " ") { e.preventDefault(); btnAuto.click(); }
  }, true);

  // keyboard hint reveal
  const hint = document.getElementById("kbd-hint");
  setTimeout(() => hint.classList.add("show"), 600);
  setTimeout(() => hint.classList.remove("show"), 4500);

  // ===================================================================
  // Initial render — photo+meta render immediately, map ops queue once ready
  // ===================================================================
  render(0, true);

  if (map) {
    map.on("load", () => {
      // one-time: wire marker click/cursor (survives removeLayer/addLayer cycles on same ID)
      map.on("click", "points-base", (e) => {
        if (!e.features || !e.features[0]) return;
        jumpTo(e.features[0].properties.idx, true);
      });
      map.on("mouseenter", "points-base", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "points-base", () => { map.getCanvas().style.cursor = ""; });

      setTimeout(() => {
        const p = points[currentIndex];
        map.flyTo({ center: [p.lon, p.lat], zoom: 11, speed: 0.5, curve: 1.5, essential: true });
      }, 400);
    });
  }

  if (DATA.build_meta && console && console.info) {
    console.info("[Reisekarte] build:", DATA.build_meta.generated_at, "| version:", DATA.build_meta.script_version);
  }
})();
</script>
</body>
</html>
""")


def get_photo_data(image_path: Path, thumb_size: int = 720) -> dict | None:
    """Liest GPS, Zeitstempel und erstellt Thumbnail als base64-String."""
    try:
        img = Image.open(image_path)

        # Moderne Pillow-API: getexif() funktioniert für JPEG, HEIC, PNG, TIFF.
        # Die alte _getexif()-Methode existiert nur für JPEG und schlägt
        # bei HEIC-Dateien (HeifImageFile) fehl.
        exif = img.getexif()
        if not exif:
            return None

        # Top-Level-EXIF (DateTime, etc.)
        exif_data = {TAGS.get(k, k): v for k, v in exif.items()}

        # GPS-IFD liegt in einem Sub-IFD und muss separat ausgelesen werden.
        # Das ist die einheitliche Methode, die für alle Formate funktioniert.
        try:
            gps_ifd = exif.get_ifd(0x8825)  # 0x8825 = GPSInfo IFD-Tag
        except (AttributeError, KeyError):
            gps_ifd = exif_data.get("GPSInfo")

        if not gps_ifd:
            return None

        gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
        if "GPSLatitude" not in gps or "GPSLongitude" not in gps:
            return None

        lat = _to_degrees(gps["GPSLatitude"])
        if gps.get("GPSLatitudeRef") == "S":
            lat = -lat
        lon = _to_degrees(gps["GPSLongitude"])
        if gps.get("GPSLongitudeRef") == "W":
            lon = -lon

        timestamp_str = exif_data.get("DateTimeOriginal") or exif_data.get("DateTime")

        # Bei HEIC liegt DateTimeOriginal oft im EXIF-Sub-IFD (0x8769)
        if not timestamp_str:
            try:
                exif_sub_ifd = exif.get_ifd(0x8769)
                if exif_sub_ifd:
                    sub_data = {TAGS.get(k, k): v for k, v in exif_sub_ifd.items()}
                    timestamp_str = sub_data.get("DateTimeOriginal") or sub_data.get("DateTimeDigitized")
            except (AttributeError, KeyError):
                pass

        timestamp = (
            datetime.strptime(timestamp_str, "%Y:%m:%d %H:%M:%S")
            if timestamp_str
            else None
        )

        thumb = ImageOps.exif_transpose(img)
        thumb.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
        if thumb.mode != "RGB":
            thumb = thumb.convert("RGB")
        buf = BytesIO()
        thumb.save(buf, format="JPEG", quality=86, optimize=True)
        thumb_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        return {
            "lat": lat,
            "lon": lon,
            "time": timestamp,
            "file": image_path.name,
            "thumb": thumb_b64,
        }
    except Exception as e:
        print(f"Übersprungen: {image_path.name} ({e})")
        return None


def _to_degrees(value) -> float:
    d, m, s = value
    return float(d) + float(m) / 60 + float(s) / 3600


def build_map(points: list[dict], output: Path) -> None:
    if not points:
        print("Keine GPS-Daten gefunden.")
        return

    timed_points = sorted([p for p in points if p["time"]], key=lambda p: p["time"])
    untimed_points = sorted([p for p in points if not p["time"]], key=lambda p: p["file"].lower())
    nav_points = timed_points + untimed_points

    if not nav_points:
        print("Keine GPS-Daten gefunden.")
        return

    by_day = defaultdict(list)
    for p in timed_points:
        by_day[p["time"].date()].append(p)

    day_color: dict = {}
    days_meta: list[dict] = []
    for i, (day, day_points) in enumerate(sorted(by_day.items())):
        color = DAY_COLORS[i % len(DAY_COLORS)]
        day_color[day.isoformat()] = color
        days_meta.append({
            "iso": day.isoformat(),
            "label": day.strftime("%d.%m.%Y"),
            "color": color,
            "count": len(day_points),
        })

    if untimed_points:
        days_meta.append({
            "iso": None,
            "label": "ohne Datum",
            "color": UNTIMED_COLOR,
            "count": len(untimed_points),
        })

    points_payload = []
    for idx, p in enumerate(nav_points):
        if p["time"]:
            day_iso = p["time"].date().isoformat()
            day_label = p["time"].strftime("%d.%m.%Y")
            time_label = p["time"].strftime("%d.%m.%Y · %H:%M")
            color = day_color[day_iso]
        else:
            day_iso = None
            day_label = "ohne Datum"
            time_label = "ohne Zeitstempel"
            color = UNTIMED_COLOR

        points_payload.append({
            "idx": idx,
            "lat": p["lat"],
            "lon": p["lon"],
            "file": p["file"],
            "thumb_data_uri": "data:image/jpeg;base64," + p["thumb"],
            "time_label": time_label,
            "day_iso": day_iso,
            "day_label": day_label,
            "color": color,
        })

    if timed_points:
        date_range = (
            f"{timed_points[0]['time'].strftime('%d.%m.')}"
            f" – {timed_points[-1]['time'].strftime('%d.%m.%Y')}"
        )
    else:
        date_range = "ohne Zeitstempel"

    ctx = {
        "title": "Reisekarte",
        "stats": {
            "photos": len(nav_points),
            "days": len(by_day),
            "date_range": date_range,
        },
        "days": days_meta,
        "points": points_payload,
        "build_meta": {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "script_version": SCRIPT_VERSION,
        },
    }

    html = INDEX_TEMPLATE.render(
        ctx=ctx,
        ctx_json=json.dumps(ctx, ensure_ascii=False),
    )
    output.write_text(html, encoding="utf-8")

    print(f"\n✓ Karte gespeichert: {output.resolve()}")
    print(f"✓ {len(nav_points)} Fotos auf {len(by_day)} Tage verteilt.")
    print("ℹ️  Im Browser: Pfeiltasten ← / → zum Blättern, Leertaste = Auto-Play,")
    print("    oder direkt auf einen Marker klicken.")


def main():
    script_dir = Path(__file__).resolve().parent
    default_folder = script_dir / "fotos"
    output = script_dir / "reisekarte.html"

    if len(sys.argv) > 1:
        folder = Path(sys.argv[1]).resolve()
    else:
        folder = default_folder

    if not folder.is_dir():
        print(f"Ordner nicht gefunden: {folder}")
        print(f"Lege deine Fotos in {default_folder} ab und starte das Skript erneut.")
        sys.exit(1)

    extensions = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".tiff"}
    images = sorted(f for f in folder.rglob("*") if f.suffix.lower() in extensions)
    print(f"Gefundene Bilder: {len(images)}")

    if not images:
        print(f"Keine unterstützten Bilder gefunden. Erlaubte Formate: {', '.join(sorted(extensions))}")
        sys.exit(1)

    points = []
    for i, img in enumerate(images, 1):
        if i % 50 == 0:
            print(f"  ... {i}/{len(images)} verarbeitet")
        if data := get_photo_data(img):
            points.append(data)

    build_map(points, output=output)


if __name__ == "__main__":
    main()
