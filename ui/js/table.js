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
  let tableReadyDispatched = false;

  const BLOCK_SIZE = 100;
  const WINDOW_MARGIN = 250;
  const RETAIN_MARGIN = 1000;
  const REQUEST_TIMEOUT_MS = 30000;
  const SEND_RETRY_DELAY_MS = 250;
  const HTTP_REQUEST_TIMEOUT_MS = 20000;
  const API_BASE = window.location.origin || "http://127.0.0.1:8888";
  const TABLE_DATA_URL = `${API_BASE}/table_data`;

  function nextRequestId() {
    requestSeq += 1;
    return `table_${cacheGeneration}_${requestSeq}`;
  }

  function clearCache() {
    const staleRequests = [...pendingRequests.values()];
    staleRequests.forEach((pending) => {
      if (pending.timeoutId) clearTimeout(pending.timeoutId);
      if (pending.retryId) clearTimeout(pending.retryId);
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

  function dispatchTableReady() {
    if (tableReadyDispatched) return;
    tableReadyDispatched = true;
    window.dispatchEvent(new CustomEvent("asterix:table-ready", {
      detail: { success: true },
    }));
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
    if (!WS.isConnected()) {
      requestWindowHttp(params, "ws-disconnected");
      return;
    }
    const requestId = nextRequestId();

    const payload = {
      action: "get_table_window",
      request_id: requestId,
      startRow,
      endRow,
      margin: WINDOW_MARGIN,
      sortCol,
      sortDir,
    };

    pendingRequests.set(requestId, {
      generation: cacheGeneration,
      startRow,
      endRow,
      payload,
      params,
      fallbackUsed: false,
      successCallback: params.successCallback,
      failCallback: params.failCallback,
      timeoutId: setTimeout(() => {
        const stale = pendingRequests.get(requestId);
        if (!stale) return;
        if (stale.retryId) clearTimeout(stale.retryId);
        pendingRequests.delete(requestId);
        if (attemptHttpFallback(stale, "timeout")) {
          return;
        }
        stale.failCallback();
        if (gridApi) {
          gridApi.setGridOption("loading", false);
          setProcessingFooter("Table request timed out. Retrying may be needed.");
          gridApi.showNoRowsOverlay();
        }
      }, REQUEST_TIMEOUT_MS),
    });

    const trySend = () => {
      const pending = pendingRequests.get(requestId);
      if (!pending) return;

      const sent = WS.send(pending.payload);
      if (sent) return;

      pending.retryId = setTimeout(trySend, SEND_RETRY_DELAY_MS);
    };

    trySend();
  }

  function onTableWindow(payload) {
    const data = payload?.data || {};
    const requestId = data.request_id;
    if (!requestId || !pendingRequests.has(requestId)) return;

    const pending = pendingRequests.get(requestId);
    if (pending?.timeoutId) clearTimeout(pending.timeoutId);
    if (pending?.retryId) clearTimeout(pending.retryId);
    pendingRequests.delete(requestId);

    if (pending.generation !== cacheGeneration) return;

    if (payload?.status && payload.status !== "ok") {
      if (attemptHttpFallback(pending, "ws-error")) {
        return;
      }
      pending.failCallback();
      if (gridApi) {
        gridApi.setGridOption("loading", false);
        setProcessingFooter(`Table error: ${data.detail || "unknown error"}`);
        gridApi.showNoRowsOverlay();
      }
      return;
    }

    applyWindowData({
      startRow: pending.startRow,
      endRow: pending.endRow,
      windowStart: data.window_start || 0,
      records: data.records || [],
      totalCount: data.total_count || 0,
      successCallback: pending.successCallback,
      failCallback: pending.failCallback,
    });
  }

  function onWsError(payload) {
    if (!hasDatasetLoaded) return;
    const detail = payload?.detail || "WebSocket request failed";
    setProcessingFooter(`WebSocket error: ${detail}`);
  }

  function applyWindowData({
    startRow,
    endRow,
    windowStart,
    records,
    totalCount,
    successCallback,
    failCallback,
  }) {
    lastKnownTotalCount = totalCount;

    if (totalCount === 0) {
      successCallback([], 0);
      updateFooter(0, false);
      if (gridApi) gridApi.setGridOption("loading", false);
      dispatchTableReady();
      return;
    }

    records.forEach((row, offset) => {
      rowCache.set(windowStart + offset, row);
    });

    pruneCache(startRow, endRow);

    if (!hasCachedRange(startRow, endRow)) {
      failCallback();
      if (gridApi) gridApi.setGridOption("loading", false);
      return;
    }

    const rows = buildRowsFromCache(startRow, endRow);
    successCallback(rows, totalCount);

    updateFooter(totalCount, false);
    if (gridApi) gridApi.setGridOption("loading", false);

    dispatchTableReady();
  }

  function resolveHttpRange(startRow, endRow) {
    const safeStart = Math.max(0, startRow - WINDOW_MARGIN);
    const safeEnd = Math.max(safeStart + BLOCK_SIZE, endRow + WINDOW_MARGIN);
    return { startRow: safeStart, endRow: safeEnd };
  }

  async function requestWindowHttp(params, reason) {
    const { sortCol, sortDir } = getSortFromParams(params);
    const range = resolveHttpRange(params.startRow, params.endRow);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), HTTP_REQUEST_TIMEOUT_MS);

    try {
      const res = await fetch(TABLE_DATA_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          startRow: range.startRow,
          endRow: range.endRow,
          sortCol,
          sortDir,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      const totalCount = data.count ?? data.total_count ?? 0;
      applyWindowData({
        startRow: params.startRow,
        endRow: params.endRow,
        windowStart: range.startRow,
        records: data.records || [],
        totalCount,
        successCallback: params.successCallback,
        failCallback: params.failCallback,
      });
    } catch (err) {
      console.warn(`[Table] HTTP fallback failed (${reason}):`, err);
      params.failCallback();
      if (gridApi) {
        gridApi.setGridOption("loading", false);
        setProcessingFooter("Table request failed. Check backend connection.");
        gridApi.showNoRowsOverlay();
      }
    } finally {
      clearTimeout(timeoutId);
    }
  }

  function attemptHttpFallback(pending, reason) {
    if (!pending || pending.fallbackUsed) return false;
    pending.fallbackUsed = true;
    if (pending.retryId) clearTimeout(pending.retryId);
    if (pending.timeoutId) clearTimeout(pending.timeoutId);
    requestWindowHttp(pending.params, reason);
    return true;
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
      sortable: false,
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
        sortable: false,
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
      tableReadyDispatched = false;
      clearCache();
      if (gridApi) {
          gridApi.destroy();
      }
      initGrid(columns);
      refreshGrid();

      if ((meta.record_count ?? 0) === 0) {
        dispatchTableReady();
      }
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
    tableReadyDispatched = false;
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
    WS.on("error", onWsError);

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
