"""
Expected DataFrame schema (one row = one ASTERIX target report):
──────────────────────────────────────────────────────────────────
  timestamp       datetime64[ns, UTC]   — absolute UTC time of the plot
  track_number    Int64                 — system track number
  callsign        str                   — aircraft callsign / flight ID
  squawk          str                   — Mode-A code (octal string)
  latitude        float64               — WGS-84 latitude  (degrees)
  longitude       float64               — WGS-84 longitude (degrees)
  altitude_ft     float64               — Mode-C altitude  (feet)
  ground_speed    float64               — knots
  heading         float64               — degrees true
  category        str                   — ASTERIX category (e.g. "CAT048")
  data_source     str                   — SAC/SIC string  "SAC:SIC"
"""

import threading
from typing import Any

import numpy as np
import pandas as pd

# Canonical column definition — guarantees consistent shape even when empty
_COLUMNS: list[str] = [
    "timestamp",
    "track_number",
    "callsign",
    "squawk",
    "latitude",
    "longitude",
    "altitude_ft",
    "ground_speed",
    "heading",
    "category",
    "data_source",
]

_DTYPES: dict[str, Any] = {
    "track_number" : "Int64",
    "callsign"     : "string",
    "squawk"       : "string",
    "latitude"     : "float64",
    "longitude"    : "float64",
    "altitude_ft"  : "float64",
    "ground_speed" : "float64",
    "heading"      : "float64",
    "category"     : "string",
    "data_source"  : "string",
}


def _empty_df() -> pd.DataFrame:
    df = pd.DataFrame(columns=_COLUMNS)
    return df.astype(_DTYPES)


class AsterixStore:
    """Thread-safe in-memory store for a decoded ASTERIX session."""

    def __init__(self):
        self._lock = threading.RLock()
        self._df   = _empty_df()

    # ── Loading ───────────────────────────────────────────────────────────────

    def load(self, records: list[dict]) -> None:
        """
        Replace the current dataset with freshly decoded records.

        Parameters
        ----------
        records : list[dict]
            Each dict must contain the keys defined in _COLUMNS.
            Called by the ASTERIX decoder inside api.py after parsing.
        """
        with self._lock:
            if not records:
                self._df = _empty_df()
                return

            df = pd.DataFrame(records, columns=_COLUMNS)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.astype(_DTYPES)
            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)
            self._df = df

        print(f"[Store] Loaded {len(self._df):,} records.")

    def load_raw_placeholder(self, raw_bytes: bytes) -> None:
        """
        Temporary placeholder — replace with real decoder integration.
        Populates the store with a minimal synthetic record so the frontend
        can confirm the pipeline works end-to-end before the decoder is ready.
        """
        import random, datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        fake = [
            {
                "timestamp"   : now + datetime.timedelta(seconds=i * 4),
                "track_number": 1000 + i,
                "callsign"    : f"IBE{100 + i:03d}",
                "squawk"      : f"{random.randint(0, 7777):04o}",
                "latitude"    : 41.0 + random.uniform(-2, 2),
                "longitude"   : 2.0  + random.uniform(-2, 2),
                "altitude_ft" : random.uniform(5000, 40000),
                "ground_speed": random.uniform(200, 500),
                "heading"     : random.uniform(0, 360),
                "category"    : "CAT048",
                "data_source" : "010:020",
            }
            for i in range(50)
        ]
        self.load(fake)

    # ── Querying ──────────────────────────────────────────────────────────────

    def filter(
        self,
        *,
        callsigns     : list[str]   | None = None,
        categories    : list[str]   | None = None,
        squawks       : list[str]   | None = None,
        altitude_min  : float | None = None,
        altitude_max  : float | None = None,
        time_start    : str   | None = None,   # ISO-8601 string
        time_end      : str   | None = None,   # ISO-8601 string
    ) -> list[dict]:
        """
        Apply one or more filters to the dataset and return matching records
        as a list of dicts, ready for JSON serialisation.

        All parameters are optional; omitting a parameter means "no restriction
        on that dimension".
        """
        with self._lock:
            df = self._df

            if callsigns:
                df = df[df["callsign"].isin(callsigns)]
            if categories:
                df = df[df["category"].isin(categories)]
            if squawks:
                df = df[df["squawk"].isin(squawks)]
            if altitude_min is not None:
                df = df[df["altitude_ft"] >= altitude_min]
            if altitude_max is not None:
                df = df[df["altitude_ft"] <= altitude_max]
            if time_start:
                ts = pd.Timestamp(time_start, tz="UTC")
                df = df[df["timestamp"] >= ts]
            if time_end:
                te = pd.Timestamp(time_end, tz="UTC")
                df = df[df["timestamp"] <= te]

            # Convert timestamps to ISO strings for JSON
            out = df.copy()
            out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            return out.to_dict(orient="records")

    def get_all(self) -> list[dict]:
        """Return every record (no filters). Useful on initial load."""
        return self.filter()

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_metadata(self) -> dict:
        """
        Lightweight summary returned immediately after /upload succeeds.
        The frontend uses this to populate filter dropdowns and the time slider.
        """
        with self._lock:
            if self._df.empty:
                return {
                    "record_count"    : 0,
                    "time_start"      : None,
                    "time_end"        : None,
                    "unique_callsigns": [],
                    "unique_categories": [],
                    "unique_squawks"  : [],
                    "altitude_min"    : None,
                    "altitude_max"    : None,
                }
            df = self._df
            return {
                "record_count"     : len(df),
                "time_start"       : df["timestamp"].min().isoformat(),
                "time_end"         : df["timestamp"].max().isoformat(),
                "unique_callsigns" : sorted(df["callsign"].dropna().unique().tolist()),
                "unique_categories": sorted(df["category"].dropna().unique().tolist()),
                "unique_squawks"   : sorted(df["squawk"].dropna().unique().tolist()),
                "altitude_min"     : float(df["altitude_ft"].min()),
                "altitude_max"     : float(df["altitude_ft"].max()),
            }

    def clear(self) -> None:
        with self._lock:
            self._df = _empty_df()
            print("[Store] Cleared.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        with self._lock:
            return len(self._df)
