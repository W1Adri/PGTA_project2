import uvicorn
import os 
import sys
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database.asterix_pandas import AsterixStore
from user_actions.user_actions_manager import Actions


def create_api(store: AsterixStore, actions: Actions) -> FastAPI:
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
        the in-memory AsterixStore.

        Returns a metadata summary so the frontend can update its UI state
        immediately (record count, time range, unique aircraft list, etc.)
        without waiting for a WebSocket round-trip.
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided.")

        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="File is empty.")

        try:
            # ── TODO: plug your ASTERIX decoder here ──────────────────────────
            # Example using the `asterix` library (pip install asterix):
            #
            #   import asterix
            #   decoded_records = asterix.parse(raw_bytes)
            #   store.load(decoded_records)
            #
            # store.load() must clear old data and populate the DataFrame.
            # See database/asterix_store.py for the expected schema.
            # ─────────────────────────────────────────────────────────────────

            # Placeholder — remove once decoder is integrated
            store.load_raw_placeholder(raw_bytes)

            return store.get_metadata()

        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Decode error: {exc}")

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