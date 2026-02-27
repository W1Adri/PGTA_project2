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

  const API_URL = "http://127.0.0.1:8000/upload";

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
    if (el) el.textContent = filename ?? "No file loaded";
  }

  // ── Upload logic ──────────────────────────────────────────────────────────────
  async function uploadFile(file) {
    if (!file) return;

    // Basic validation — ASTERIX files are binary, typically .ast or no extension
    const maxSize = 200 * 1024 * 1024;  // 200 MB
    if (file.size > maxSize) {
      toast("File exceeds 200 MB limit.", "error");
      return;
    }

    toast(`Loading: ${file.name}`);
    setFileStatus(`${file.name} — uploading...`);

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(API_URL, { method: "POST", body: form });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? "Upload failed");
      }

      const meta = await res.json();

      // Update record badge in header
      const badge = document.getElementById("record-count");
      if (badge) badge.textContent = meta.record_count?.toLocaleString() ?? "0";

      setFileStatus(`${file.name}  (${(file.size / 1024).toFixed(0)} KB)`);
      toast(`Loaded ${meta.record_count?.toLocaleString() ?? "?"} records.`, "success");

      // Notify other modules
      window.dispatchEvent(new CustomEvent("asterix:loaded", { detail: meta }));

    } catch (err) {
      console.error("[Upload] Error:", err);
      toast(`Error: ${err.message}`, "error");
      setFileStatus("Upload failed.");
    }
  }

  // ── Drop overlay ──────────────────────────────────────────────────────────────
  function initDragDrop() {
    const overlay = document.getElementById("drop-overlay");
    if (!overlay) return;

    let dragCounter = 0;  // track nested dragenter/dragleave pairs

    window.addEventListener("dragenter", (e) => {
      e.preventDefault();
      dragCounter++;
      if (dragCounter === 1) overlay.classList.add("visible");
    });

    window.addEventListener("dragleave", () => {
      dragCounter--;
      if (dragCounter <= 0) {
        dragCounter = 0;
        overlay.classList.remove("visible");
      }
    });

    window.addEventListener("dragover", (e) => {
      e.preventDefault();  // required to allow drop
    });

    window.addEventListener("drop", (e) => {
      e.preventDefault();
      dragCounter = 0;
      overlay.classList.remove("visible");

      const file = e.dataTransfer?.files?.[0];
      if (file) uploadFile(file);
    });
  }

  // ── File input (button) ───────────────────────────────────────────────────────
  function initFileInput() {
    const input  = document.getElementById("file-input");
    const button = document.getElementById("upload-btn");
    if (!input || !button) return;

    button.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (file) uploadFile(file);
      input.value = "";  // reset so the same file can be re-selected
    });
  }

  // ── Init ──────────────────────────────────────────────────────────────────────
  function init() {
    initDragDrop();
    initFileInput();
  }

  return { init, uploadFile };

})();

document.addEventListener("DOMContentLoaded", () => Upload.init());
