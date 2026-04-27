/**
 * upload.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Handles ASTERIX binary file upload to POST /upload.
 * Two entry points:
 *   1. The "Load File" button in the header triggers the hidden file input.
 *   2. Drag-and-drop anywhere on the window shows a drop overlay and
 *      submits the file when released.
 *
 * On success, fires the custom window event "asterix:loaded" with the
 * metadata JSON returned by the API, so other modules (map, table, filters)
 * can react independently.
 */

const Upload = (() => {

  const API_BASE = "http://127.0.0.1:8888";
  const API_URL = `${API_BASE}/upload`;
  const CSV_URL = `${API_BASE}/download/csv`;

  let processingActive = false;
  let fileLoaded = false;
  let progressOrder = [];
  let progressNodes = new Map();
  let currentStageKey = null;
  let currentStageText = "Waiting to start.";
  let decodeProgressPercent = 0;
  let tableReadyTimeoutId = null;

  const TABLE_READY_TIMEOUT_MS = 15000;

  // ── Toast helper ─────────────────────────────────────────────────────────────
  function toast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);

    setTimeout(() => {
      el.style.transition = "opacity 300ms ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 320);
    }, 3500);
  }

  // ── Status bar file info ──────────────────────────────────────────────────────
  function setFileStatus(filename) {
    const el = document.getElementById("file-label");
    if (el) el.textContent = filename ?? "No file uploaded yet";
  }

  function setMessageBadge(value) {
    const badge = document.getElementById("record-count");
    if (badge) badge.textContent = value;
  }

  function setFrontStatus(message) {
    const el = document.getElementById("front-status");
    if (el) el.textContent = message;
  }

  function setUploadControlsDisabled(disabled) {
    const frontButton = document.getElementById("front-upload-btn");
    if (frontButton) frontButton.disabled = disabled;

    const headerButton = document.getElementById("upload-btn");
    if (headerButton) headerButton.disabled = disabled;

    const input = document.getElementById("file-input");
    if (input) input.disabled = disabled;
  }

  function setHeaderUploadMode(mode) {
    const button = document.getElementById("upload-btn");
    if (!button) return;

    if (mode === "exit") {
      button.textContent = "Exit File";
      button.dataset.action = "exit-file";
      return;
    }

    button.textContent = "Upload File";
    button.dataset.action = "upload-file";
  }

  function setDownloadDisabled(disabled) {
    const button = document.getElementById("download-btn");
    if (button) button.disabled = disabled;
  }

  function getProgressPanel() {
    return {
      stack: document.querySelector(".upload-progress-stack-box"),
      current: document.getElementById("upload-progress-current-box"),
      fill: document.getElementById("upload-progress-fill"),
      percent: document.getElementById("upload-progress-percent"),
      text: document.getElementById("upload-progress-text"),
      log: document.getElementById("upload-progress-log"),
      stage: document.getElementById("upload-progress-stage"),
      stackCount: document.getElementById("upload-progress-stack-count"),
    };
  }

  function clearProgressLog() {
    progressOrder = [];
    progressNodes = new Map();
    currentStageKey = null;
    currentStageText = "Waiting to start.";
    decodeProgressPercent = 0;

    if (tableReadyTimeoutId) {
      clearTimeout(tableReadyTimeoutId);
      tableReadyTimeoutId = null;
    }

    const { log, stackCount, stage, text, percent, fill, current, stack } = getProgressPanel();
    if (log) log.innerHTML = "";
    if (stackCount) stackCount.textContent = "0";
    if (stage) stage.textContent = "Waiting to start";
    if (text) text.textContent = "Waiting to start.";
    if (percent) percent.textContent = "0%";
    if (fill) fill.style.width = "0%";
    if (stack) stack.hidden = true;
    if (current) current.hidden = true;
  }

  function formatCount(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return null;
    return number.toLocaleString();
  }

  function formatProgress(data) {
    const stageMap = {
      "Leyendo archivo ASTERIX": "Reading ASTERIX file",
      "Separando mensajes": "Splitting messages",
      "Leyendo FSPEC": "Parsing FSPEC",
      "Preparando decodificadores": "Preparing decoders",
      "Decodificando mensajes": "Decoding messages",
      "Finalizando tabla": "Building final table",
    };

    const rawStage = data?.stage || "Processing file";
    const stage = stageMap[rawStage] || rawStage;
    const percent = Number(data?.percent ?? 0);
    const current = Number.isFinite(Number(data?.current)) ? Number(data.current) : null;
    const total = Number.isFinite(Number(data?.total)) ? Number(data.total) : null;
    const currentText = formatCount(current);
    const totalText = formatCount(total);
    const isSplitStage = rawStage === "Separando mensajes" || stage === "Splitting messages";
    const isDecodeStage = rawStage === "Decodificando mensajes" || stage === "Decoding messages";

    let detail = stage;
    if (isSplitStage && totalText !== null) {
      detail = `${stage} ${totalText}`;
    } else if (isDecodeStage && totalText !== null) {
      const currentDisplay = currentText ?? "0";
      detail = `${stage} ${currentDisplay} / ${totalText}`;
    }

    return { stage, percent, detail };
  }

  function setProgressPanel(text, percent, stageLabel) {
    const { current, fill, percent: percentEl, text: textEl, stage: stageEl } = getProgressPanel();
    if (!current || !fill || !percentEl || !textEl || !stageEl) return;

    const safePercent = Number.isFinite(percent)
      ? Math.max(0, Math.min(100, percent))
      : 0;

    current.hidden = false;
    fill.style.width = `${safePercent}%`;
    percentEl.textContent = `${Math.round(safePercent)}%`;
    textEl.textContent = text;
    stageEl.textContent = stageLabel || currentStageKey || "Processing";
  }

  function hideProgressPanel() {
    const { current, fill, percent, text, log, stage, stackCount } = getProgressPanel();
    if (!current || !fill || !percent || !text || !log || !stage || !stackCount) return;

    fill.style.width = "0%";
    percent.textContent = "0%";
    text.textContent = "Waiting to start.";
    stage.textContent = "Waiting to start";
    log.innerHTML = "";
    stackCount.textContent = "0";
    current.hidden = true;
  }

  function appendCompletedStage(key, text) {
    const { log, stack, stackCount } = getProgressPanel();
    if (!log) return;

    if (stack) stack.hidden = false;

    let entry = progressNodes.get(key);
    if (!entry) {
      entry = document.createElement("div");
      entry.className = "upload-progress-entry";
      progressNodes.set(key, entry);
      progressOrder.push(key);
      log.appendChild(entry);

      while (progressOrder.length > 7) {
        const oldestKey = progressOrder.shift();
        const oldestNode = progressNodes.get(oldestKey);
        if (oldestNode) oldestNode.remove();
        progressNodes.delete(oldestKey);
      }

      if (stackCount) stackCount.textContent = String(progressOrder.length);
    }

    entry.textContent = text;
    entry.classList.add("is-complete");
  }

  function updateCurrentStage(stage, detail, percent) {
    currentStageKey = stage;
    currentStageText = detail;
    setProgressPanel(detail, percent, stage);
  }

  function commitPreviousStage(nextStage) {
    if (!currentStageKey) return;
    if (currentStageKey === nextStage) return;

    appendCompletedStage(currentStageKey, currentStageText);
  }

  function finishCurrentStage(finalText) {
    if (!currentStageKey) return;
    appendCompletedStage(currentStageKey, finalText || currentStageText);
    currentStageKey = null;
  }

  function onDecodeProgress(payload) {
    if (!processingActive) return;

    const data = payload?.data || {};
    const { stage, percent, detail } = formatProgress(data);
    const nextPercent = Math.min(95, Math.max(decodeProgressPercent, percent));
    decodeProgressPercent = nextPercent;

    setFrontStatus(detail);

    commitPreviousStage(stage);
    updateCurrentStage(stage, detail, nextPercent);

    window.dispatchEvent(new CustomEvent("asterix:processing-progress", {
      detail: {
        ...data,
        stage,
        display_text: detail,
      },
    }));
  }

  function startProcessingUI(filename) {
    processingActive = true;
    setUploadControlsDisabled(true);
    setDownloadDisabled(true);
    document.body.classList.add("uploading");
    clearProgressLog();
    const overlay = document.getElementById("drop-overlay");
    if (overlay) overlay.classList.remove("visible");
    currentStageKey = "Preparing decoder";
    currentStageText = `Preparing decoder for ${filename}`;
    setProgressPanel(currentStageText, 0, "Preparing decoder");
  }

  function scheduleTableReadyFallback() {
    if (tableReadyTimeoutId) clearTimeout(tableReadyTimeoutId);

    tableReadyTimeoutId = setTimeout(() => {
      tableReadyTimeoutId = null;
      if (!processingActive) return;

      toast("Table is taking longer than expected. Opening dashboard.", "info");
      window.dispatchEvent(new CustomEvent("asterix:table-ready", {
        detail: { success: true, degraded: true },
      }));
    }, TABLE_READY_TIMEOUT_MS);
  }

  function finishProcessingUI() {
    processingActive = false;
    if (tableReadyTimeoutId) {
      clearTimeout(tableReadyTimeoutId);
      tableReadyTimeoutId = null;
    }
    setUploadControlsDisabled(false);
    document.body.classList.remove("uploading");
    hideProgressPanel();
  }

  function onTableReady(evt) {
    if (!processingActive) return;

    const degraded = !!evt?.detail?.degraded;

    if (tableReadyTimeoutId) {
      clearTimeout(tableReadyTimeoutId);
      tableReadyTimeoutId = null;
    }

    if (degraded) {
      finishCurrentStage("File decoded. Table is still loading in background.");
      setFrontStatus("File processed. Table is still loading in background.");
      setProgressPanel("File decoded. Table is still loading in background.", 100, "Ready");
    } else {
      finishCurrentStage("Loading tables complete. Dashboard ready.");
      setFrontStatus("File processed successfully. Opening dashboard...");
      setProgressPanel("Loading tables complete. Dashboard ready.", 100, "Ready");
    }

    setDownloadDisabled(false);
    fileLoaded = true;
    setHeaderUploadMode("exit");
    finishProcessingUI();
  }

  function clearCurrentFile() {
    if (processingActive) return;

    fileLoaded = false;
    document.body.classList.remove("uploading");
    setHeaderUploadMode("upload");
    setDownloadDisabled(true);
    setMessageBadge("—");
    setFileStatus(null);
    setFrontStatus("Waiting for file upload.");
    clearProgressLog();
    if (typeof Filters !== "undefined" && typeof Filters.resetFilters === "function") {
      Filters.resetFilters({ apply: false });
    }

    window.dispatchEvent(new CustomEvent("asterix:session-cleared"));
    toast("Returned to start menu.", "info");
  }

  // ── Upload logic ──────────────────────────────────────────────────────────────
  async function uploadFile(file) {
    if (!file) return;

    if (processingActive) {
      toast("A file is already being processed.", "info");
      return;
    }

    // Basic validation — ASTERIX files are binary, typically .ast or no extension
    const maxSize = 200 * 1024 * 1024;  // 200 MB
    if (file.size > maxSize) {
      toast("File exceeds 200 MB limit.", "error");
      return;
    }

    toast(`Processing file: ${file.name}`);
    setFileStatus(`Processing file... ${file.name}`);
    setMessageBadge("Processing...");
    setFrontStatus(`Processing file: ${file.name}`);
    startProcessingUI(file.name);

    window.dispatchEvent(new CustomEvent("asterix:processing-start", {
      detail: { filename: file.name }
    }));

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(API_URL, { method: "POST", body: form });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? "Upload failed");
      }

      const meta = await res.json();

      // Update message badge in header
      setMessageBadge(meta.record_count?.toLocaleString() ?? "0");

      setFileStatus(`${file.name}  (${(file.size / 1024).toFixed(0)} KB)`);
      toast(`Loaded ${meta.record_count?.toLocaleString() ?? "?"} messages.`, "success");

      // Notify other modules
      window.dispatchEvent(new CustomEvent("asterix:loaded", { detail: meta }));
      window.dispatchEvent(new CustomEvent("asterix:processing-end", {
        detail: { success: true, metadata: meta }
      }));

      if (!processingActive) {
        return;
      }

      setFrontStatus("Loading tables...");
      currentStageKey = "Loading tables";
      currentStageText = "Loading tables...";
      setProgressPanel("Loading tables...", Math.max(96, decodeProgressPercent), "Loading tables");
      scheduleTableReadyFallback();

    } catch (err) {
      console.error("[Upload] Error:", err);
      toast(`Error: ${err.message}`, "error");
      setFileStatus("Upload failed.");
      setMessageBadge("—");
      setFrontStatus("Processing failed. Upload another file to continue.");
      window.dispatchEvent(new CustomEvent("asterix:processing-end", {
        detail: { success: false, error: String(err?.message || err) }
      }));
      finishProcessingUI();
    }
  }

  // ── Drop overlay ──────────────────────────────────────────────────────────────
  function initDragDrop() {
    const overlay = document.getElementById("drop-overlay");
    if (!overlay) return;

    let dragCounter = 0;  // track nested dragenter/dragleave pairs

    window.addEventListener("dragenter", (e) => {
      e.preventDefault();
      if (processingActive) return;
      dragCounter++;
      if (dragCounter === 1) overlay.classList.add("visible");
    });

    window.addEventListener("dragleave", () => {
      if (processingActive) return;
      dragCounter--;
      if (dragCounter <= 0) {
        dragCounter = 0;
        overlay.classList.remove("visible");
      }
    });

    window.addEventListener("dragover", (e) => {
      e.preventDefault();  // required to allow drop
      if (processingActive) return;
    });

    window.addEventListener("drop", (e) => {
      e.preventDefault();
      if (processingActive) return;
      dragCounter = 0;
      overlay.classList.remove("visible");

      const file = e.dataTransfer?.files?.[0];
      if (file) uploadFile(file);
    });
  }

  // ── File input (button) ───────────────────────────────────────────────────────
  function initFileInput() {
    const input  = document.getElementById("file-input");
    const frontButton = document.getElementById("front-upload-btn");
    const headerButton = document.getElementById("upload-btn");
    if (!input || !frontButton || !headerButton) return;

    frontButton.addEventListener("click", () => {
      if (processingActive) return;
      input.click();
    });

    headerButton.addEventListener("click", () => {
      if (processingActive) return;
      if (headerButton.dataset.action === "exit-file") {
        clearCurrentFile();
        return;
      }
      input.click();
    });

    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (file) uploadFile(file);
      input.value = "";  // reset so the same file can be re-selected
    });
  }

  // ── Init ──────────────────────────────────────────────────────────────────────
  // ── Download CSV ─────────────────────────────────────────────────────────────
  function initDownload() {
    const button = document.getElementById("download-btn");
    if (!button) return;

    button.addEventListener("click", async () => {
      toast("Downloading CSV…");
      try {
        if (window.pywebview && window.pywebview.api) {
            const res = await window.pywebview.api.trigger_download_csv();
            if (res === "Cancelled") {
                toast("Download cancelled");
            } else if (res.includes("successfully")) {
                toast(res, "success");
            } else {
                toast(`Error: ${res}`, "error");
            }
        } else {
            // Fallback for normal browsers (e.g. Chrome/Firefox)
            const a = document.createElement("a");
            a.href = CSV_URL;
            a.download = "decoded_asterix.csv";
            document.body.appendChild(a);
            a.click();
            a.remove();
        }
      } catch (err) {
          toast(err.message, "error");
      }
    });
  }

  // ── Init ──────────────────────────────────────────────────────────────────────
  function init() {
    initDragDrop();
    initFileInput();
    initDownload();
    WS.on("decode_progress", onDecodeProgress);
    window.addEventListener("asterix:table-ready", onTableReady);
    document.body.classList.remove("uploading");
    setFileStatus(null);
    setMessageBadge("—");
    setFrontStatus("Waiting for file upload.");
    setHeaderUploadMode("upload");
    hideProgressPanel();
  }

  return { init, uploadFile };

})();

document.addEventListener("DOMContentLoaded", () => Upload.init());
