/**
 * map.js — always visible, centred on Barcelona by default.
 */

const Map = (() => {

  let leaflet     = null;
  let initialized = false;

  const DEFAULT_CENTER = [41.297, 2.078];
  const DEFAULT_ZOOM   = 8;

  function init() {
    if (initialized) return;
    initialized = true;

    leaflet = L.map("map", {
      center     : DEFAULT_CENTER,
      zoom       : DEFAULT_ZOOM,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom    : 18,
    }).addTo(leaflet);

    // Placeholder marker — LEBL airport
    L.marker([41.2974, 2.0833])
      .addTo(leaflet)
      .bindTooltip("LEBL — Barcelona El Prat", { permanent: false })
      .bindPopup("<b>LEBL</b><br>Barcelona El Prat International Airport");

    setTimeout(() => leaflet.invalidateSize(), 80);
    console.log("[Map] Leaflet initialised.");
  }

  function updateInfoBox({ record_count, time_start, time_end } = {}) {
    const box = document.getElementById("map-info-box");
    if (!box) return;
    const fmt = iso => iso
      ? new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " Z"
      : "—";
    box.querySelector("[data-info='count']")  .textContent = record_count?.toLocaleString() ?? "—";
    box.querySelector("[data-info='t-start']").textContent = fmt(time_start);
    box.querySelector("[data-info='t-end']")  .textContent = fmt(time_end);
  }

  function onDataLoaded(meta) {
    updateInfoBox(meta);
    if (leaflet) setTimeout(() => leaflet.invalidateSize(), 50);
  }

  function onPanelVisible() {
    if (!initialized) init();
    else if (leaflet) leaflet.invalidateSize();
  }

  // TODO: implement when data integration is ready
  function renderRecords(records) {
    console.log(`[Map] renderRecords — ${records.length} records (not yet implemented)`);
  }

  function clearLayers() {
    console.log("[Map] clearLayers (not yet implemented)");
  }

  function setup() {
    window.addEventListener("asterix:loaded", e => onDataLoaded(e.detail));
  }

  return { setup, init, onPanelVisible, renderRecords, clearLayers };

})();

document.addEventListener("DOMContentLoaded", () => Map.setup());
