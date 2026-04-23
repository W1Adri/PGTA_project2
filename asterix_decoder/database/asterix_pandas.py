"""
asterix_pandas.py
──────────────────────────────────────────────────────────────────────────────
Thread-safe in-memory store for decoded ASTERIX data.

The DataFrame schema is **dynamic** — it mirrors whatever columns the decoder
produces (e.g. CAT, SAC, SIC, TIME, LAT, LON, FL, TARGET_IDENTIFICATION …).
"""

import io
import threading
from typing import Any

import pandas as pd

from asterix_decoder.database.filters import AsterixFilters

class AsterixPandas:
    """Thread-safe in-memory store for a decoded ASTERIX session."""

    def __init__(self):
        self._lock = threading.RLock()
        self._df: pd.DataFrame = pd.DataFrame()
        self._filters = AsterixFilters()

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
            self._filters.set_base_dataframe(self._df)
            self._filters.apply_filters(categories=["CAT021", "CAT048"])
        print(f"[Store] Loaded {len(self._df):,} records  ({len(self._df.columns)} columns).")

    # ── Querying ──────────────────────────────────────────────────────────────

    def _col_from(self, df: pd.DataFrame, *candidates: str) -> str | None:
        """Return the first matching column name in the provided DataFrame."""
        for c in candidates:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _seconds_to_hms(seconds: float | int) -> str:
        sec = max(0, int(seconds)) % 86400
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def apply_temporary_filters(self, **filters: Any) -> dict[str, Any]:
        """Rebuild the temporary filtered DataFrame from the original DataFrame."""
        with self._lock:
            filtered_df = self._filters.apply_filters(**filters)
            return {
                "active_filters": self._filters.get_active_filters(),
                "count": len(filtered_df),
            }

    def reset_temporary_filters(self) -> None:
        with self._lock:
            self._filters.apply_filters(categories=["CAT021", "CAT048"])

    def _current_df(self) -> pd.DataFrame:
        return self._filters.get_filtered_dataframe()

    def filter(
        self,
        **kwargs
    ) -> list[dict]:
        """
        Apply optional filters and return ALL matching records as dicts.
        """
        with self._lock:
            if kwargs:
                df = self._filters.apply_filters(**kwargs)
            else:
                df = self._current_df()
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
            if kwargs:
                df = self._filters.apply_filters(**kwargs)
            else:
                df = self._current_df()
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

    def get_table_window(
        self,
        start_row: int,
        end_row: int,
        *,
        margin: int = 400,
        sort_col: str | None = None,
        sort_dir: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Return a window around a requested visible range.

        The returned records are contiguous in the filtered/sorted index space,
        and include extra rows on both sides to reduce round-trips while scrolling.
        """
        with self._lock:
            if kwargs:
                df = self._filters.apply_filters(**kwargs)
            else:
                df = self._current_df()
            total_count = len(df)
            if total_count == 0:
                return {
                    "records": [],
                    "total_count": 0,
                    "window_start": 0,
                    "window_end": 0,
                }

            if sort_col and sort_col in df.columns:
                ascending = (sort_dir != "desc")
                df = df.sort_values(by=sort_col, ascending=ascending)

            safe_start = max(0, min(int(start_row), total_count))
            safe_end = max(safe_start, min(int(end_row), total_count))
            safe_margin = max(0, int(margin))

            window_start = max(0, safe_start - safe_margin)
            window_end = min(total_count, safe_end + safe_margin)

            sliced_df = df.iloc[window_start:window_end]
            records = sliced_df.astype(object).where(pd.notna(sliced_df), None).to_dict(orient="records")

            return {
                "records": records,
                "total_count": total_count,
                "window_start": window_start,
                "window_end": window_end,
            }

    def get_all(self) -> list[dict]:
        """Return every record (no filters)."""
        with self._lock:
            df = self._current_df()
            if df.empty:
                return []
            return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_metadata(self) -> dict:
        """Lightweight summary returned after /upload succeeds."""
        with self._lock:
            if self._df.empty:
                return {
                    "record_count":      0,
                    "record_count_original": 0,
                    "columns":           [],
                    "time_start":        None,
                    "time_end":          None,
                    "unique_callsigns":  [],
                    "unique_categories": [],
                    "unique_squawks":    [],
                    "category_filter_options": self._filters.get_category_filter_options(),
                    "target_identification_filter": {
                        "groups": [],
                        "all_values": [],
                    },
                    "altitude_min":      None,
                    "altitude_max":      None,
                }

            base_df = self._df
            filtered_df = self._current_df()
            meta: dict[str, Any] = {
                "record_count": len(filtered_df),
                "record_count_original": len(base_df),
                "columns":      list(base_df.columns),
                "category_filter_options": self._filters.get_category_filter_options(),
                "target_identification_filter": self._filters.get_target_identification_filter(),
            }

            # Time
            time_col = self._col_from(base_df, "TIME", "timestamp")
            if time_col and time_col in base_df.columns:
                t = pd.to_numeric(
                    base_df[time_col].map(AsterixFilters._parse_time_filter_value),
                    errors="coerce",
                )
                if t.notna().any():
                    meta["time_start"] = self._seconds_to_hms(float(t.min()))
                    meta["time_end"] = self._seconds_to_hms(float(t.max()))
                else:
                    meta["time_start"] = None
                    meta["time_end"] = None
            else:
                meta["time_start"] = None
                meta["time_end"]   = None

            # Callsigns
            id_col = self._col_from(base_df, "TARGET_IDENTIFICATION", "callsign")
            if id_col:
                meta["unique_callsigns"] = sorted(
                    base_df[id_col].dropna().astype(str).unique().tolist()
                )
            else:
                meta["unique_callsigns"] = []

            # Categories
            cat_col = self._col_from(base_df, "CAT", "category")
            if cat_col:
                meta["unique_categories"] = sorted(
                    base_df[cat_col].dropna().astype(str).unique().tolist()
                )
            else:
                meta["unique_categories"] = []

            # Squawks
            sqk_col = self._col_from(base_df, "MODE_3/A", "squawk")
            if sqk_col:
                meta["unique_squawks"] = sorted(
                    base_df[sqk_col].dropna().astype(str).unique().tolist()
                )
            else:
                meta["unique_squawks"] = []

            # Altitude range
            alt_col = self._col_from(base_df, "FL", "altitude_ft")
            if alt_col:
                alt = pd.to_numeric(base_df[alt_col], errors="coerce")
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
            current_df = self._current_df()
            current_df.to_csv(
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
            self._filters.clear()
            print("[Store] Cleared.")

    def __len__(self) -> int:
        with self._lock:
            return len(self._df)
