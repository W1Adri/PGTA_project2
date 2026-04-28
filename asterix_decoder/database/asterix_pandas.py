"""
asterix_pandas.py
──────────────────────────────────────────────────────────────────────────────
Thread-safe in-memory store for decoded ASTERIX data.

The DataFrame schema is **dynamic** — it mirrors whatever columns the decoder
produces (e.g. CAT, SAC, SIC, TIME, LAT, LON, FL, TARGET_IDENTIFICATION …).
"""

import io
import math
import re
import threading
from typing import Any

import pandas as pd

from asterix_decoder.database.filters import AsterixFilters

TABLE_DEFAULT_MARGIN = 40
TABLE_MAX_MARGIN = 60
TABLE_MAX_WINDOW_ROWS = 180
TABLE_MAX_PAGE_ROWS = 180

MAP_DEFAULT_WINDOW_BEFORE_SECONDS = 12
MAP_DEFAULT_WINDOW_AFTER_SECONDS = 0
MAP_MAX_WINDOW_BEFORE_SECONDS = 60
MAP_MAX_WINDOW_AFTER_SECONDS = 5
MAP_MAX_POINTS = 500


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

    @staticmethod
    def _time_bucket_and_millis(value: Any) -> tuple[float | None, int | None]:
        """Parse a time-like value into (ceil-second bucket, milliseconds)."""
        if value is None:
            return None, None

        try:
            if pd.isna(value):
                return None, None
        except Exception:
            pass

        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return None, None

        match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?(?::(\d{1,3}))?$", text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            second = int(match.group(3) or 0)
            ms_text = match.group(4) or "0"
            millis = int(ms_text.ljust(3, "0")[:3])
            total = (hour * 3600) + (minute * 60) + second + (millis / 1000.0)
            return float(math.ceil(total)), millis

        try:
            numeric = float(text)
            if math.isfinite(numeric):
                frac = numeric - math.floor(numeric)
                millis = int(round(frac * 1000))
                millis = max(0, min(999, millis))
                return float(math.ceil(numeric)), millis
        except Exception:
            pass

        parsed = pd.to_datetime(text, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None, None

        timestamp = float(parsed.timestamp())
        frac = timestamp - math.floor(timestamp)
        millis = int(round(frac * 1000))
        millis = max(0, min(999, millis))
        return float(math.ceil(timestamp)), millis

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
        max_rows: int = TABLE_MAX_PAGE_ROWS,
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
            
            safe_start = max(0, min(int(start_row), total_count))
            safe_end = max(safe_start, min(int(end_row), total_count))
            try:
                page_limit = int(max_rows)
            except (TypeError, ValueError):
                page_limit = TABLE_MAX_PAGE_ROWS
            if page_limit <= 0:
                page_limit = TABLE_MAX_PAGE_ROWS
            safe_end = min(safe_end, safe_start + page_limit)

            sliced_df = df.iloc[safe_start:safe_end]
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
        margin: int = TABLE_DEFAULT_MARGIN,
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
            requested_end = max(safe_start, min(int(end_row), total_count))
            safe_end = min(requested_end, safe_start + TABLE_MAX_WINDOW_ROWS)
            safe_margin = min(max(0, int(margin)), TABLE_MAX_MARGIN)

            window_start = max(0, safe_start - safe_margin)
            window_end = min(total_count, safe_end + safe_margin)
            if window_end - window_start > TABLE_MAX_WINDOW_ROWS:
                window_end = window_start + TABLE_MAX_WINDOW_ROWS
                if window_end < safe_end:
                    window_end = safe_end
                    window_start = max(0, window_end - TABLE_MAX_WINDOW_ROWS)

            sliced_df = df.iloc[window_start:window_end]
            records = sliced_df.astype(object).where(pd.notna(sliced_df), None).to_dict(orient="records")

            return {
                "records": records,
                "total_count": total_count,
                "window_start": window_start,
                "window_end": window_end,
            }

    def get_map_window(
        self,
        current_time: Any,
        *,
        window_before: int = MAP_DEFAULT_WINDOW_BEFORE_SECONDS,
        window_after: int = MAP_DEFAULT_WINDOW_AFTER_SECONDS,
        max_points: int = MAP_MAX_POINTS,
        **kwargs,
    ) -> dict[str, Any]:
        """Return the filtered records around a time cursor for the map player."""
        with self._lock:
            if kwargs:
                df = self._filters.apply_filters(**kwargs)
            else:
                df = self._current_df()
            if df.empty:
                return {
                    "records": [],
                    "count": 0,
                    "center_seconds": None,
                    "window_start_seconds": None,
                    "window_end_seconds": None,
                }

            time_col = self._col_from(df, "TIME", "timestamp")
            lat_col = self._col_from(df, "LAT", "latitude")
            lon_col = self._col_from(df, "LON", "longitude")
            if not time_col or not lat_col or not lon_col:
                return {
                    "records": [],
                    "count": 0,
                    "center_seconds": None,
                    "window_start_seconds": None,
                    "window_end_seconds": None,
                }

            center_seconds = AsterixFilters._parse_time_filter_value(current_time)
            if center_seconds is None:
                return {
                    "records": [],
                    "count": 0,
                    "center_seconds": None,
                    "window_start_seconds": None,
                    "window_end_seconds": None,
                }

            before = min(max(0, int(window_before)), MAP_MAX_WINDOW_BEFORE_SECONDS)
            after = min(max(0, int(window_after)), MAP_MAX_WINDOW_AFTER_SECONDS)
            try:
                requested_points = int(max_points)
            except (TypeError, ValueError):
                requested_points = MAP_MAX_POINTS
            point_limit = MAP_MAX_POINTS if requested_points <= 0 else min(requested_points, MAP_MAX_POINTS)
            lower_bound = float(center_seconds) - before
            upper_bound = float(center_seconds) + after

            time_series = pd.to_numeric(
                df[time_col].map(AsterixFilters._parse_time_filter_value),
                errors="coerce",
            )
            position_mask = df[lat_col].notna() & df[lon_col].notna()
            window_mask = time_series.between(lower_bound, upper_bound) & position_mask

            window_df = df.loc[window_mask].copy()
            if window_df.empty:
                return {
                    "records": [],
                    "count": 0,
                    "center_seconds": float(center_seconds),
                    "window_start_seconds": float(lower_bound),
                    "window_end_seconds": float(upper_bound),
                }

            window_time_series = pd.to_numeric(
                window_df[time_col].map(AsterixFilters._parse_time_filter_value),
                errors="coerce",
            )
            window_df["__row_id"] = window_df.index.astype(int)
            window_df["__time_seconds"] = window_time_series

            parsed_time_parts = window_df[time_col].map(self._time_bucket_and_millis)
            window_df["__time_bucket"] = pd.to_numeric(
                parsed_time_parts.map(lambda value: value[0] if isinstance(value, tuple) else None),
                errors="coerce",
            )
            window_df["__time_millis"] = pd.to_numeric(
                parsed_time_parts.map(lambda value: value[1] if isinstance(value, tuple) else None),
                errors="coerce",
            ).fillna(-1).astype(int)

            target_col = self._col_from(
                window_df,
                "TARGET_IDENTIFICATION",
                "target_identification",
                "callsign",
            )
            heading_col = self._col_from(window_df, "HEADING", "HDG", "heading")
            if target_col:
                window_df["__target_id"] = window_df[target_col].astype(str).str.strip().str.upper()
                dedupe_mask = (
                    window_df["__target_id"].notna()
                    & window_df["__target_id"].ne("")
                    & window_df["__target_id"].ne("NAN")
                    & window_df["__time_bucket"].notna()
                )

                if dedupe_mask.any():
                    deduped_rows: list[pd.Series] = []
                    grouped_duplicates = window_df.loc[dedupe_mask].sort_values(
                        by=["__target_id", "__time_bucket", "__time_millis", "__row_id"],
                        ascending=[True, True, True, True],
                    ).groupby(["__target_id", "__time_bucket"], sort=False)

                    for _, group in grouped_duplicates:
                        winner = group.iloc[-1].copy()
                        if heading_col and pd.isna(winner.get(heading_col)):
                            heading_candidates = group[group[heading_col].notna()]
                            if not heading_candidates.empty:
                                winner[heading_col] = heading_candidates.iloc[-1][heading_col]
                        deduped_rows.append(winner)

                    deduped = pd.DataFrame(deduped_rows)
                    window_df = pd.concat([window_df.loc[~dedupe_mask], deduped], axis=0)

            window_df = window_df.sort_values(by=["__time_seconds", "__row_id"], ascending=[True, True])

            if point_limit > 0 and len(window_df) > point_limit:
                center_index = window_df["__time_seconds"].sub(float(center_seconds)).abs().idxmin()
                if center_index in window_df.index:
                    center_pos = window_df.index.get_loc(center_index)
                else:
                    center_pos = len(window_df) // 2
                half = point_limit // 2
                start = max(0, center_pos - half)
                end = min(len(window_df), start + point_limit)
                start = max(0, end - point_limit)
                window_df = window_df.iloc[start:end]

            window_df = self._build_map_payload_frame(window_df, time_col, lat_col, lon_col)
            records = (
                window_df.astype(object)
                .where(pd.notna(window_df), None)
                .to_dict(orient="records")
            )

            return {
                "records": records,
                "count": len(records),
                "center_seconds": float(center_seconds),
                "window_start_seconds": float(lower_bound),
                "window_end_seconds": float(upper_bound),
            }

    def _build_map_payload_frame(
        self,
        window_df: pd.DataFrame,
        time_col: str,
        lat_col: str,
        lon_col: str,
    ) -> pd.DataFrame:
        """Return only the fields the Leaflet player needs to draw a frame."""
        payload = pd.DataFrame(index=window_df.index)

        def add_alias(output_col: str, *candidates: str | None) -> None:
            for column in candidates:
                if column and column in window_df.columns:
                    payload[output_col] = window_df[column]
                    return

        add_alias("CAT", "CAT", "category")
        add_alias("TIME", time_col, "TIME", "timestamp")
        add_alias("LAT", lat_col, "LAT", "latitude")
        add_alias("LON", lon_col, "LON", "longitude")
        add_alias("TARGET_IDENTIFICATION", "TARGET_IDENTIFICATION", "callsign", "target_identification")
        add_alias("TARGET_ADDRESS", "TARGET_ADDRESS", "target_address", "ICAO", "MODE_S")
        add_alias("TRACK_NUMBER", "TRACK_NUMBER", "track_number")
        add_alias("HEADING", "HEADING", "HDG", "heading")
        add_alias("MODE_3/A", "MODE_3/A", "squawk", "MODE_3A", "MODE_3_A")
        add_alias("FL", "FL", "altitude_ft", "ALTITUDE", "altitude")
        add_alias("__row_id", "__row_id")
        add_alias("__time_seconds", "__time_seconds")

        return payload

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
                    "lat_min":           None,
                    "lat_max":           None,
                    "lon_min":           None,
                    "lon_max":           None,
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

            # Global map bounds (all loaded points)
            lat_col = self._col_from(base_df, "LAT", "latitude")
            lon_col = self._col_from(base_df, "LON", "longitude")
            if lat_col and lon_col:
                lat = pd.to_numeric(base_df[lat_col], errors="coerce")
                lon = pd.to_numeric(base_df[lon_col], errors="coerce")
                mask = lat.notna() & lon.notna()
                if mask.any():
                    meta["lat_min"] = float(lat[mask].min())
                    meta["lat_max"] = float(lat[mask].max())
                    meta["lon_min"] = float(lon[mask].min())
                    meta["lon_max"] = float(lon[mask].max())
                else:
                    meta["lat_min"] = None
                    meta["lat_max"] = None
                    meta["lon_min"] = None
                    meta["lon_max"] = None
            else:
                meta["lat_min"] = None
                meta["lat_max"] = None
                meta["lon_min"] = None
                meta["lon_max"] = None

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
