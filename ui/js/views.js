/**
 * views.js
 * Switches between the Map and Table view panels.
 * Calls Map.onPanelVisible() when the map becomes active so Leaflet
 * can recalculate its container size.
 */

const Views = (() => {

  let current = "table";
  let appReady = false;

  function setShellState(ready) {
    appReady = ready;
    document.body.classList.toggle("app-ready", ready);
  }

  function switchTo(view) {
    if (!appReady) return;
    if (view === current) return;
    current = view;

    document.querySelectorAll(".view-panel").forEach(p =>
      p.classList.toggle("active", p.dataset.view === view));

    document.querySelectorAll(".view-btn").forEach(b =>
      b.classList.toggle("active", b.dataset.view === view));

    if (view === "map") AppMap.onPanelVisible();
  }

  function onProcessingEnd(evt) {
    const ok = !!evt?.detail?.success;
    if (!ok) return;

    setShellState(true);
    switchTo("table");
  }

  function init() {
    setShellState(false);

    // Set initial states
    document.querySelectorAll(".view-panel").forEach(p =>
      p.classList.toggle("active", p.dataset.view === current));

    document.querySelectorAll(".view-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.view === current);
      b.addEventListener("click", () => switchTo(b.dataset.view));
    });

    window.addEventListener("asterix:processing-end", onProcessingEnd);
  }

  return { init, switchTo, current: () => current, isReady: () => appReady };

})();

document.addEventListener("DOMContentLoaded", () => Views.init());
