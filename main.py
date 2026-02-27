import time
import threading

import webview

from connections.api import create_api, start_api_server
from connections.websocket_handler import start_websocket_server
from database.asterix_pandas import AsterixStore
from user_actions.user_actions_manager import Actions


# ── Configuration ─────────────────────────────────────────────────────────────
HTTP_PORT  = 8000
WS_PORT    = 8765
APP_TITLE  = "ASTERIX Decoder"
APP_WIDTH  = 1400
APP_HEIGHT = 900

# ── Bootstrap ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    # 1. Shared in-memory store (single source of truth)
    store = AsterixStore()

    # 2. Action dispatcher (passed to both API and WS layers)
    actions = Actions(store)

    # 3. FastAPI — REST + static files
    api = create_api(store, actions)
    http_thread = threading.Thread(
        target=start_api_server,
        args=(api, HTTP_PORT),
        daemon=True,
    )
    http_thread.start()
    print(f"[HTTP]  http://127.0.0.1:{HTTP_PORT}")

    # 4. WebSocket server
    ws_thread = threading.Thread(
        target=start_websocket_server,
        args=(actions, WS_PORT),
        daemon=True,
    )
    ws_thread.start()
    print(f"[WS]    ws://127.0.0.1:{WS_PORT}")

    # 5. Wait for both servers to bind
    time.sleep(1)

    # 6. Open pywebview — blocks until the user closes the window
    webview.create_window(
        title     = APP_TITLE,
        url       = f"http://127.0.0.1:{HTTP_PORT}",
        width     = APP_WIDTH,
        height    = APP_HEIGHT,
        resizable = True,
        min_size  = (900, 600),
    )
    webview.start(gui="qt")
    print("Window closed. Exiting.")
