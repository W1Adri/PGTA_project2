/**
 * websocket.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Manages the WebSocket connection lifecycle.
 * Exposes a thin global `WS` object used by other modules to send messages
 * and register action handlers.
 *
 * Usage from other modules:
 *   WS.send({ action: "apply_filters", callsigns: ["IBE001"] });
 *   WS.on("apply_filters_result", (data) => { ... });
 */

const WS = (() => {

  const WS_URL         = "ws://127.0.0.1:8765";
  const RECONNECT_DELAY = 3000;   // ms

  let socket    = null;
  let reconnectTimer = null;
  const handlers = {};   // action → [callback, ...]

  // ── Status helpers ──────────────────────────────────────────────────────────
  function setStatus(state) {
    const dot   = document.getElementById("ws-dot");
    const label = document.getElementById("ws-label");
    if (!dot || !label) return;

    dot.className   = `status-dot ${state}`;
    const labels    = { connected: "Connected", disconnected: "Disconnected", loading: "Connecting..." };
    label.textContent = labels[state] ?? state;
  }

  // ── Connection ──────────────────────────────────────────────────────────────
  function connect() {
    setStatus("loading");

    socket = new WebSocket(WS_URL);

    socket.addEventListener("open", () => {
      console.log("[WS] Connected");
      setStatus("connected");
      clearTimeout(reconnectTimer);
    });

    socket.addEventListener("close", (evt) => {
      console.warn("[WS] Closed", evt.code, evt.reason);
      setStatus("disconnected");
      socket = null;
      scheduleReconnect();
    });

    socket.addEventListener("error", (err) => {
      console.error("[WS] Error", err);
      // close event follows, so reconnect is handled there
    });

    socket.addEventListener("message", (evt) => {
      let payload;
      try { payload = JSON.parse(evt.data); }
      catch { console.warn("[WS] Non-JSON message:", evt.data); return; }

      const type = payload.type;
      if (!type) { console.warn("[WS] No type in message:", payload); return; }

      (handlers[type] || []).forEach(cb => {
        try { cb(payload); }
        catch (e) { console.error(`[WS] Handler error for '${type}':`, e); }
      });

      // Global catch-all for debug
      (handlers["*"] || []).forEach(cb => {
        try { cb(payload); }
        catch (e) { console.error("[WS] Catch-all handler error:", e); }
      });
    });
  }

  function scheduleReconnect() {
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      console.log("[WS] Attempting reconnect...");
      connect();
    }, RECONNECT_DELAY);
  }

  // ── Public API ───────────────────────────────────────────────────────────────
  function send(payload) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      console.warn("[WS] Cannot send — socket not open:", payload);
      return false;
    }
    socket.send(JSON.stringify(payload));
    return true;
  }

  /**
   * Register a handler for a specific message type.
   * Multiple handlers per type are supported.
   * Use "*" to receive all messages.
   */
  function on(type, callback) {
    if (!handlers[type]) handlers[type] = [];
    handlers[type].push(callback);
  }

  function off(type, callback) {
    if (!handlers[type]) return;
    handlers[type] = handlers[type].filter(cb => cb !== callback);
  }

  function isConnected() {
    return socket && socket.readyState === WebSocket.OPEN;
  }

  // Auto-connect when the module loads
  connect();

  return { send, on, off, isConnected };

})();
