import asyncio
import json
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

from user_actions.user_actions_manager import Actions


_SERVER_LOOP: asyncio.AbstractEventLoop | None = None
_CLIENTS: set[WebSocketServerProtocol] = set()
_LAST_BROADCAST_DROP: str | None = None


def _debug_ws(message: str) -> None:
    Actions._debug_log(f"[WS] {message}")


def _make_broadcast_drop_key(reason: str, payload_type: Any) -> str:
    return f"{reason}:{payload_type}"


# ── Per-connection handler ────────────────────────────────────────────────────

async def _handle_connection(
    websocket: WebSocketServerProtocol,
    actions: Actions,
) -> None:
    """Lifecycle handler for a single browser connection."""
    _CLIENTS.add(websocket)
    remote = websocket.remote_address
    print(f"[WS] Connected  — {remote}")
    _debug_ws(f"Connected remote={remote}")

    try:
        async for raw in websocket:
            await _dispatch(raw, websocket, actions)

    except websockets.exceptions.ConnectionClosed as exc:
        print(f"[WS] Closed     — {remote}  ({exc.code}) {exc.reason}")
        _debug_ws(f"Closed remote={remote} code={exc.code} reason={exc.reason}")
    except Exception as exc:
        import traceback
        print(f"[WS] Unexpected error from {remote}: {exc}")
        traceback.print_exc()
    finally:
        _CLIENTS.discard(websocket)
        print(f"[WS] Disconnected — {remote}")
        _debug_ws(f"Disconnected remote={remote}")


async def _dispatch(
    raw: str,
    websocket: WebSocketServerProtocol,
    actions: Actions,
) -> None:
    """Parse a raw message and route it to the correct action handler."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        await _send_error(websocket, f"Invalid JSON: {exc}")
        return

    action = data.get("action")
    if not action:
        await _send_error(websocket, "Missing 'action' field.")
        return

    print(f"[WS] Action → {action}")
    try:
        await actions.handle_action(action, websocket, data)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        await _send_error(websocket, f"Action '{action}' failed: {exc}")


async def _send_error(websocket: WebSocketServerProtocol, detail: str) -> None:
    payload = json.dumps({"type": "error", "detail": detail}, separators=(",", ":"))
    await websocket.send(payload)


async def _broadcast(payload: dict[str, Any]) -> None:
    if not _CLIENTS:
        return

    message = json.dumps(payload, default=str, separators=(",", ":"))
    stale_clients: list[WebSocketServerProtocol] = []

    for websocket in list(_CLIENTS):
        try:
            await websocket.send(message)
        except Exception:
            stale_clients.append(websocket)

    for websocket in stale_clients:
        _CLIENTS.discard(websocket)


def broadcast_message(payload: dict[str, Any]) -> None:
    """Thread-safe broadcast helper for progress updates and alerts."""
    global _LAST_BROADCAST_DROP
    if _SERVER_LOOP is None or _SERVER_LOOP.is_closed():
        drop_key = _make_broadcast_drop_key("no_loop", payload.get("type"))
        if drop_key != _LAST_BROADCAST_DROP:
            _LAST_BROADCAST_DROP = drop_key
            _debug_ws(f"Broadcast skipped (no loop) type={payload.get('type')}")
        return

    if not _CLIENTS:
        drop_key = _make_broadcast_drop_key("no_clients", payload.get("type"))
        if drop_key != _LAST_BROADCAST_DROP:
            _LAST_BROADCAST_DROP = drop_key
            _debug_ws(f"Broadcast skipped (no clients) type={payload.get('type')}")
        return

    try:
        asyncio.run_coroutine_threadsafe(_broadcast(payload), _SERVER_LOOP)
    except Exception:
        pass


# ── Server entry point ────────────────────────────────────────────────────────

async def _run_server(actions: Actions, port: int) -> None:
    """Start the WebSocket server and keep it alive indefinitely."""
    global _SERVER_LOOP
    _SERVER_LOOP = asyncio.get_running_loop()

    # Wrap the per-connection coroutine so it receives `actions` via closure
    async def handler(ws: WebSocketServerProtocol):
        await _handle_connection(ws, actions)

    async with websockets.serve(
        handler,
        "127.0.0.1",
        port,
        ping_interval=None,
        max_queue=64,
        max_size=4 * 1024 * 1024,
        compression=None,
        close_timeout=2,
    ):
        print(f"[WS]    ws://127.0.0.1:{port}")
        _debug_ws(f"Server listening on 127.0.0.1:{port}")
        await asyncio.Future()   # run forever


def start_websocket_server(actions: Actions, port: int) -> None:
    """
    Blocking entry point for a daemon thread.
    Creates its own event loop so it doesn't conflict with any other loop.
    """
    asyncio.run(_run_server(actions, port))
