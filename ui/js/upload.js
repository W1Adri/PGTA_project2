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
    document.querySelectorAll("[data-upload-trigger='true']").forEach(button => {
      button.disabled = disabled;
    });

    const input = document.getElementById("file-input");
    if (input) input.disabled = disabled;
  }

  function setDownloadDisabled(disabled) {
    const button = document.getElementById("download-btn");
    if (button) button.disabled = disabled;
  }

  function setProcessingBanner(text, percent) {
    const banner = document.getElementById("processing-banner");
    const fill = document.getElementById("processing-fill");
    const percentEl = document.getElementById("processing-percent");
    const textEl = document.getElementById("processing-text");
    if (!banner || !fill || !percentEl || !textEl) return;

    const safePercent = Number.isFinite(percent)
      ? Math.max(0, Math.min(100, percent))
      : 0;

    banner.hidden = false;
    fill.style.width = `${safePercent}%`;
    percentEl.textContent = `${Math.round(safePercent)}%`;
    textEl.textContent = text;
  }

  function hideProcessingBanner() {
    const banner = document.getElementById("processing-banner");
    const fill = document.getElementById("processing-fill");
    const percentEl = document.getElementById("processing-percent");
    const textEl = document.getElementById("processing-text");
    if (!banner || !fill || !percentEl || !textEl) return;

    fill.style.width = "0%";
    percentEl.textContent = "0%";
    textEl.textContent = "Waiting to start.";
    banner.hidden = true;
  }

  function formatProgress(data) {
    const stage = data?.stage || "Processing file";
    const percent = Number(data?.percent ?? 0);
    const current = Number(data?.current ?? 0);
    const total = Number(data?.total ?? 0);

    if (Number.isFinite(total) && total > 0) {
      return {
        text: `${stage} · ${current.toLocaleString()} / ${total.toLocaleString()}`,
        percent,
      };
    }

    return { text: stage, percent };
  }

  function onDecodeProgress(payload) {
    if (!processingActive) return;

    const data = payload?.data || {};
    const { text, percent } = formatProgress(data);

    setProcessingBanner(text, percent);
    setFrontStatus(text);

    window.dispatchEvent(new CustomEvent("asterix:processing-progress", {
      detail: {
        ...data,
        display_text: text,
      },
    }));
  }

  function startProcessingUI(filename) {
    processingActive = true;
    setUploadControlsDisabled(true);
    setDownloadDisabled(true);
    const overlay = document.getElementById("drop-overlay");
    if (overlay) overlay.classList.remove("visible");
    setProcessingBanner(`Preparing decoder for ${filename}`, 0);
  }

  function finishProcessingUI() {
    processingActive = false;
    setUploadControlsDisabled(false);
    hideProcessingBanner();
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
      setFrontStatus("File processed successfully. Opening dashboard...");
      toast(`Loaded ${meta.record_count?.toLocaleString() ?? "?"} messages.`, "success");

      // Enable download button
      setDownloadDisabled(false);

      // Notify other modules
      window.dispatchEvent(new CustomEvent("asterix:loaded", { detail: meta }));
      window.dispatchEvent(new CustomEvent("asterix:processing-end", {
        detail: { success: true, metadata: meta }
      }));
      finishProcessingUI();

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
    const buttons = document.querySelectorAll("[data-upload-trigger='true']");
    if (!input || buttons.length === 0) return;

    buttons.forEach(button => {
      button.addEventListener("click", () => input.click());
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
    setFileStatus(null);
    setMessageBadge("—");
    setFrontStatus("Waiting for file upload.");
    hideProcessingBanner();
  }

  return { init, uploadFile };

})();

document.addEventListener("DOMContentLoaded", () => Upload.init());
