/**
 * table.js — AG Grid integration using websocket windowed streaming.
 */

const Table = (() => {

  let gridApi = null;
  let cacheGeneration = 0;
  let requestSeq = 0;
  let lastKnownTotalCount = 0;
  let hasDatasetLoaded = false;
  let isProcessing = false;
  let pendingRequests = new Map();
  let rowCache = new Map(); // absolute_row_index -> row data

  const BLOCK_SIZE = 100;
  const WINDOW_MARGIN = 400;
  const RETAIN_MARGIN = 1000;
  const REQUEST_TIMEOUT_MS = 8000;

  function nextRequestId() {
    requestSeq += 1;
    return `table_${cacheGeneration}_${requestSeq}`;
  }

  function clearCache() {
    const staleRequests = [...pendingRequests.values()];
    staleRequests.forEach((pending) => {
      if (pending.timeoutId) clearTimeout(pending.timeoutId);
    });
    rowCache.clear();
    pendingRequests.clear();
    lastKnownTotalCount = 0;
    cacheGeneration += 1;

    staleRequests.forEach((pending) => {
      try {
        pending.failCallback();
      } catch {
        // Ignore datasource callback failures during cache invalidation.
      }
    });
  }

  function hasCachedRange(startRow, endRow) {
    const limit = lastKnownTotalCount > 0
      ? Math.min(endRow, lastKnownTotalCount)
      : endRow;
    for (let i = startRow; i < limit; i += 1) {
      if (!rowCache.has(i)) return false;
    }
    return true;
  }

  function buildRowsFromCache(startRow, endRow) {
    const rows = [];
    const limit = lastKnownTotalCount > 0
      ? Math.min(endRow, lastKnownTotalCount)
      : endRow;
    for (let i = startRow; i < limit; i += 1) {
      rows.push(rowCache.get(i) || null);
    }
    return rows;
  }

  function pruneCache(keepStart, keepEnd) {
    const minKeep = Math.max(0, keepStart - RETAIN_MARGIN);
    const maxKeep = keepEnd + RETAIN_MARGIN;

    for (const idx of rowCache.keys()) {
      if (idx < minKeep || idx >= maxKeep) {
        rowCache.delete(idx);
      }
    }
  }

  function getSortFromParams(params) {
    if (params.sortModel && params.sortModel.length > 0) {
      return {
        sortCol: params.sortModel[0].colId,
        sortDir: params.sortModel[0].sort,
      };
    }
    return { sortCol: null, sortDir: null };
  }

  function requestWindow(params) {
    const startRow = params.startRow;
    const endRow = params.endRow;
    const { sortCol, sortDir } = getSortFromParams(params);
    const requestId = nextRequestId();

    pendingRequests.set(requestId, {
      generation: cacheGeneration,
      startRow,
      endRow,
      successCallback: params.successCallback,
      failCallback: params.failCallback,
      timeoutId: setTimeout(() => {
        const stale = pendingRequests.get(requestId);
        if (!stale) return;
        pendingRequests.delete(requestId);
        stale.failCallback();
        if (gridApi) {
          gridApi.setGridOption("loading", false);
          updateFooter(0, false);
          gridApi.showNoRowsOverlay();
        }
      }, REQUEST_TIMEOUT_MS),
    });

    const sent = WS.send({
      action: "get_table_window",
      request_id: requestId,
      startRow,
      endRow,
      margin: WINDOW_MARGIN,
      sortCol,
      sortDir,
    });

    if (!sent) {
      const pending = pendingRequests.get(requestId);
      if (pending?.timeoutId) clearTimeout(pending.timeoutId);
      pendingRequests.delete(requestId);
      params.failCallback();
      if (gridApi) {
        gridApi.setGridOption("loading", false);
        updateFooter(0, false);
        gridApi.showNoRowsOverlay();
      }
    }
  }

  function onTableWindow(payload) {
    const data = payload?.data || {};
    const requestId = data.request_id;
    if (!requestId || !pendingRequests.has(requestId)) return;

    const pending = pendingRequests.get(requestId);
    if (pending?.timeoutId) clearTimeout(pending.timeoutId);
    pendingRequests.delete(requestId);

    if (pending.generation !== cacheGeneration) return;

    const windowStart = data.window_start || 0;
    const records = data.records || [];
    const totalCount = data.total_count || 0;
    lastKnownTotalCount = totalCount;

    if (totalCount === 0) {
      pending.successCallback([], 0);
      updateFooter(0, false);
      if (gridApi) gridApi.setGridOption("loading", false);
      return;
    }

    records.forEach((row, offset) => {
      rowCache.set(windowStart + offset, row);
    });

    pruneCache(pending.startRow, pending.endRow);

    if (!hasCachedRange(pending.startRow, pending.endRow)) {
      pending.failCallback();
      if (gridApi) gridApi.setGridOption("loading", false);
      return;
    }

    const rows = buildRowsFromCache(pending.startRow, pending.endRow);
    pending.successCallback(rows, totalCount);

    updateFooter(totalCount, false);
    if (gridApi) gridApi.setGridOption("loading", false);
  }

  // ── AG Grid Datasource ──────────────────────────────────────────────────
  const datasource = {
    getRows: (params) => {
      if (!hasDatasetLoaded) {
        params.successCallback([], 0);
        if (gridApi) {
          gridApi.setGridOption("loading", false);
          updateFooter(0, true);
          gridApi.showNoRowsOverlay();
        }
        return;
      }

      if (gridApi) gridApi.setGridOption("loading", true);

      if (hasCachedRange(params.startRow, params.endRow)) {
        const rows = buildRowsFromCache(params.startRow, params.endRow);
        params.successCallback(rows, lastKnownTotalCount);
        if (gridApi) gridApi.setGridOption("loading", false);
        return;
      }

      requestWindow(params);
    }
  };

  // ── Initialization ────────────────────────────────────────────────────────
  function initGrid(columns = []) {
    const gridDiv = document.querySelector('#myGrid');
    if (!gridDiv) return;

    gridDiv.innerHTML = ""; // Clear existing grid if any
    
    const rowNumberCol = {
      headerName: "#",
      colId: "row_number",
      width: 80,
      minWidth: 70,
      maxWidth: 100,
      pinned: "left",
      sortable: false,
      filter: false,
      resizable: false,
      suppressMovable: true,
      valueGetter: (params) => (params?.node?.rowIndex ?? 0) + 1,
      cellClass: "table-row-index",
    };

    // Map data columns to AG Grid format
    const dataColumnDefs = columns.map(col => ({
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

    const columnDefs = [rowNumberCol, ...dataColumnDefs];

    // If no columns, show placeholder
    if (dataColumnDefs.length === 0) {
      columnDefs.push({ headerName: "No Data", field: "empty" });
    }

    const gridOptions = {
      columnDefs: columnDefs,
      rowModelType: 'infinite',
      cacheBlockSize: BLOCK_SIZE,
      maxBlocksInCache: 10,
      datasource: datasource,
      rowSelection: undefined,
      suppressRowClickSelection: true,
      loading: false,
      overlayLoadingTemplate: '<span class="ag-overlay-loading-center">Loading messages...</span>',
      overlayNoRowsTemplate: '<span class="ag-overlay-loading-center">No messages to display</span>',
      defaultColDef: {
        flex: 1, // Automatically expand columns to fit width
        minWidth: 100,
        cellStyle: { textAlign: "center" },
        headerClass: "table-header-centered"
      }
    };

    gridApi = agGrid.createGrid(gridDiv, gridOptions);
    updateFooter(0, true);
  }

  // ── Footer ────────────────────────────────────────────────────────────────
  function updateFooter(n, isPlaceholder = false) {
    const el = document.getElementById("table-row-count");
    if (!el) return;

    if (isPlaceholder) {
      const message = isProcessing
        ? "Processing uploaded file... messages will appear soon"
        : "No file uploaded yet. Upload a file to display messages";
      el.innerHTML = `<span style="color:var(--text-dim)">${message}</span>`;
      return;
    }

    el.innerHTML = isPlaceholder
      ? `<span style="color:var(--text-dim)">No file uploaded yet. Upload a file to display messages</span>`
      : `<span>${(n || 0).toLocaleString()}</span> filtered messages`;
  }

  function setProcessingFooter(message) {
    const el = document.getElementById("table-row-count");
    if (!el) return;

    el.innerHTML = `<span style="color:var(--text-dim)">${message}</span>`;
  }

  // ── Actions ───────────────────────────────────────────────────────────────
  
  function refreshGrid() {
    clearCache();
    if (gridApi) gridApi.purgeInfiniteCache();
  }

  // ── Event Handlers ────────────────────────────────────────────────────────
  
  // When file is uploaded and metadata is available, we setup columns and grid
  function onDataLoaded(meta) {
      const columns = meta.columns || [];
      isProcessing = false;
      hasDatasetLoaded = true;
      clearCache();
      if (gridApi) {
          gridApi.destroy();
      }
      initGrid(columns);
      refreshGrid();
  }

  function onProcessingStart() {
    isProcessing = true;
    hasDatasetLoaded = false;
    clearCache();
    if (gridApi) {
      gridApi.setGridOption("loading", true);
      updateFooter(0, true);
    }
    setProcessingFooter("Processing uploaded file... 0%");
  }

  function onProcessingProgress(evt) {
    if (!isProcessing) return;

    const data = evt?.detail || {};
    const stage = data.stage || "Processing uploaded file";
    const percent = Number(data.percent ?? 0);
    setProcessingFooter(`${stage} (${Math.round(percent)}%)`);
  }

  function onProcessingEnd(evt) {
    const ok = !!evt?.detail?.success;
    isProcessing = false;
    if (!ok) {
      hasDatasetLoaded = false;
      clearCache();
      if (gridApi) {
        gridApi.setGridOption("loading", false);
        updateFooter(0, true);
        gridApi.showNoRowsOverlay();
      }
    }
  }

  function onSessionCleared() {
    isProcessing = false;
    hasDatasetLoaded = false;
    clearCache();
    if (gridApi) {
      gridApi.setGridOption("loading", false);
      updateFooter(0, true);
      gridApi.showNoRowsOverlay();
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    initGrid([]); // Start with empty placeholder Grid
    hasDatasetLoaded = false;

    // Always show the table wrapper — hide the empty state div if it existed
    const empty  = document.getElementById("table-empty");
    const scroll = document.querySelector(".table-scroll");
    if (empty)  empty.style.display  = "none";
    if (scroll) scroll.style.display = "block";

    // 1. Listen for initial file load to discover columns
    window.addEventListener("asterix:loaded", (e) => onDataLoaded(e.detail));
    window.addEventListener("asterix:processing-start", onProcessingStart);
    window.addEventListener("asterix:processing-end", onProcessingEnd);
    window.addEventListener("asterix:processing-progress", onProcessingProgress);
    window.addEventListener("asterix:session-cleared", onSessionCleared);

    // 2. Refresh table only after backend confirms temporary pandas refresh
    window.addEventListener("asterix:filters-applied", refreshGrid);

    // 3. WS fallback if WS pushes "apply_filters_result" (optional, but good for map sync)
    // WS.on("apply_filters_result", refreshGrid);

    // 4. Main table stream channel
    WS.on("table_window_result", onTableWindow);

    // Keep initial table state clean while no file exists.
    if (gridApi) {
      gridApi.setGridOption("loading", false);
      updateFooter(0, true);
      gridApi.showNoRowsOverlay();
    }
  }

  return { init, refreshGrid };

})();

document.addEventListener("DOMContentLoaded", () => Table.init());
