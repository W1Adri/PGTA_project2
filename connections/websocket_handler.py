import asyncio
import json

import websockets
from websockets.server import WebSocketServerProtocol

from user_actions.user_actions_manager import Actions


# ── Per-connection handler ────────────────────────────────────────────────────

async def _handle_connection(
    websocket: WebSocketServerProtocol,
    actions: Actions,
) -> None:
    """Lifecycle handler for a single browser connection."""
    remote = websocket.remote_address
    print(f"[WS] Connected  — {remote}")

    try:
        async for raw in websocket:
            await _dispatch(raw, websocket, actions)

    except websockets.exceptions.ConnectionClosed as exc:
        print(f"[WS] Closed     — {remote}  ({exc.code})")
    except Exception as exc:
        import traceback
        print(f"[WS] Unexpected error from {remote}: {exc}")
        traceback.print_exc()
    finally:
        print(f"[WS] Disconnected — {remote}")


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
    payload = json.dumps({"type": "error", "detail": detail})
    await websocket.send(payload)


# ── Server entry point ────────────────────────────────────────────────────────

async def _run_server(actions: Actions, port: int) -> None:
    """Start the WebSocket server and keep it alive indefinitely."""

    # Wrap the per-connection coroutine so it receives `actions` via closure
    async def handler(ws: WebSocketServerProtocol):
        await _handle_connection(ws, actions)

    async with websockets.serve(handler, "127.0.0.1", port):
        print(f"[WS]    ws://127.0.0.1:{port}")
        await asyncio.Future()   # run forever


def start_websocket_server(actions: Actions, port: int) -> None:
    """
    Blocking entry point for a daemon thread.
    Creates its own event loop so it doesn't conflict with any other loop.
    """
    asyncio.run(_run_server(actions, port))
