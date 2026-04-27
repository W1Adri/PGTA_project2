import io
import uvicorn
import os
import sys
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

from asterix_decoder.database.asterix_pandas import AsterixPandas
from connections.websocket_handler import broadcast_message
from user_actions.user_actions_manager import Actions


def create_api(store: AsterixPandas, actions: Actions) -> FastAPI:
    """Build and return the configured FastAPI application."""

    api = FastAPI(title="ASTERIX Decoder API")

    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # safe — only reachable on localhost
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Liveness ──────────────────────────────────────────────────────────────
    @api.get("/health")
    def health():
        return {"status": "ok", "records": len(store)}

    # ── ASTERIX binary upload ─────────────────────────────────────────────────
    @api.post("/upload")
    async def upload_binary(file: UploadFile = File(...)):
        """
        Receive an ASTERIX binary file (.ast / .bin), decode it, and populate
        the in-memory AsterixPandas.

        Returns a metadata summary so the frontend can update its UI state
        immediately (record count, time range, unique aircraft list, etc.)
        without waiting for a WebSocket round-trip.
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided.")

        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="File is empty.")

        actions._debug_log(
            f"upload start filename={file.filename} size={len(raw_bytes)}"
        )

        last_stage: str | None = None

        def report_progress(detail: dict) -> None:
            nonlocal last_stage
            broadcast_message({
                "type": "decode_progress",
                "status": "ok",
                "data": detail,
            })
            stage = detail.get("stage")
            if stage and stage != last_stage:
                last_stage = stage
                actions._debug_log(
                    "decode_progress "
                    f"stage={stage} percent={detail.get('percent')} "
                    f"current={detail.get('current')}/{detail.get('total')}"
                )

        try:
            from asterix_decoder.decoder_service import decode_asterix

            # Always start from a clean in-memory dataset per upload session.
            store.clear()
            df = decode_asterix(raw_bytes, progress_callback=report_progress)
            store.load_dataframe(df)
            meta = store.get_metadata()
            actions._debug_log(
                "upload complete "
                f"records={meta.get('record_count')} "
                f"columns={len(meta.get('columns', []))}"
            )

            return meta

        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Decode error: {exc}")

    # ── CSV download ──────────────────────────────────────────────────────────
    @api.get("/download/csv")
    def download_csv():
        """Return the current store data as a downloadable CSV file."""
        if len(store) == 0:
            raise HTTPException(status_code=404, detail="No data loaded yet.")

        csv_bytes = store.to_csv_bytes()
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=decoded_asterix.csv"
            },
        )

    # ── Table Data (AG Grid) ──────────────────────────────────────────────────
    @api.post("/table_data")
    async def get_table_data(request: Request):
        """Return paginated and optionally filtered data for the frontend data grid."""
        try:
            body = await request.json()
        except Exception:
            body = {}

        start_row = body.get("startRow", 0)
        end_row = body.get("endRow", 100)
        sort_col = body.get("sortCol")
        sort_dir = body.get("sortDir")
        
        result = store.filter_paginated(
            start_row=start_row,
            end_row=end_row,
            sort_col=sort_col,
            sort_dir=sort_dir,
        )
        return result

    # ── Static frontend — MUST be last so API routes take priority ────────────
    api.mount("/", StaticFiles(directory=resource_path("ui"), html=True), name="ui")

    return api


def start_api_server(api: FastAPI, port: int) -> None:
    """Run uvicorn in the calling thread (blocking). Designed for daemon threads."""
    config = uvicorn.Config(
        app=api,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    uvicorn.Server(config).run()


def resource_path(relative: str) -> str:
    """Devuelve la ruta correcta tanto en desarrollo como en el ejecutable."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.abspath("."), relative)
