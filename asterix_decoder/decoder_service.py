"""
decoder_service.py
──────────────────────────────────────────────────────────────────────────────
Consolidates the full ASTERIX decoding pipeline (notebook Blocks 1–6) into a
single callable entry point for the web application.

    from asterix_decoder.decoder_service import decode_asterix
    final_df = decode_asterix(raw_bytes)      # → pd.DataFrame
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any

import pandas as pd

from asterix_decoder.data_items.data_item import ItemXXX
from asterix_decoder.data_tables.uap_tables import uap021_df, uap048_df
from asterix_decoder.data_tables.csv_table import CSV_CAT021_COLUMNS, CSV_CAT048_COLUMNS
from asterix_decoder.helpers.compute_target_lat_lon import compute_target_lat_lon

# ══════════════════════════════════════════════════════════════════════════════
# Module-level caches (computed once, reused across uploads)
# ══════════════════════════════════════════════════════════════════════════════

_CLASS_MAP: dict[tuple[int, str], type] | None = None
_UAP_DF: pd.DataFrame | None = None
_FRN_MAP: dict[tuple[int, int], Any] | None = None

# Pre-computed FSPEC lookup tables (from notebook Block 3)
_ACTIVE_OFFSETS: tuple[tuple[int, ...], ...] = tuple(
    tuple(i for i in range(7) if (b >> (7 - i)) & 1)
    for b in range(256)
)
_HAS_FX: tuple[bool, ...] = tuple(bool(b & 1) for b in range(256))

# Barcelona TMA bounding box (from notebook Block 6)
_LAT_MIN, _LAT_MAX = 40.9, 41.7
_LON_MIN, _LON_MAX = 1.5, 2.6


# ══════════════════════════════════════════════════════════════════════════════
# Block 2 — Split the binary stream into ASTERIX messages
# ══════════════════════════════════════════════════════════════════════════════

def _split_messages(raw: bytes) -> pd.DataFrame:
    """Walk the binary stream and return a DataFrame with one row per message."""
    view = memoryview(raw)
    total = len(raw)
    rows: list[dict] = []
    offset = 0
    msg_id = 1

    while offset + 3 <= total:
        cat = view[offset]
        length = int.from_bytes(view[offset + 1:offset + 3], "big")

        if length < 3 or offset + length > total:
            raise ValueError(f"Invalid message at offset {offset}: LEN={length}")

        rows.append({
            "message_id":  msg_id,
            "offset":      offset,
            "cat":         cat,
            "length":      length,
            "data_record": bytes(view[offset + 3:offset + length]),
        })
        offset += length
        msg_id += 1

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Block 3 — Parse the FSPEC of each message
# ══════════════════════════════════════════════════════════════════════════════

def _parse_fspec(data_record: bytes) -> tuple[list[int], bytes]:
    frns: list[int] = []
    frn_base: int = 1
    cursor: int = 0
    n: int = len(data_record)

    while cursor < n:
        b = data_record[cursor]
        offsets = _ACTIVE_OFFSETS[b]
        if offsets:
            base = frn_base
            frns += [base + off for off in offsets]
        cursor += 1
        frn_base += 7
        if not _HAS_FX[b]:
            break

    return frns, data_record[cursor:]


# ══════════════════════════════════════════════════════════════════════════════
# Block 4 — Discover item decoder classes and build the UAP
# ══════════════════════════════════════════════════════════════════════════════

def _discover_item_classes(
    cats: list[int],
    base_folder: Path | None = None,
) -> dict[tuple[int, str], type]:
    """Map (cat, item_id) → class loaded dynamically from CATxxx folders."""
    if base_folder is None:
        base_folder = Path(__file__).parent / "data_items"

    class_map: dict[tuple[int, str], type] = {}

    for cat in cats:
        folder = base_folder / f"CAT{cat:03d}"
        if not folder.exists():
            continue

        for file in folder.glob("*.py"):
            if file.name == "__init__.py":
                continue

            module_name = f"dyn_cat{cat:03d}_{file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, file)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for _, cls in inspect.getmembers(module, inspect.isclass):
                if (
                    cls.__module__ == module_name
                    and callable(getattr(cls, "get_item_id", None))
                ):
                    item_id = str(cls.get_item_id()).strip()
                    class_map[(cat, item_id)] = cls

    return class_map


def _build_instance(row: pd.Series, class_map: dict[tuple[int, str], type]):
    """Create one decoder instance for one UAP row."""
    cat = int(row["cat"])
    item_id = str(row["item_id"]).strip()
    item_name = str(row["item_name"])
    length_str = str(row["length_str"])

    cls = class_map.get((cat, item_id))
    if cls is None:
        return ItemXXX(item_name=item_name, length_str=length_str, item_id=item_id)

    try:
        return cls(item_name=item_name, length_str=length_str)
    except TypeError:
        return cls(item_name, length_str)


def _ensure_uap_ready() -> dict[tuple[int, int], Any]:
    """Lazily build and cache the UAP dataframe and FRN→instance map."""
    global _CLASS_MAP, _UAP_DF, _FRN_MAP

    if _FRN_MAP is not None:
        return _FRN_MAP

    _CLASS_MAP = _discover_item_classes([21, 48])

    uap_df = pd.concat([uap021_df, uap048_df], ignore_index=True)
    uap_df["instance"] = uap_df.apply(
        lambda r: _build_instance(r, _CLASS_MAP), axis=1
    )
    _UAP_DF = uap_df

    _FRN_MAP = dict(
        zip(
            uap_df[["cat", "frn"]].apply(tuple, axis=1),
            uap_df["instance"],
        )
    )
    return _FRN_MAP


# ══════════════════════════════════════════════════════════════════════════════
# Block 5 — Decode each message into structured fields
# ══════════════════════════════════════════════════════════════════════════════

def _decode_message(
    cat: int,
    frns: list[int],
    data_fields: bytes,
    frn_map: dict,
) -> dict[str, Any]:
    """Decode a single ASTERIX record into a flat dict of named fields."""
    final_data: dict[str, Any] = {}
    cursor = 0

    for frn in frns:
        instance = frn_map.get((cat, frn))
        if instance is None:
            continue
        delta_cursor, instance_data = instance.decode(data_fields[cursor:])
        final_data.update(instance_data)
        cursor += delta_cursor

    # ── Derived: target lat/lon from polar coords (CAT048) ────────────────
    RHO = final_data.get("RHO")
    THETA = final_data.get("THETA")
    FL = final_data.get("FL")

    if RHO is not None:
        lat, lon = compute_target_lat_lon(RHO, THETA, FL)
        final_data["LAT"] = lat
        final_data["LON"] = lon

    # ── Derived: corrected Mode-C altitude ────────────────────────────────
    if FL is not None:
        BP = final_data.get("BP")
        if BP is not None and FL < 60:
            try:
                # BP might be formatted as '1013,2' from the BDS4.0 decoder
                bp_val = float(str(BP).replace(",", "."))
                final_data["MODE_C_CORRECTED"] = round(FL * 100 + (bp_val - 1013.2) * 30, 2)
            except ValueError:
                pass
    else:
        final_data["H(m)"] = 0
        final_data["H(ft)"] = 0

    return final_data


# ══════════════════════════════════════════════════════════════════════════════
# Block 6 — Build the final table and apply default filters
# ══════════════════════════════════════════════════════════════════════════════

def _build_final_df(messages_df: pd.DataFrame) -> pd.DataFrame:
    """Select columns based on categories, build tabular output, apply filters."""

    cats_present = set(
        pd.to_numeric(messages_df["cat"], errors="coerce")
        .dropna()
        .astype(int)
        .unique()
    )

    # Determine output columns based on categories found
    if cats_present == {48}:
        target_cols = CSV_CAT048_COLUMNS.copy()
    elif cats_present == {21}:
        target_cols = CSV_CAT021_COLUMNS.copy()
        target_cols.append("GBS")
    else:
        shared = set(CSV_CAT021_COLUMNS).intersection(CSV_CAT048_COLUMNS)
        target_cols = [c for c in CSV_CAT048_COLUMNS if c in shared]

    # Ensure CAT is the first column
    target_cols = [c for c in target_cols if c != "CAT"]
    target_cols = ["CAT"] + target_cols

    # Build rows from decoded dicts
    rows = []
    for r in messages_df.itertuples(index=False):
        data_dict = r.data if isinstance(r.data, dict) else {}
        row_out = {col: data_dict.get(col, None) for col in target_cols[1:]}
        rows.append(row_out)

    final_df = pd.DataFrame(rows, columns=target_cols[1:])

    # CAT column
    cat_series = pd.to_numeric(messages_df["cat"], errors="coerce").astype("Int64")
    final_df.insert(
        0,
        "CAT",
        cat_series.map(lambda x: f"CAT0{x}" if pd.notna(x) else pd.NA),
    )

    # ── Filter 1 · Barcelona TMA bounding box ────────────────────────────
    lat_col = next((c for c in final_df.columns if "LAT" in c.upper()), None)
    lon_col = next((c for c in final_df.columns if "LON" in c.upper()), None)

    if lat_col is not None and lon_col is not None:
        lat = pd.to_numeric(final_df[lat_col], errors="coerce")
        lon = pd.to_numeric(final_df[lon_col], errors="coerce")
        in_bbox = lat.isna() | (
            lat.between(_LAT_MIN, _LAT_MAX) & lon.between(_LON_MIN, _LON_MAX)
        )
        final_df = final_df[in_bbox].reset_index(drop=True)

    # ── Filter 2 · Discard GBS == 1 ──────────────────────────────────────
    if "GBS" in final_df.columns:
        final_df = final_df[~(final_df["GBS"] == 1)].reset_index(drop=True)
        final_df = final_df.drop(columns=["GBS"], errors="ignore")

    return final_df


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def decode_asterix(raw_bytes: bytes) -> pd.DataFrame:
    """
    Full decoding pipeline: binary → DataFrame.

    Parameters
    ----------
    raw_bytes : bytes
        Contents of an ASTERIX `.ast` / `.bin` file.

    Returns
    -------
    pd.DataFrame
        Decoded and filtered records ready for display and CSV export.
    """
    if len(raw_bytes) < 3:
        raise ValueError("File is too short to contain a valid ASTERIX header.")

    # Step 1: split binary into message blocks
    messages_df = _split_messages(raw_bytes)
    print(f"[Decoder] Messages found: {len(messages_df):,}")

    # Step 2: parse FSPEC for each message
    records = messages_df["data_record"].tolist()
    parsed = list(map(_parse_fspec, records))
    messages_df = messages_df.assign(
        frns=[p[0] for p in parsed],
        data_fields=[p[1] for p in parsed],
    )

    # Step 3: ensure UAP decoders are ready (cached after first call)
    frn_map = _ensure_uap_ready()

    # Step 4: decode every message
    messages_df["data"] = [
        _decode_message(r.cat, r.frns, r.data_fields, frn_map)
        for r in messages_df.itertuples(index=False)
    ]

    # Step 5: build final table + apply default filters
    final_df = _build_final_df(messages_df)
    print(f"[Decoder] Final records: {len(final_df):,}")

    return final_df
