/**
 * table.js — AG Grid integration for server-side pagination (Infinite Row Model).
 */

const Table = (() => {

  let gridApi = null;
  const API_URL = "http://127.0.0.1:8888/table_data";

  // ── AG Grid Datasource ──────────────────────────────────────────────────
  const datasource = {
    getRows: async (params) => {
      // Show loading overlay
      if (gridApi) gridApi.showLoadingOverlay();

      try {
        // Get active filters from sidebar
        const filters = typeof Filters !== "undefined" ? Filters.getActive() : {};

        // Extract sort info if available
        let sortCol = null;
        let sortDir = null;
        if (params.sortModel && params.sortModel.length > 0) {
           sortCol = params.sortModel[0].colId;
           sortDir = params.sortModel[0].sort;
        }

        const requestBody = {
          startRow: params.startRow,
          endRow: params.endRow,
          sortCol: sortCol,
          sortDir: sortDir,
          filters: filters
        };

        const response = await fetch(API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
          throw new Error("Network response was not ok");
        }

        const data = await response.json();
        
        // Hide loading
        if (gridApi) gridApi.hideOverlay();

        // Pass results to AG Grid
        params.successCallback(data.records || [], data.count);

        // Update custom footer
        updateFooter(data.count, false);

      } catch (error) {
        console.error("Error fetching paginated data:", error);
        if (gridApi) gridApi.hideOverlay();
        params.failCallback();
      }
    }
  };

  // ── Initialization ────────────────────────────────────────────────────────
  function initGrid(columns = []) {
    const gridDiv = document.querySelector('#myGrid');
    if (!gridDiv) return;

    gridDiv.innerHTML = ""; // Clear existing grid if any
    
    // Map data columns to AG Grid format
    const columnDefs = columns.map(col => ({
      field: col,
      headerName: col,
      sortable: true,
      filter: false, // We use sidebar filtering
      minWidth: 120,
      resizable: true,
      valueFormatter: (params) => {
          return (params.value === null || params.value === undefined) ? "—" : params.value;
      }
    }));

    // If no columns, show placeholder
    if (columnDefs.length === 0) {
      columnDefs.push({ headerName: "No Data", field: "empty" });
    }

    const gridOptions = {
      columnDefs: columnDefs,
      rowModelType: 'infinite',
      cacheBlockSize: 100, // Fetch 100 rows at a time
      maxBlocksInCache: 10,  // Keep up to 1000 rows in DOM
      datasource: datasource,
      rowSelection: 'single',
      overlayLoadingTemplate: '<span class="ag-overlay-loading-center">Cargando datos...</span>',
      overlayNoRowsTemplate: '<span class="ag-overlay-loading-center">Sin resultados</span>',
      defaultColDef: {
        flex: 1, // Automatically expand columns to fit width
        minWidth: 100
      }
    };

    gridApi = agGrid.createGrid(gridDiv, gridOptions);
    updateFooter(0, true);
  }

  // ── Footer ────────────────────────────────────────────────────────────────
  function updateFooter(n, isPlaceholder = false) {
    const el = document.getElementById("table-row-count");
    if (!el) return;
    el.innerHTML = isPlaceholder
      ? `<span style="color:var(--text-dim)">Load a file to populate the table</span>`
      : `<span>${(n || 0).toLocaleString()}</span> filtered records`;
  }

  // ── Actions ───────────────────────────────────────────────────────────────
  
  function refreshGrid() {
    if (gridApi) {
      gridApi.purgeInfiniteCache(); // Forces datasource.getRows to trigger again
    }
  }

  // ── Event Handlers ────────────────────────────────────────────────────────
  
  // When file is uploaded and metadata is available, we setup columns and grid
  function onDataLoaded(meta) {
      const columns = meta.columns || [];
      if (gridApi) {
          gridApi.destroy();
      }
      initGrid(columns);
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    initGrid([]); // Start with empty placeholder Grid

    // Always show the table wrapper — hide the empty state div if it existed
    const empty  = document.getElementById("table-empty");
    const scroll = document.querySelector(".table-scroll");
    if (empty)  empty.style.display  = "none";
    if (scroll) scroll.style.display = "block";

    // 1. Listen for initial file load to discover columns
    window.addEventListener("asterix:loaded", (e) => onDataLoaded(e.detail));

    // 2. Listen for "apply_filters" button to trigger refresh
    const applyBtn = document.getElementById("btn-apply-filters");
    if (applyBtn) {
        applyBtn.addEventListener("click", () => {
            // Wait slightly for standard Filters logic to update states if needed
            setTimeout(refreshGrid, 50); 
        });
    }

    // 3. WS fallback if WS pushes "apply_filters_result" (optional, but good for map sync)
    // WS.on("apply_filters_result", refreshGrid);
  }

  return { init, refreshGrid };

})();

document.addEventListener("DOMContentLoaded", () => Table.init());
