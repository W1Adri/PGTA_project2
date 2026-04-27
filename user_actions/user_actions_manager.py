import asyncio
import json
import os
import sys
import tempfile
import time
from websockets.server import WebSocketServerProtocol

from asterix_decoder.database.asterix_pandas import (
    MAP_DEFAULT_WINDOW_AFTER_SECONDS,
    MAP_DEFAULT_WINDOW_BEFORE_SECONDS,
    MAP_MAX_POINTS,
    TABLE_DEFAULT_MARGIN,
    AsterixPandas,
)


class Actions:

    def __init__(self, store: AsterixPandas):
        self.store = store

    @staticmethod
    def _debug_log(message: str) -> None:
        """Persist runtime diagnostics for packaged builds and opt-in debug runs."""
        should_log = getattr(sys, "frozen", False) or os.environ.get("ASTERIX_DEBUG_LOG") == "1"
        if not should_log:
            return

        try:
            forced_dir = os.environ.get("ASTERIX_DEBUG_LOG_DIR")
            if forced_dir:
                base_dir = forced_dir
            elif getattr(sys, "frozen", False):
                base_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                base_dir = tempfile.gettempdir()

            log_path = os.path.join(base_dir, "asterix_decoder_debug.log")
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {message}\n")
            except OSError:
                # Fallback if executable directory is read-only.
                fallback_path = os.path.join(tempfile.gettempdir(), "asterix_decoder_debug.log")
                with open(fallback_path, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    # ── Dispatcher ────────────────────────────────────────────────────────────

    async def handle_action(
        self,
        action   : str,
        websocket: WebSocketServerProtocol,
        data     : dict,
    ) -> None:
        """Route an incoming WebSocket message to the correct handler."""

        if action == "get_all":
            await self.action_get_all(websocket, data)

        elif action == "apply_filters":
            await self.action_apply_filters(websocket, data)

        elif action == "get_metadata":
            await self.action_get_metadata(websocket, data)

        elif action == "clear_data":
            await self.action_clear_data(websocket, data)

        elif action == "get_table_window":
            await self.action_get_table_window(websocket, data)

        elif action == "get_map_window":
            await self.action_get_map_window(websocket, data)

        # ── TODO: register new actions here ──────────────────────────────────
        # elif action == "your_new_action":
        #     await self.action_your_new_action(websocket, data)

        else:
            await self._send(websocket, {
                "type"  : "error",
                "status": "error",
                "data"  : {"detail": f"Unknown action: '{action}'"},
            })

    # ── Action handlers ───────────────────────────────────────────────────────

    async def action_get_all(
        self,
        websocket: WebSocketServerProtocol,
        data     : dict,
    ) -> None:
        """
        Return every record currently in the store, unfiltered.

        Request:  { "action": "get_all" }
        Response: { "type": "get_all_result", "status": "ok",
                    "data": { "records": [ ... ] } }
        """
        records = await asyncio.to_thread(self.store.get_all)
        await self._send(websocket, {
            "type"  : "get_all_result",
            "status": "ok",
            "data"  : {"records": records[:5000]},
        })

    async def action_apply_filters(
        self,
        websocket: WebSocketServerProtocol,
        data     : dict,
    ) -> None:
        """
        Apply one or more filters and return matching records.

        Request:
          {
            "action"      : "apply_filters",
            "callsigns"   : ["IBE001", "VLG202"],   // optional
            "categories"  : ["CAT048"],              // optional
            "squawks"     : ["2000"],                // optional
            "altitude_min": 5000,                    // optional (feet)
            "altitude_max": 35000,                   // optional (feet)
            "time_start"  : "2024-01-01T10:00:00Z", // optional ISO-8601
            "time_end"    : "2024-01-01T11:00:00Z"  // optional ISO-8601
          }

        Response:
          { "type": "apply_filters_result", "status": "ok",
            "data": { "records": [ ... ], "count": 123 } }
        """
        filters = {
            "callsigns"   : data.get("callsigns"),
            "categories"  : data.get("categories"),
            "target_identifications": data.get("target_identifications"),
            "on_ground"   : data.get("on_ground"),
            "pure_white"  : data.get("pure_white"),
            "fl_min"      : data.get("fl_min"),
            "fl_max"      : data.get("fl_max"),
            "fl_keep_null": data.get("fl_keep_null"),
            "squawks"     : data.get("squawks"),
            "altitude_min": data.get("altitude_min"),
            "altitude_max": data.get("altitude_max"),
            "time_start"  : data.get("time_start"),
            "time_end"    : data.get("time_end"),
        }

        result = await asyncio.to_thread(self.store.apply_temporary_filters, **filters)
        await self._send(websocket, {
            "type"  : "apply_filters_result",
            "status": "ok",
            "data"  : result,
        })

    async def action_get_metadata(
        self,
        websocket: WebSocketServerProtocol,
        data     : dict,
    ) -> None:
        """
        Return store metadata (record count, time range, unique values for
        filter dropdowns). Safe to call before any file is uploaded.

        Request:  { "action": "get_metadata" }
        Response: { "type": "get_metadata_result", "status": "ok",
                    "data": { ...metadata... } }
        """
        meta = await asyncio.to_thread(self.store.get_metadata)
        await self._send(websocket, {
            "type"  : "get_metadata_result",
            "status": "ok",
            "data"  : meta,
        })

    async def action_clear_data(
        self,
        websocket: WebSocketServerProtocol,
        data     : dict,
    ) -> None:
        """
        Wipe all data from the store (e.g. before loading a new file).

        Request:  { "action": "clear_data" }
        Response: { "type": "clear_data_result", "status": "ok" }
        """
        self.store.clear()
        await self._send(websocket, {
            "type"  : "clear_data_result",
            "status": "ok",
            "data"  : {"detail": "Store cleared."},
        })

    async def action_get_table_window(
        self,
        websocket: WebSocketServerProtocol,
        data: dict,
    ) -> None:
        """
        Return a contiguous table window around the currently visible indices.

        Request:
          {
            "action": "get_table_window",
            "startRow": 1200,
            "endRow": 1300,
            "margin": 40,
            "sortCol": "TIME",          // optional
            "sortDir": "asc|desc",      // optional
            "filters": {...},             // optional
            "request_id": "uuid-like"   // optional client correlation id
          }

        Response:
          {
            "type": "table_window_result",
            "status": "ok",
            "data": {
              "request_id": "...",
              "window_start": 800,
              "window_end": 1700,
              "total_count": 52340,
              "records": [...]
            }
          }
        """
        start_row = int(data.get("startRow", 0))
        end_row = int(data.get("endRow", start_row + 100))
        margin = int(data.get("margin", TABLE_DEFAULT_MARGIN))
        sort_col = data.get("sortCol")
        sort_dir = data.get("sortDir")
        request_id = data.get("request_id")
        started_at = time.perf_counter()

        self._debug_log(
            "table_window request "
            f"id={request_id} start={start_row} end={end_row} margin={margin} "
            f"sort={sort_col}:{sort_dir}"
        )

        try:
            result = await asyncio.to_thread(
                self.store.get_table_window,
                start_row=start_row,
                end_row=end_row,
                margin=margin,
                sort_col=sort_col,
                sort_dir=sort_dir,
            )

            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            self._debug_log(
                "table_window result "
                f"id={request_id} total={result.get('total_count', 0)} "
                f"records={len(result.get('records', []))} elapsed_ms={elapsed_ms}"
            )

            await self._send(websocket, {
                "type": "table_window_result",
                "status": "ok",
                "data": {
                    "request_id": request_id,
                    **result,
                },
            })
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            self._debug_log(
                "table_window error "
                f"id={request_id} elapsed_ms={elapsed_ms} error={exc}"
            )
            await self._send(websocket, {
                "type": "table_window_result",
                "status": "error",
                "data": {
                    "request_id": request_id,
                    "detail": str(exc),
                },
            })

    async def action_get_map_window(
        self,
        websocket: WebSocketServerProtocol,
        data: dict,
    ) -> None:
        """
        Return a time-based window of the filtered dataset for the map player.

        Request:
          {
            "action": "get_map_window",
            "current_time": 12345,         // required, seconds or parseable time
            "window_before": 12,           // optional, seconds before current_time
            "window_after": 0,             // optional, seconds after current_time
            "max_points": 500,             // optional cap for frontend rendering
            "request_id": "..."           // optional client correlation id
          }

        Response:
          {
            "type": "map_window_result",
            "status": "ok",
            "data": { "request_id": "...", "records": [ ... ] }
          }
        """
        request_id = data.get("request_id")
        current_time = data.get("current_time")
        window_before = int(data.get("window_before", MAP_DEFAULT_WINDOW_BEFORE_SECONDS))
        window_after = int(data.get("window_after", MAP_DEFAULT_WINDOW_AFTER_SECONDS))
        max_points = int(data.get("max_points", MAP_MAX_POINTS))

        result = await asyncio.to_thread(
            self.store.get_map_window,
            current_time=current_time,
            window_before=window_before,
            window_after=window_after,
            max_points=max_points,
        )

        await self._send(websocket, {
            "type": "map_window_result",
            "status": "ok",
            "data": {
                "request_id": request_id,
                **result,
            },
        })

    # ── TODO: add new action handlers below ──────────────────────────────────
    #
    # async def action_your_new_action(
    #     self,
    #     websocket: WebSocketServerProtocol,
    #     data     : dict,
    # ) -> None:
    #     """Docstring: what this action does, request/response shape."""
    #     # 1. Extract params from `data`
    #     # 2. Call self.store or any service
    #     # 3. Send result back
    #     result = {}
    #     await self._send(websocket, {
    #         "type"  : "your_new_action_result",
    #         "status": "ok",
    #         "data"  : result,
    #     })

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _send(websocket: WebSocketServerProtocol, payload: dict) -> None:
        """Serialise and send a response dict. Silently drops if disconnected."""
        try:
            message = await asyncio.to_thread(
                json.dumps,
                payload,
                default=str,
                separators=(",", ":"),
            )
            await websocket.send(message)
        except Exception:
            pass   # client disconnected mid-response — ignore
