/**
 * filters.js
 * Manages sidebar filter controls.
 * Collects values → sends { action: "apply_filters", ...filters } via WS.
 * Listens to "asterix:loaded" to populate controls from file metadata.
 */

const Filters = (() => {

  // ── Collect current filter values from the DOM ────────────────────────────
  function collect() {
    return {
      time_start  : val("f-time-start")  || null,
      time_end    : val("f-time-end")    || null,
      altitude_min: num("f-alt-min"),
      altitude_max: num("f-alt-max"),
      callsigns   : getTagValues("f-callsign-tags") || null,
      categories  : getChecked("f-categories")      || null,
      squawks     : parseSquawks(val("f-squawk")),
    };
  }

  function getActive() { return collect(); }

  // ── Send filters to backend ───────────────────────────────────────────────
  function applyFilters() {
    const raw     = collect();
    const payload = { action: "apply_filters" };

    // Strip nulls so the backend receives only active filters
    Object.entries(raw).forEach(([k, v]) => {
      if (v !== null && v !== undefined) payload[k] = v;
    });

    if (!WS.send(payload)) {
      console.warn("[Filters] WS not ready.");
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────────
  function resetFilters() {
    ["f-time-start","f-time-end","f-alt-min","f-alt-max","f-squawk"]
      .forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });

    document.querySelectorAll("[data-filter-group='f-categories']")
      .forEach(cb => { cb.checked = true; });

    clearTags("f-callsign-tags");
    updateBadge();
  }

  // ── Populate from file metadata ───────────────────────────────────────────
  function onDataLoaded(meta) {
    if (meta.time_start) {
      const el = document.getElementById("f-time-start");
      if (el) el.value = toDatetimeLocal(meta.time_start);
    }
    if (meta.time_end) {
      const el = document.getElementById("f-time-end");
      if (el) el.value = toDatetimeLocal(meta.time_end);
    }

    if (meta.altitude_min != null) {
      const el = document.getElementById("f-alt-min");
      if (el) el.placeholder = Math.round(meta.altitude_min);
    }
    if (meta.altitude_max != null) {
      const el = document.getElementById("f-alt-max");
      if (el) el.placeholder = Math.round(meta.altitude_max);
    }

    const container = document.getElementById("f-categories-container");
    if (container && meta.unique_categories?.length) {
      container.innerHTML = "";
      meta.unique_categories.forEach(cat => {
        container.insertAdjacentHTML("beforeend", `
          <label class="filter-check-item">
            <input type="checkbox" data-filter-group="f-categories" value="${cat}" checked>
            <span class="filter-check-label">${cat}</span>
          </label>`);
      });
    }

    updateBadge();
  }

  // ── Active filter badge ───────────────────────────────────────────────────
  function updateBadge() {
    const f = collect();
    let n = 0;
    if (f.time_start) n++;
    if (f.time_end)   n++;
    if (f.altitude_min !== null) n++;
    if (f.altitude_max !== null) n++;
    if (f.callsigns?.length)  n++;
    if (f.categories?.length) n++;
    if (f.squawks?.length)    n++;

    const pill = document.getElementById("filter-active-count");
    if (pill) { pill.textContent = n; pill.style.display = n > 0 ? "inline-flex" : "none"; }
  }

  // ── Collapsible sections ──────────────────────────────────────────────────
  function initSections() {
    document.querySelectorAll(".sidebar-section-header").forEach(h => {
      h.addEventListener("click", () =>
        h.closest(".sidebar-section").classList.toggle("collapsed"));
    });
  }

  // ── Tag input ─────────────────────────────────────────────────────────────
  function initTagInput(wrapperId, inputId) {
    const wrapper = document.getElementById(wrapperId);
    const input   = document.getElementById(inputId);
    if (!wrapper || !input) return;

    input.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        const v = input.value.trim().toUpperCase().replace(/,/g,"");
        if (v) addTag(wrapperId, v);
        input.value = "";
        updateBadge();
      }
      if (e.key === "Backspace" && !input.value) {
        const tags = wrapper.querySelectorAll(".filter-tag");
        if (tags.length) { tags[tags.length-1].remove(); updateBadge(); }
      }
    });

    wrapper.addEventListener("click", () => input.focus());
  }

  function addTag(wrapperId, value) {
    const wrapper = document.getElementById(wrapperId);
    const input   = wrapper?.querySelector("input");
    if (!wrapper || !input) return;

    const existing = [...wrapper.querySelectorAll(".filter-tag")].map(t => t.dataset.value);
    if (existing.includes(value)) return;

    const tag = document.createElement("span");
    tag.className     = "filter-tag";
    tag.dataset.value = value;
    tag.innerHTML     = `${value}<span class="filter-tag-remove">&times;</span>`;
    tag.querySelector(".filter-tag-remove").addEventListener("click", e => {
      e.stopPropagation(); tag.remove(); updateBadge();
    });
    wrapper.insertBefore(tag, input);
  }

  function getTagValues(wrapperId) {
    const w = document.getElementById(wrapperId);
    if (!w) return null;
    const v = [...w.querySelectorAll(".filter-tag")].map(t => t.dataset.value);
    return v.length ? v : null;
  }

  function clearTags(wrapperId) {
    document.getElementById(wrapperId)?.querySelectorAll(".filter-tag").forEach(t => t.remove());
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  const val = id => document.getElementById(id)?.value?.trim() ?? "";
  const num = id => { const v = parseFloat(document.getElementById(id)?.value); return isNaN(v) ? null : v; };

  function getChecked(group) {
    const v = [...document.querySelectorAll(`[data-filter-group="${group}"]:checked`)].map(c => c.value);
    return v.length ? v : null;
  }

  function parseSquawks(raw) {
    if (!raw) return null;
    const v = raw.split(",").map(s => s.trim()).filter(Boolean);
    return v.length ? v : null;
  }

  function toDatetimeLocal(iso) {
    try { return new Date(iso).toISOString().slice(0,16); } catch { return ""; }
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    initSections();
    initTagInput("f-callsign-tags", "f-callsign-input");

    document.getElementById("btn-apply-filters")
      ?.addEventListener("click", applyFilters);

    document.getElementById("btn-reset-filters")
      ?.addEventListener("click", resetFilters);

    document.getElementById("sidebar")
      ?.addEventListener("change", updateBadge);
    document.getElementById("sidebar")
      ?.addEventListener("input",  updateBadge);

    window.addEventListener("asterix:loaded", e => onDataLoaded(e.detail));
  }

  return { init, getActive, applyFilters, resetFilters };

})();

document.addEventListener("DOMContentLoaded", () => Filters.init());
