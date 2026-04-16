import json
from websockets.server import WebSocketServerProtocol

from database.asterix_pandas import AsterixPandas


class Actions:

    def __init__(self, store: AsterixPandas):
        self.store = store

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
        records = self.store.get_all()
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
            "squawks"     : data.get("squawks"),
            "altitude_min": data.get("altitude_min"),
            "altitude_max": data.get("altitude_max"),
            "time_start"  : data.get("time_start"),
            "time_end"    : data.get("time_end"),
        }

        records = self.store.filter(**filters)
        await self._send(websocket, {
            "type"  : "apply_filters_result",
            "status": "ok",
            "data"  : {"records": records[:5000], "count": len(records)},
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
        meta = self.store.get_metadata()
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
            "margin": 400,
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
        margin = int(data.get("margin", 400))
        sort_col = data.get("sortCol")
        sort_dir = data.get("sortDir")
        request_id = data.get("request_id")

        raw_filters = data.get("filters") or {}
        if not isinstance(raw_filters, dict):
            raw_filters = {}

        result = self.store.get_table_window(
            start_row=start_row,
            end_row=end_row,
            margin=margin,
            sort_col=sort_col,
            sort_dir=sort_dir,
            **raw_filters,
        )

        await self._send(websocket, {
            "type": "table_window_result",
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
            await websocket.send(json.dumps(payload, default=str))
        except Exception:
            pass   # client disconnected mid-response — ignore
