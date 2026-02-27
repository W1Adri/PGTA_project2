/**
 * table.js — always shows the table structure with placeholder rows until data loads.
 */

const Table = (() => {

  let allRows = [];

  const COLUMNS = [
    { key: "timestamp",    label: "Timestamp",  cls: "" },
    { key: "track_number", label: "Track #",    cls: "" },
    { key: "callsign",     label: "Callsign",   cls: "col-callsign" },
    { key: "squawk",       label: "Squawk",     cls: "col-squawk" },
    { key: "category",     label: "Category",   cls: "col-category" },
    { key: "latitude",     label: "Lat",        cls: "" },
    { key: "longitude",    label: "Lon",        cls: "" },
    { key: "altitude_ft",  label: "Alt (ft)",   cls: "col-altitude" },
    { key: "ground_speed", label: "GS (kts)",   cls: "" },
    { key: "heading",      label: "HDG",        cls: "" },
    { key: "data_source",  label: "Source",     cls: "" },
  ];

  const PLACEHOLDER_ROWS = 10;

  // ── Header ────────────────────────────────────────────────────────────────
  function buildHeader() {
    const tr = document.querySelector("#data-table thead tr");
    if (!tr) return;
    tr.innerHTML = COLUMNS.map(c =>
      `<th data-key="${c.key}">${c.label}</th>`
    ).join("");
  }

  // ── Placeholder rows ──────────────────────────────────────────────────────
  function buildPlaceholderRows() {
    const tbody = document.querySelector("#data-table tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    for (let i = 0; i < PLACEHOLDER_ROWS; i++) {
      const tr = document.createElement("tr");
      tr.classList.add("placeholder-row");
      COLUMNS.forEach(() => {
        const td = document.createElement("td");
        const bar = document.createElement("span");
        bar.className = "placeholder-bar";
        td.appendChild(bar);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }

    updateFooter(0, true);
  }

  // ── Render records ────────────────────────────────────────────────────────
  function renderRecords(records) {
    // TODO: implement after data integration
    // allRows = records;
    // const tbody = document.querySelector("#data-table tbody");
    // tbody.innerHTML = "";
    // records.forEach(r => {
    //   const tr = document.createElement("tr");
    //   COLUMNS.forEach(col => {
    //     const td = document.createElement("td");
    //     td.className   = col.cls;
    //     td.textContent = formatCell(col.key, r[col.key]);
    //     tr.appendChild(td);
    //   });
    //   tbody.appendChild(tr);
    // });
    // updateFooter(records.length, false);
    console.log(`[Table] renderRecords — ${records.length} records (not yet implemented)`);
  }

  function clearRows() {
    document.querySelector("#data-table tbody").innerHTML = "";
    allRows = [];
  }

  // ── Quick search ──────────────────────────────────────────────────────────
  function initQuickSearch() {
    const input = document.getElementById("table-search");
    if (!input) return;
    input.addEventListener("input", () => {
      const q    = input.value.trim().toLowerCase();
      const rows = document.querySelectorAll("#data-table tbody tr:not(.placeholder-row)");
      let vis = 0;
      rows.forEach(row => {
        const show = !q || row.textContent.toLowerCase().includes(q);
        row.style.display = show ? "" : "none";
        if (show) vis++;
      });
      const foot = document.getElementById("table-row-count");
      if (foot && allRows.length) {
        foot.innerHTML = q
          ? `Showing <span>${vis.toLocaleString()}</span> of <span>${allRows.length.toLocaleString()}</span> records`
          : `<span>${allRows.length.toLocaleString()}</span> records`;
      }
    });
  }

  // ── Footer ────────────────────────────────────────────────────────────────
  function updateFooter(n, isPlaceholder = false) {
    const el = document.getElementById("table-row-count");
    if (!el) return;
    el.innerHTML = isPlaceholder
      ? `<span style="color:var(--text-dim)">Load a file to populate the table</span>`
      : `<span>${n.toLocaleString()}</span> records`;
  }

  // ── WS handlers ───────────────────────────────────────────────────────────
  function onFilterResult(payload) {
    if (payload.status !== "ok") return;
    renderRecords(payload.data?.records ?? []);
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    buildHeader();
    buildPlaceholderRows();
    initQuickSearch();

    // Always show the table — hide the empty state div
    const empty  = document.getElementById("table-empty");
    const scroll = document.querySelector(".table-scroll");
    if (empty)  empty.style.display  = "none";
    if (scroll) scroll.style.display = "block";

    WS.on("apply_filters_result", onFilterResult);
    WS.on("get_all_result",       onFilterResult);

    window.addEventListener("asterix:loaded", () => updateFooter(0, false));
  }

  return { init, renderRecords, clearRows };

})();

document.addEventListener("DOMContentLoaded", () => Table.init());
