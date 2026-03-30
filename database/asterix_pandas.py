"""
asterix_pandas.py
──────────────────────────────────────────────────────────────────────────────
Thread-safe in-memory store for decoded ASTERIX data.

The DataFrame schema is **dynamic** — it mirrors whatever columns the decoder
produces (e.g. CAT, SAC, SIC, TIME, LAT, LON, FL, TARGET_IDENTIFICATION …).
"""

import io
import os
import threading
from typing import Any

import pandas as pd

DB_FILE = os.path.join(os.path.dirname(__file__), "decoded_data.pkl")

class AsterixPandas:
    """Thread-safe in-memory store for a decoded ASTERIX session."""

    def __init__(self):
        self._lock = threading.RLock()
        self._df: pd.DataFrame = pd.DataFrame()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        try:
            if os.path.exists(DB_FILE):
                self._df = pd.read_pickle(DB_FILE)
                print(f"[Store] Initialized from disk: {len(self._df):,} records.")
            else:
                self._df = pd.DataFrame()
        except Exception as e:
            print(f"[Store] Failed to load from disk: {e}")
            self._df = pd.DataFrame()

    def _save_to_disk(self) -> None:
        try:
            if not self._df.empty:
                self._df.to_pickle(DB_FILE)
                print(f"[Store] Saved {len(self._df):,} records to disk.")
            else:
                if os.path.exists(DB_FILE):
                    os.remove(DB_FILE)
        except Exception as e:
            print(f"[Store] Failed to save to disk: {e}")

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_dataframe(self, df: pd.DataFrame) -> None:
        """
        Replace the current dataset with a decoded DataFrame from the decoder.

        Parameters
        ----------
        df : pd.DataFrame
            Output of ``decode_asterix()``.
        """
        with self._lock:
            self._df = df.reset_index(drop=True)
            self._save_to_disk()
        print(f"[Store] Loaded {len(self._df):,} records  ({len(self._df.columns)} columns).")

    # ── Querying ──────────────────────────────────────────────────────────────

    def _col(self, *candidates: str) -> str | None:
        """Return the first column name found in the current DataFrame."""
        for c in candidates:
            if c in self._df.columns:
                return c
        return None

    def _apply_filters(
        self,
        *,
        callsigns: list[str] | None = None,
        categories: list[str] | None = None,
        squawks: list[str] | None = None,
        altitude_min: float | None = None,
        altitude_max: float | None = None,
        time_start: str | None = None,
        time_end: str | None = None,
    ) -> pd.DataFrame:
        if self._df.empty:
            return self._df
            
        df = self._df

        # — Callsign / Target ID —
        id_col = self._col("TARGET_IDENTIFICATION", "callsign")
        if callsigns and id_col:
            df = df[df[id_col].isin(callsigns)]

        # — Category —
        cat_col = self._col("CAT", "category")
        if categories and cat_col:
            df = df[df[cat_col].isin(categories)]

        # — Squawk —
        sqk_col = self._col("MODE_3/A", "squawk")
        if squawks and sqk_col:
            df = df[df[sqk_col].astype(str).isin(squawks)]

        # — Altitude (flight level) —
        alt_col = self._col("FL", "altitude_ft")
        if alt_col:
            alt = pd.to_numeric(df[alt_col], errors="coerce")
            if altitude_min is not None:
                df = df[alt >= altitude_min]
                alt = pd.to_numeric(df[alt_col], errors="coerce")
            if altitude_max is not None:
                df = df[alt <= altitude_max]

        # — Time range —
        time_col = self._col("TIME", "timestamp")
        if time_col:
            t = pd.to_numeric(df[time_col], errors="coerce")
            if time_start is not None:
                df = df[t >= float(time_start)] if t.notna().any() else df
            if time_end is not None:
                t = pd.to_numeric(df[time_col], errors="coerce")
                df = df[t <= float(time_end)] if t.notna().any() else df

        return df

    def filter(
        self,
        **kwargs
    ) -> list[dict]:
        """
        Apply optional filters and return ALL matching records as dicts.
        """
        with self._lock:
            df = self._apply_filters(**kwargs)
            if df.empty:
                return []
            return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")

    def filter_paginated(
        self,
        start_row: int,
        end_row: int,
        sort_col: str | None = None,
        sort_dir: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Apply filters, sort, paginate, and return records + total count.
        """
        with self._lock:
            df = self._apply_filters(**kwargs)
            if df.empty:
                return {"records": [], "count": 0}
            
            total_count = len(df)
            
            if sort_col and sort_col in df.columns:
                ascending = (sort_dir != "desc")
                df = df.sort_values(by=sort_col, ascending=ascending)
            
            sliced_df = df.iloc[start_row:end_row]
            records = sliced_df.astype(object).where(pd.notna(sliced_df), None).to_dict(orient="records")
            
            return {
                "records": records,
                "count": total_count
            }

    def get_all(self) -> list[dict]:
        """Return every record (no filters)."""
        with self._lock:
            if self._df.empty:
                return []
            return self._df.astype(object).where(pd.notna(self._df), None).to_dict(orient="records")

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_metadata(self) -> dict:
        """Lightweight summary returned after /upload succeeds."""
        with self._lock:
            if self._df.empty:
                return {
                    "record_count":      0,
                    "columns":           [],
                    "time_start":        None,
                    "time_end":          None,
                    "unique_callsigns":  [],
                    "unique_categories": [],
                    "unique_squawks":    [],
                    "altitude_min":      None,
                    "altitude_max":      None,
                }

            df = self._df
            meta: dict[str, Any] = {
                "record_count": len(df),
                "columns":      list(df.columns),
            }

            # Time
            time_col = self._col("TIME", "timestamp")
            if time_col and time_col in df.columns:
                t = pd.to_numeric(df[time_col], errors="coerce")
                meta["time_start"] = float(t.min()) if t.notna().any() else None
                meta["time_end"]   = float(t.max()) if t.notna().any() else None
            else:
                meta["time_start"] = None
                meta["time_end"]   = None

            # Callsigns
            id_col = self._col("TARGET_IDENTIFICATION", "callsign")
            if id_col:
                meta["unique_callsigns"] = sorted(
                    df[id_col].dropna().astype(str).unique().tolist()
                )
            else:
                meta["unique_callsigns"] = []

            # Categories
            cat_col = self._col("CAT", "category")
            if cat_col:
                meta["unique_categories"] = sorted(
                    df[cat_col].dropna().astype(str).unique().tolist()
                )
            else:
                meta["unique_categories"] = []

            # Squawks
            sqk_col = self._col("MODE_3/A", "squawk")
            if sqk_col:
                meta["unique_squawks"] = sorted(
                    df[sqk_col].dropna().astype(str).unique().tolist()
                )
            else:
                meta["unique_squawks"] = []

            # Altitude range
            alt_col = self._col("FL", "altitude_ft")
            if alt_col:
                alt = pd.to_numeric(df[alt_col], errors="coerce")
                meta["altitude_min"] = float(alt.min()) if alt.notna().any() else None
                meta["altitude_max"] = float(alt.max()) if alt.notna().any() else None
            else:
                meta["altitude_min"] = None
                meta["altitude_max"] = None

            return meta

    # ── CSV export ────────────────────────────────────────────────────────────

    def to_csv_bytes(self) -> bytes:
        """Serialize the current DataFrame to CSV bytes (European format)."""
        with self._lock:
            buf = io.BytesIO()
            self._df.to_csv(
                buf,
                index=False,
                sep=";",
                decimal=",",
                na_rep="N/A",
            )
            return buf.getvalue()

    # ── Housekeeping ──────────────────────────────────────────────────────────

    def clear(self) -> None:
        with self._lock:
            self._df = pd.DataFrame()
            self._save_to_disk()
            print("[Store] Cleared.")

    def __len__(self) -> int:
        with self._lock:
            return len(self._df)
