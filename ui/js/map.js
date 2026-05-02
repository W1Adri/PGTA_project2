/**
 * map.js — Leaflet player for filtered ASTERIX points.
 */

const AppMap = (() => {

  const DEFAULT_CENTER = [41.3851, 2.1734]; // Barcelona city center
  const DEFAULT_ZOOM = 10;
  const REQUEST_DEBOUNCE_MS = 90;
  const MIN_REQUEST_DEBOUNCE_MS = 35;
  const PLAYBACK_TICK_MS = 1000;
  const PLAYBACK_RATES = [1, 5, 10, 30, 60];
  const DEFAULT_WINDOW_SECONDS = 12;
  const MAX_RENDERED_POINTS = 500;
  const PRUNE_MARGIN_SECONDS = 45;
  const REQUEST_TIMEOUT_MS = 12000;
  const HTTP_REQUEST_TIMEOUT_MS = 12000;
  const API_BASE = window.location.origin || "http://127.0.0.1:8888";
  const MAP_DATA_URL = `${API_BASE}/map_data`;
  const MARKER_STALE_SECONDS = 10;
  const UNKNOWN_MARKER_STALE_SECONDS = 3;
  const HIGH_SPEED_TRAIL_MIN_INTERVAL_MS = 220;
  const AIRLINE_PALETTE = [
    "#0ea5e9", "#22c55e", "#f97316", "#e11d48", "#8b5cf6",
    "#14b8a6", "#f59e0b", "#06b6d4", "#84cc16", "#ef4444",
    "#6366f1", "#10b981", "#f43f5e", "#3b82f6", "#a855f7",
  ];

  let leaflet = null;
  let initialized = false;
  let markersLayer = null;
  let trailsLayer = null;
  let requestTimer = null;
  let playbackTimer = null;
  let requestSeq = 0;
  let pendingRequestId = null;
  let pendingRequestTransport = null;
  let pendingRequestTimeoutId = null;
  let currentRequestPayload = null;
  let queuedWindowRequest = false;
  let latestRequestedSeq = 0;
  let lastRenderedRequestSeq = 0;
  let datasetReady = false;
  let hasAdjustedView = false;
  let legendExpanded = false;
  let playbackAccumulator = 0;
  let lastTrailRenderAt = 0;

  const state = {
    playing: false,
    playbackRateIndex: 0,
    playbackDirection: 1,
    currentTime: null,
    minTime: null,
    maxTime: null,
    windowBefore: DEFAULT_WINDOW_SECONDS,
    windowAfter: 0,
    maxPoints: MAX_RENDERED_POINTS,
  };

  const markersById = new Map();
  const airlineColorByCode = new Map();

  function init() {
    if (initialized) return;
    initialized = true;

    leaflet = L.map("map", {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      zoomControl: false,
    });

    L.control.zoom({ position: "topright" }).addTo(leaflet);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(leaflet);

    markersLayer = L.layerGroup().addTo(leaflet);
    trailsLayer = L.layerGroup().addTo(leaflet);

    state.windowBefore = getTrailWindowSeconds(leaflet.getZoom());
    leaflet.on("zoomend", onZoomChanged);

    bindControls();
    setControlsDisabled(true);
    updatePlayerDisplay();
    updateInfoBox({ record_count: 0, time_start: null, time_end: null });

    setTimeout(() => {
      leaflet.invalidateSize();
      leaflet.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    }, 80);
    console.log("[Map] Leaflet initialised.");
  }

  function bindControls() {
    document.getElementById("map-player-toggle")?.addEventListener("click", togglePlayback);
    document.getElementById("map-player-direction")?.addEventListener("click", togglePlaybackDirection);
    document.getElementById("map-player-speed")?.addEventListener("click", cyclePlaybackSpeed);

    const range = document.getElementById("map-player-range");
    if (range) {
      range.addEventListener("input", onRangeInput);
      range.addEventListener("change", onRangeChange);
    }
  }

  function setControlsDisabled(disabled) {
    document.getElementById("map-player-toggle")?.toggleAttribute("disabled", disabled);
    document.getElementById("map-player-direction")?.toggleAttribute("disabled", disabled);
    document.getElementById("map-player-speed")?.toggleAttribute("disabled", disabled);
    const range = document.getElementById("map-player-range");
    if (range) range.toggleAttribute("disabled", disabled);
  }

  function getPlaybackRate() {
    return PLAYBACK_RATES[state.playbackRateIndex] || 1;
  }

  function updatePlaybackTimer() {
    if (playbackTimer) {
      clearInterval(playbackTimer);
      playbackTimer = null;
    }

    if (!state.playing) return;

    const rate = Math.max(1, getPlaybackRate()) * (state.playbackDirection >= 0 ? 1 : -1);
    const tickMs = 50;

    playbackTimer = setInterval(() => {
      if (!Number.isFinite(state.maxTime)) return;

      playbackAccumulator += (rate * tickMs) / PLAYBACK_TICK_MS;
      const stepSeconds = Math.floor(playbackAccumulator);
      if (stepSeconds < 1) return;
      playbackAccumulator -= stepSeconds;

      const next = state.currentTime + (rate >= 0 ? stepSeconds : -stepSeconds);
      if (rate >= 0 && next >= state.maxTime) {
        setCurrentTime(state.maxTime);
        state.playing = false;
        playbackAccumulator = 0;
        updatePlaybackTimer();
        updatePlayerDisplay();
        return;
      }

      if (rate < 0 && Number.isFinite(state.minTime) && next <= state.minTime) {
        setCurrentTime(state.minTime);
        state.playing = false;
        playbackAccumulator = 0;
        updatePlaybackTimer();
        updatePlayerDisplay();
        return;
      }

      setCurrentTime(next);
    }, tickMs);
  }

  function cyclePlaybackSpeed() {
    state.playbackRateIndex = (state.playbackRateIndex + 1) % PLAYBACK_RATES.length;
    playbackAccumulator = 0;
    updatePlayerDisplay();
    if (state.playing) {
      updatePlaybackTimer();
    }
  }

  function togglePlaybackDirection() {
    state.playbackDirection *= -1;
    playbackAccumulator = 0;
    updatePlayerDisplay();
    if (state.playing) {
      updatePlaybackTimer();
    }
  }

  function getTrailWindowSeconds(zoom) {
    const z = Number.isFinite(zoom) ? zoom : DEFAULT_ZOOM;
    const minZoom = 5;
    const maxZoom = 14;
    const minSeconds = 8;
    const maxSeconds = 60;
    const clamped = Math.max(minZoom, Math.min(maxZoom, z));
    const ratio = (maxZoom - clamped) / (maxZoom - minZoom);
    return Math.round(minSeconds + ((ratio * ratio) * (maxSeconds - minSeconds)));
  }

  function onZoomChanged() {
    const nextWindow = getTrailWindowSeconds(leaflet?.getZoom?.());
    if (nextWindow === state.windowBefore) return;
    state.windowBefore = nextWindow;
    if (datasetReady) {
      requestWindowNow();
    }
  }

  function parseTimeToSeconds(value) {
    if (value === null || value === undefined || value === "") return null;
    if (typeof value === "number" && Number.isFinite(value)) return Math.ceil(value);

    const text = String(value).trim();
    if (!text) return null;

    const match = text.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?(?::\d{1,3})?$/);
    if (match) {
      const hour = Number(match[1]);
      const minute = Number(match[2]);
      const second = Number(match[3] || 0);
      if (
        Number.isInteger(hour) && Number.isInteger(minute) && Number.isInteger(second) &&
        hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59 && second >= 0 && second <= 59
      ) {
        return Math.ceil((hour * 3600) + (minute * 60) + second);
      }
    }

    const numeric = Number(text);
    if (Number.isFinite(numeric)) return Math.ceil(numeric);

    const parsed = Date.parse(text);
    if (Number.isFinite(parsed)) return Math.ceil(parsed / 1000);
    return null;
  }

  function formatSeconds(seconds) {
    if (!Number.isFinite(seconds)) return "—";
    const normalized = Math.max(0, Math.floor(seconds)) % 86400;
    const hours = String(Math.floor(normalized / 3600)).padStart(2, "0");
    const minutes = String(Math.floor((normalized % 3600) / 60)).padStart(2, "0");
    const secs = String(normalized % 60).padStart(2, "0");
    return `${hours}:${minutes}:${secs}`;
  }

  function getTimeBounds() {
    return {
      min: state.minTime,
      max: state.maxTime,
      current: state.currentTime,
    };
  }

  function clampTime(seconds) {
    const { min, max } = getTimeBounds();
    const rounded = Number.isFinite(seconds) ? Math.ceil(seconds) : NaN;
    if (!Number.isFinite(rounded)) return min ?? 0;
    if (Number.isFinite(min) && rounded < min) return min;
    if (Number.isFinite(max) && rounded > max) return max;
    return rounded;
  }

  function setCurrentTime(seconds, { silent = false } = {}) {
    const prev = state.currentTime;
    const next = clampTime(seconds);
    state.currentTime = next;

    const jumped = Number.isFinite(prev) && Number.isFinite(next) && Math.abs(next - prev) > 3;
    if (jumped) {
      clearLayers();
    }

    const range = document.getElementById("map-player-range");
    if (range) range.value = String(next);

    updatePlayerDisplay();

    if (!silent) {
      scheduleWindowRequest();
    }
  }

  function updatePlayerDisplay() {
    const label = document.getElementById("map-player-time");
    if (label) {
      label.textContent = Number.isFinite(state.currentTime)
        ? formatSeconds(state.currentTime)
        : "--:--:--";
    }

    const range = document.getElementById("map-player-range");
    if (range) {
      if (Number.isFinite(state.minTime)) range.min = String(state.minTime);
      if (Number.isFinite(state.maxTime)) range.max = String(state.maxTime);
      if (Number.isFinite(state.currentTime)) range.value = String(state.currentTime);
    }

    const toggle = document.getElementById("map-player-toggle");
    if (toggle) {
      const isPlaying = state.playing;
      toggle.textContent = isPlaying ? "❚❚" : "▶";
      toggle.title = isPlaying ? "Pause" : "Play";
      toggle.setAttribute("aria-label", isPlaying ? "Pause" : "Play");
    }

    const speed = document.getElementById("map-player-speed");
    if (speed) {
      const rate = getPlaybackRate();
      speed.textContent = `x${rate}`;
      speed.title = `Playback speed x${rate}`;
      speed.setAttribute("aria-label", `Playback speed x${rate}`);
    }
  }

  function setInfoTimeRange(startSeconds, endSeconds) {
    updateInfoBox({
      record_count: markersById.size,
      time_start: Number.isFinite(startSeconds) ? formatSeconds(startSeconds) : null,
      time_end: Number.isFinite(endSeconds) ? formatSeconds(endSeconds) : null,
    });
  }

  function updateInfoBox({ record_count, time_start, time_end } = {}) {
    const box = document.getElementById("map-info-box");
    if (!box) return;

    box.querySelector("[data-info='count']").textContent = record_count?.toLocaleString() ?? "—";
    box.querySelector("[data-info='t-start']").textContent = time_start ?? "—";
    box.querySelector("[data-info='t-end']").textContent = time_end ?? "—";
  }

  function resetInfoBox() {
    updateInfoBox({ record_count: null, time_start: null, time_end: null });
  }

  function onDataLoaded(meta) {
    if (!initialized) init();

    datasetReady = true;
    state.minTime = parseTimeToSeconds(meta?.time_start);
    state.maxTime = parseTimeToSeconds(meta?.time_end);
    hasAdjustedView = false;
    lastTrailRenderAt = 0;
    state.playbackDirection = 1;

    if (!Number.isFinite(state.currentTime)) {
      state.currentTime = state.minTime ?? 0;
    } else {
      state.currentTime = clampTime(state.currentTime);
    }

    setControlsDisabled(false);
    updatePlayerDisplay();

    const latMin = Number(meta?.lat_min);
    const latMax = Number(meta?.lat_max);
    const lonMin = Number(meta?.lon_min);
    const lonMax = Number(meta?.lon_max);
    // Fit to dataset bounds on each load so map starts near traffic.
    if ([latMin, latMax, lonMin, lonMax].every(Number.isFinite) && leaflet) {
      const bounds = L.latLngBounds([[latMin, lonMin], [latMax, lonMax]]);
      if (bounds.isValid()) {
        leaflet.fitBounds(bounds.pad(0.08), { animate: true, duration: 0.25 });
        hasAdjustedView = true;
      }
    }

    setCurrentTime(state.currentTime, { silent: true });
    requestWindowNow();
  }

  function onFiltersApplied() {
    if (!datasetReady) return;
    requestWindowNow();
  }

  function onPanelVisible() {
    if (!initialized) init();
    else if (leaflet) leaflet.invalidateSize();
  }

  function onSessionCleared() {
    datasetReady = false;
    state.playing = false;
    state.playbackDirection = 1;
    state.currentTime = null;
    state.minTime = null;
    state.maxTime = null;
    state.playbackRateIndex = 0;
    playbackAccumulator = 0;
    hasAdjustedView = false;
    lastTrailRenderAt = 0;
    pendingRequestId = null;
    pendingRequestTransport = null;
    currentRequestPayload = null;
    queuedWindowRequest = false;
    latestRequestedSeq = 0;
    lastRenderedRequestSeq = 0;

    if (playbackTimer) {
      clearInterval(playbackTimer);
      playbackTimer = null;
    }

    if (requestTimer) {
      clearTimeout(requestTimer);
      requestTimer = null;
    }
    if (pendingRequestTimeoutId) {
      clearTimeout(pendingRequestTimeoutId);
      pendingRequestTimeoutId = null;
    }

    markersById.forEach(({ layer }) => {
      try { markersLayer?.removeLayer(layer); } catch {}
    });
    markersById.clear();

    if (leaflet && markersLayer) {
      markersLayer.clearLayers();
    }
    if (leaflet && trailsLayer) {
      trailsLayer.clearLayers();
    }

    setControlsDisabled(true);
    updatePlayerDisplay();
    resetInfoBox();
    updateLegend();
  }

  function scheduleWindowRequest() {
    if (!datasetReady || !Number.isFinite(state.currentTime)) return;

    if (requestTimer) clearTimeout(requestTimer);
    const rate = getPlaybackRate();
    const dynamicDelay = state.playing
      ? Math.max(MIN_REQUEST_DEBOUNCE_MS, Math.floor(REQUEST_DEBOUNCE_MS / Math.max(1, rate)))
      : REQUEST_DEBOUNCE_MS;

    requestTimer = setTimeout(() => {
      requestTimer = null;
      requestWindowNow();
    }, dynamicDelay);
  }

  function requestWindowNow() {
    if (!datasetReady || !Number.isFinite(state.currentTime)) return;
    if (!initialized) init();
    if (!markersLayer) return;

    // Keep one request in-flight to avoid backend queue lag and stale rendering.
    if (pendingRequestId) {
      queuedWindowRequest = true;
      return;
    }

    const requestId = `map_${Date.now()}_${++requestSeq}`;
    latestRequestedSeq = requestSeq;
    const payload = buildWindowPayload(requestId);

    if (!WS.isConnected()) {
      requestWindowHttp(payload, "ws-disconnected");
      return;
    }

    beginPendingRequest(requestId, "ws", payload, REQUEST_TIMEOUT_MS);

    const sent = WS.send(payload);

    if (!sent) {
      finishPendingRequest(requestId, { keepQueued: true });
      requestWindowHttp(payload, "ws-send-failed");
    }
  }

  function getActiveFilters() {
    try {
      if (typeof Filters !== "undefined" && typeof Filters.getActive === "function") {
        return Filters.getActive() || {};
      }
    } catch (err) {
      console.warn("[Map] Could not collect active filters:", err);
    }
    return {};
  }

  function buildWindowPayload(requestId) {
    return {
      action: "get_map_window",
      request_id: requestId,
      current_time: state.currentTime,
      window_before: state.windowBefore,
      window_after: state.windowAfter,
      max_points: state.maxPoints,
      filters: getActiveFilters(),
    };
  }

  function beginPendingRequest(requestId, transport, payload, timeoutMs) {
    if (pendingRequestTimeoutId) clearTimeout(pendingRequestTimeoutId);
    pendingRequestId = requestId;
    pendingRequestTransport = transport;
    currentRequestPayload = payload;
    queuedWindowRequest = false;

    pendingRequestTimeoutId = setTimeout(() => {
      const timedOutPayload = currentRequestPayload;
      const timedOutTransport = pendingRequestTransport;
      finishPendingRequest(requestId, { keepQueued: true });
      if (timedOutTransport === "ws") {
        requestWindowHttp(timedOutPayload, "ws-timeout");
      }
    }, timeoutMs);
  }

  function finishPendingRequest(requestId, { keepQueued = false } = {}) {
    if (requestId && pendingRequestId && requestId !== pendingRequestId) {
      return false;
    }

    if (pendingRequestTimeoutId) {
      clearTimeout(pendingRequestTimeoutId);
      pendingRequestTimeoutId = null;
    }

    const hadQueuedRequest = queuedWindowRequest;
    pendingRequestId = null;
    pendingRequestTransport = null;
    currentRequestPayload = null;
    if (!keepQueued) queuedWindowRequest = false;
    return hadQueuedRequest;
  }

  async function requestWindowHttp(payload, reason) {
    if (!payload || !datasetReady) return;
    if (pendingRequestId) {
      queuedWindowRequest = true;
      return;
    }

    beginPendingRequest(payload.request_id, "http", payload, HTTP_REQUEST_TIMEOUT_MS + 1000);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), HTTP_REQUEST_TIMEOUT_MS);

    try {
      const res = await fetch(MAP_DATA_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_time: payload.current_time,
          window_before: payload.window_before,
          window_after: payload.window_after,
          max_points: payload.max_points,
          filters: payload.filters || getActiveFilters(),
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      data.request_id = payload.request_id;

      const responseSeq = getRequestSeq(payload.request_id);
      if (responseSeq !== null && responseSeq > lastRenderedRequestSeq) {
        lastRenderedRequestSeq = responseSeq;
        renderWindow(data);
      }
    } catch (err) {
      console.warn(`[Map] HTTP fallback failed (${reason}):`, err);
    } finally {
      clearTimeout(timeoutId);
      const shouldRunQueued = finishPendingRequest(payload.request_id);
      if (shouldRunQueued) {
        requestWindowNow();
      }
    }
  }

  function getRequestSeq(requestId) {
    if (typeof requestId !== "string") return null;
    const match = requestId.match(/_(\d+)$/);
    if (!match) return null;
    const seq = Number(match[1]);
    return Number.isInteger(seq) ? seq : null;
  }

  function getRecordKey(record) {
    const trackId = [
      record?.TARGET_IDENTIFICATION,
      record?.callsign,
      record?.TARGET_ADDRESS,
      record?.ICAO,
      record?.MODE_S,
      record?.TRACK_NUMBER,
    ].find(value => value !== null && value !== undefined && String(value).trim() !== "");

    const category = String(record?.CAT || "").toUpperCase();

    if (trackId !== undefined) {
      const baseKey = String(trackId).trim().toUpperCase();
      return category ? `${baseKey}|${category}` : baseKey;
    }

    if (record && record.__row_id !== null && record.__row_id !== undefined) {
      const baseId = String(record.__row_id);
      return category ? `${baseId}|${category}` : baseId;
    }

    const parts = [
      record?.CAT,
      record?.TARGET_IDENTIFICATION,
      record?.callsign,
      record?.TIME,
      record?.LAT,
      record?.LON,
    ].filter(value => value !== null && value !== undefined && String(value).trim() !== "");

    return parts.length ? parts.join("|") : `fallback-${Math.random().toString(16).slice(2)}`;
  }

  function getTargetLabel(record) {
    const raw = String(record?.TARGET_IDENTIFICATION || record?.callsign || "").trim();
    return raw || "Unknown";
  }

  function getAirlineCode(record) {
    const raw = String(record?.TARGET_IDENTIFICATION || record?.callsign || "").trim().toUpperCase();
    const match = raw.match(/^[A-Z]{3}/);
    return match ? match[0] : null;
  }

  function pickAirlineColor(code) {
    if (!code) return null;
    if (airlineColorByCode.has(code)) return airlineColorByCode.get(code);

    let hash = 0;
    for (let i = 0; i < code.length; i += 1) {
      hash = ((hash * 31) + code.charCodeAt(i)) >>> 0;
    }

    const color = AIRLINE_PALETTE[hash % AIRLINE_PALETTE.length];
    airlineColorByCode.set(code, color);
    return color;
  }

  function getHeadingDegrees(record) {
    const candidates = [record?.HEADING, record?.HDG, record?.heading];
    for (const value of candidates) {
      const num = Number(value);
      if (Number.isFinite(num)) {
        const normalized = ((num % 360) + 360) % 360;
        return normalized;
      }
    }
    return null;
  }

  function isFixTransponder(record) {
    const squawk = String(record?.["MODE_3/A"] ?? record?.squawk ?? record?.MODE_3A ?? record?.MODE_3_A ?? "").trim();
    const targetIdentification = String(record?.TARGET_IDENTIFICATION || record?.callsign || "").trim().toUpperCase();
    return squawk === "7777" || targetIdentification.startsWith("7777");
  }

  function buildAircraftIcon(record, color) {
    const heading = getHeadingDegrees(record);
    const directional = Number.isFinite(heading) && !isFixTransponder(record);
    const fixTransponder = isFixTransponder(record);
    const markerClass = fixTransponder
      ? "aircraft-marker fix-transponder"
      : directional
        ? "aircraft-marker directional"
        : "aircraft-marker neutral";
    const rotation = directional ? `transform: rotate(${heading}deg);` : "";
    const glyph = fixTransponder ? "⨯" : directional ? "▲" : "◆";

    return L.divIcon({
      className: "aircraft-marker-wrap",
      html: `<div class="${markerClass}" style="--aircraft-color: ${color}; ${rotation}">${glyph}</div>`,
      iconSize: [22, 22],
      iconAnchor: [10, 10],
      popupAnchor: [0, -10],
      tooltipAnchor: [10, -8],
    });
  }

  function getSensorInfo(record) {
    const category = String(record?.CAT || "").toUpperCase();
    if (category === "CAT048") {
      return { sensorName: "Radar", category: "CAT048", color: "#FF0000" };
    }
    if (category === "CAT021") {
      return { sensorName: "ADSB", category: "CAT021", color: "#0000FF" };
    }
    return { sensorName: "Unknown", category, color: "#808080" };
  }

  function getMarkerColor(record) {
    const sensorInfo = getSensorInfo(record);
    return sensorInfo.color;
  }

  function buildPopupContent(record) {
    const target = record?.TARGET_IDENTIFICATION || record?.callsign || "Unknown target";
    const category = record?.CAT || record?.category || "—";
    const time = formatSeconds(parseTimeToSeconds(record?.TIME ?? record?.__time_seconds));
    const lat = Number(record?.LAT);
    const lon = Number(record?.LON);
    const altitude = record?.FL ?? record?.altitude_ft ?? "—";
    const heading = getHeadingDegrees(record);
    const fixTransponder = isFixTransponder(record);

    return `
      <div class="map-popup">
        <strong>${target}</strong><br>
        TYPE: ${fixTransponder ? "FIX TRANSPONDER" : Number.isFinite(heading) ? "HEADING TRACK" : "UNKNOWN"}<br>
        CAT: ${category}<br>
        TIME: ${time}<br>
        LAT: ${Number.isFinite(lat) ? lat.toFixed(6) : "—"}<br>
        LON: ${Number.isFinite(lon) ? lon.toFixed(6) : "—"}<br>
        FL: ${altitude ?? "—"}
      </div>
    `;
  }

  function upsertMarker(record) {
    const lat = Number(record?.LAT);
    const lon = Number(record?.LON);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;

    const key = getRecordKey(record);
    const timeSeconds = parseTimeToSeconds(record?.TIME ?? record?.__time_seconds);
    const color = getMarkerColor(record);
    const heading = getHeadingDegrees(record);
    const normalizedHeading = Number.isFinite(heading) ? heading : null;
    const airlineCode = getAirlineCode(record) || "UNKNOWN";
    const targetLabel = getTargetLabel(record);
    const popupContent = buildPopupContent(record);

    let entry = markersById.get(key);
    if (!entry) {
      const icon = buildAircraftIcon(record, color);
      const layer = L.marker([lat, lon], { icon });

      layer.addTo(markersLayer);
      const sensorInfo = getSensorInfo(record);
      entry = {
        layer,
        timeSeconds: Number.isFinite(timeSeconds) ? timeSeconds : null,
        lastUpdateSecond: Number.isFinite(timeSeconds) ? timeSeconds : null,
        airlineCode,
        targetLabel,
        color,
        heading: normalizedHeading,
        sensorCategory: sensorInfo.category,
        sensorName: sensorInfo.sensorName,
      };
      markersById.set(key, entry);
      entry.layer.bindPopup(popupContent);
      entry.layer.bindTooltip(targetLabel, { sticky: true });
    } else {
      entry.layer.setLatLng([lat, lon]);

      // Avoid replacing marker icon when visual state hasn't changed.
      const iconNeedsUpdate = entry.color !== color || entry.heading !== normalizedHeading;
      if (iconNeedsUpdate) {
        entry.layer.setIcon(buildAircraftIcon(record, color));
      }

      const sensorInfo = getSensorInfo(record);
      entry.timeSeconds = Number.isFinite(timeSeconds) ? timeSeconds : entry.timeSeconds;
      entry.lastUpdateSecond = Number.isFinite(timeSeconds) ? timeSeconds : entry.lastUpdateSecond;
      entry.airlineCode = airlineCode;
      entry.targetLabel = targetLabel;
      entry.color = color;
      entry.heading = normalizedHeading;
      entry.sensorCategory = sensorInfo.category;
      entry.sensorName = sensorInfo.sensorName;
      if (entry.layer.getPopup()) {
        entry.layer.setPopupContent(popupContent);
      } else {
        entry.layer.bindPopup(popupContent);
      }

      const tooltipText = targetLabel;
      if (entry.layer.getTooltip()) {
        entry.layer.setTooltipContent(tooltipText);
      } else {
        entry.layer.bindTooltip(tooltipText, { sticky: true });
      }
    }
    return key;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function updateLegend() {
    const legend = document.getElementById("map-legend-box");
    if (!legend) return;

    const byAircraftSensor = new Map();
    for (const entry of markersById.values()) {
      const targetLabel = entry?.targetLabel || "Unknown";
      const sensorName = entry?.sensorName || "Unknown";
      const color = entry?.color || "#808080";
      const key = `${targetLabel}|${sensorName}`;
      
      if (!byAircraftSensor.has(key)) {
        byAircraftSensor.set(key, { color, targetLabel, sensorName, count: 0 });
      }
      const bucket = byAircraftSensor.get(key);
      bucket.count += 1;
    }

    const items = [...byAircraftSensor.entries()].sort((a, b) => {
      const aLabel = a[1].targetLabel;
      const bLabel = b[1].targetLabel;
      if (aLabel === bLabel) {
        return a[1].sensorName.localeCompare(b[1].sensorName);
      }
      return aLabel.localeCompare(bLabel);
    });

    const bodyMarkup = items.map(([key, info]) => {
      const displayLabel = `${info.targetLabel} (${info.sensorName})`;
      return `
        <div class="map-legend-item">
          <span class="map-legend-swatch" style="background:${escapeHtml(info.color)}"></span>
          <span class="map-legend-label">${escapeHtml(displayLabel)}</span>
          <span class="map-legend-count">${info.count}</span>
        </div>
      `;
    }).join("");

    const currentFlights = markersById.size;
    legend.innerHTML = `
      <button type="button" class="map-legend-toggle" aria-expanded="${legendExpanded ? "true" : "false"}">
        <span class="map-legend-toggle-icon">${legendExpanded ? "▾" : "▸"}</span>
        <span class="map-legend-toggle-text">Current Flights (${currentFlights})</span>
      </button>
      <div class="map-legend-body${legendExpanded ? " is-open" : ""}">${bodyMarkup}</div>
    `;

    legend.querySelector(".map-legend-toggle")?.addEventListener("click", () => {
      legendExpanded = !legendExpanded;
      updateLegend();
    });
  }

  function pruneMarkers() {
    if (!Number.isFinite(state.currentTime)) return;

    const retainMin = state.currentTime - Math.max(state.windowBefore, PRUNE_MARGIN_SECONDS);
    const retainMax = state.currentTime + Math.max(state.windowAfter, PRUNE_MARGIN_SECONDS);

    for (const [key, entry] of markersById.entries()) {
      const timeSeconds = entry?.timeSeconds;
      if (!Number.isFinite(timeSeconds)) continue;
      if (timeSeconds < retainMin || timeSeconds > retainMax) {
        try { markersLayer?.removeLayer(entry.layer); } catch {}
        markersById.delete(key);
      }
    }
  }

  function renderWindow(data) {
    const records = Array.isArray(data?.records) ? data.records : [];
    const currentSecond = Number.isFinite(state.currentTime) ? state.currentTime : null;
    const playbackRate = getPlaybackRate();
    const highSpeedPlayback = state.playing && playbackRate >= 30;
    const now = Date.now();
    const shouldRenderTrails = !highSpeedPlayback || ((now - lastTrailRenderAt) >= HIGH_SPEED_TRAIL_MIN_INTERVAL_MS);
    const grouped = new Map();

    records.forEach(record => {
      const key = getRecordKey(record);
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(record);
    });

    const activeKeys = new Set();
    if (shouldRenderTrails) {
      trailsLayer?.clearLayers();
      lastTrailRenderAt = now;
    }

    for (const [key, groupRecords] of grouped.entries()) {
      const normalized = groupRecords
        .map(record => {
          const lat = Number(record?.LAT);
          const lon = Number(record?.LON);
          const t = parseTimeToSeconds(record?.__time_seconds ?? record?.TIME);
          if (!Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(t)) {
            return null;
          }
          return { record, lat, lon, t };
        })
        .filter(Boolean)
        .sort((a, b) => a.t - b.t);

      if (!normalized.length) continue;

      let currentIdx = -1;
      if (Number.isFinite(currentSecond)) {
        for (let i = normalized.length - 1; i >= 0; i -= 1) {
          if (normalized[i].t <= currentSecond) {
            currentIdx = i;
            break;
          }
        }
      }
      const currentRecord = currentIdx >= 0 ? normalized[currentIdx] : null;

      if (currentRecord) {
        const markerKey = upsertMarker(currentRecord.record);
        if (markerKey) activeKeys.add(markerKey);
      }

      if (!Number.isFinite(currentSecond) || !shouldRenderTrails) continue;

      const limitIndex = currentRecord ? currentIdx : (normalized.length - 1);
      if (limitIndex <= 0) continue;

      const stride = highSpeedPlayback
        ? (playbackRate >= 60 ? 4 : 2)
        : 1;
      const maxTrailPoints = highSpeedPlayback ? 90 : 220;

      let startIndex = 0;
      const availablePoints = limitIndex + 1;
      if (availablePoints > maxTrailPoints * stride) {
        startIndex = availablePoints - (maxTrailPoints * stride);
      }

      const trailPoints = [];
      for (let i = startIndex; i <= limitIndex; i += stride) {
        trailPoints.push([normalized[i].lat, normalized[i].lon]);
      }
      if (trailPoints.length) {
        const lastPoint = trailPoints[trailPoints.length - 1];
        const endLat = normalized[limitIndex].lat;
        const endLon = normalized[limitIndex].lon;
        if (lastPoint[0] !== endLat || lastPoint[1] !== endLon) {
          trailPoints.push([endLat, endLon]);
        }
      }

      if (trailPoints.length >= 2) {
        const trailColor = getMarkerColor(currentRecord?.record || normalized[normalized.length - 1].record);
        L.polyline(trailPoints, {
          color: trailColor,
          weight: 5,
          opacity: 0.45,
          lineCap: "round",
          lineJoin: "round",
        }).addTo(trailsLayer);
      }
    }

    pruneMarkers();

    for (const [key, entry] of markersById.entries()) {
      if (activeKeys.has(key)) continue;

      const age = Number.isFinite(currentSecond) && Number.isFinite(entry?.lastUpdateSecond)
        ? (currentSecond - entry.lastUpdateSecond)
        : 0;
      const isUnknown = String(entry?.airlineCode || "").trim().toUpperCase() === "UNKNOWN";
      const staleSeconds = isUnknown ? UNKNOWN_MARKER_STALE_SECONDS : MARKER_STALE_SECONDS;

      if (Number.isFinite(age) && age <= staleSeconds) {
        continue;
      }

      try { markersLayer?.removeLayer(entry.layer); } catch {}
      markersById.delete(key);
    }

    updatePlayerDisplay();
    setInfoTimeRange(data?.window_start_seconds, data?.window_end_seconds);
    updateLegend();

    if (!hasAdjustedView && markersById.size > 0 && leaflet) {
      const group = L.featureGroup([...markersById.values()].map(entry => entry.layer));
      const bounds = group.getBounds();
      if (bounds.isValid()) {
        leaflet.fitBounds(bounds.pad(0.12), { animate: true, duration: 0.2 });
        hasAdjustedView = true;
      }
    }
  }

  function onMapWindow(payload) {
    if (!initialized) init();
    if (!markersLayer) return;

    const data = payload?.data || {};
    const responseSeq = getRequestSeq(data.request_id);

    if (payload?.status && payload.status !== "ok") {
      const fallbackPayload = currentRequestPayload || buildWindowPayload(data.request_id || `map_${Date.now()}_${++requestSeq}`);
      finishPendingRequest(data.request_id, { keepQueued: true });
      requestWindowHttp(fallbackPayload, "ws-error");
      return;
    }

    // Ignore responses older than the last one we already rendered.
    if (responseSeq !== null && responseSeq <= lastRenderedRequestSeq) {
      if (pendingRequestId && data.request_id === pendingRequestId) {
        const shouldRunQueued = finishPendingRequest(data.request_id, { keepQueued: true });
        if (shouldRunQueued) {
          requestWindowNow();
        }
      }
      return;
    }

    if (responseSeq !== null) {
      lastRenderedRequestSeq = responseSeq;
    }

    const shouldRunQueued = pendingRequestId && data.request_id === pendingRequestId
      ? finishPendingRequest(data.request_id)
      : queuedWindowRequest;

    renderWindow(data);

    if (shouldRunQueued) {
      requestWindowNow();
    }
  }

  function onWsStatus(evt) {
    const stateValue = evt?.detail?.state;
    if (!datasetReady) return;

    if (stateValue === "disconnected") {
      if (pendingRequestId && pendingRequestTransport === "ws") {
        const fallbackPayload = currentRequestPayload;
        finishPendingRequest(pendingRequestId, { keepQueued: true });
        requestWindowHttp(fallbackPayload, "ws-disconnected");
      }
      return;
    }

    if (stateValue === "connected" && !pendingRequestId) {
      scheduleWindowRequest();
    }
  }

  function onRangeInput(evt) {
    const value = Number(evt?.target?.value);
    if (!Number.isFinite(value)) return;
    setCurrentTime(value);
  }

  function onRangeChange(evt) {
    const value = Number(evt?.target?.value);
    if (!Number.isFinite(value)) return;
    setCurrentTime(value);
  }

  function togglePlayback() {
    if (!datasetReady || !Number.isFinite(state.currentTime)) return;

    state.playing = !state.playing;
    updatePlayerDisplay();

    updatePlaybackTimer();
  }

  function clearLayers() {
    markersById.forEach(({ layer }) => {
      try { markersLayer?.removeLayer(layer); } catch {}
    });
    markersById.clear();
    trailsLayer?.clearLayers();
    updateLegend();
  }

  function setup() {
    window.addEventListener("asterix:loaded", e => onDataLoaded(e.detail));
    window.addEventListener("asterix:filters-applied", onFiltersApplied);
    window.addEventListener("asterix:session-cleared", onSessionCleared);
    window.addEventListener("asterix:ws-status", onWsStatus);
    WS.on("map_window_result", onMapWindow);
  }

  return { setup, init, onPanelVisible, clearLayers };

})();

document.addEventListener("DOMContentLoaded", () => AppMap.setup());
