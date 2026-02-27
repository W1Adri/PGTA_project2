/**
 * views.js
 * Switches between the Map and Table view panels.
 * Calls Map.onPanelVisible() when the map becomes active so Leaflet
 * can recalculate its container size.
 */

const Views = (() => {

  let current = "map";

  function switchTo(view) {
    if (view === current) return;
    current = view;

    document.querySelectorAll(".view-panel").forEach(p =>
      p.classList.toggle("active", p.dataset.view === view));

    document.querySelectorAll(".view-btn").forEach(b =>
      b.classList.toggle("active", b.dataset.view === view));

    if (view === "map") Map.onPanelVisible();
  }

  function init() {
    // Set initial states
    document.querySelectorAll(".view-panel").forEach(p =>
      p.classList.toggle("active", p.dataset.view === current));

    document.querySelectorAll(".view-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.view === current);
      b.addEventListener("click", () => switchTo(b.dataset.view));
    });

    // Map is the default — init immediately
    Map.init();
  }

  return { init, switchTo, current: () => current };

})();

document.addEventListener("DOMContentLoaded", () => Views.init());
