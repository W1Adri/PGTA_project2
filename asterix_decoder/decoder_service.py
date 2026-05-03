from __future__ import annotations

import importlib
import inspect
from functools import lru_cache
from typing import Any, Callable

import pandas as pd

from asterix_decoder.data_items.data_item import ItemXXX
from asterix_decoder.data_tables.csv_table import CAT021_COLUMNS, CAT048_COLUMNS, COMBINED_COLUMNS
from asterix_decoder.helpers.compute_target_lat_lon import compute_target_lat_lon
from asterix_decoder.helpers.progress import emit_progress
from asterix_decoder.data_tables.uap_tables import uap021_df, uap048_df
from asterix_decoder.optimization import decode_messages

# Barcelona TMA bounding box (from notebook Block 6)
_LAT_MIN, _LAT_MAX = 40.9, 41.7
_LON_MIN, _LON_MAX = 1.5, 2.6


# ══════════════════════════════════════════════════════════════════════════════
# Block 3 — Parse FSPEC and build the UAP registry
# ══════════════════════════════════════════════════════════════════════════════

_ACTIVE_OFFSETS: tuple[tuple[int, ...], ...] = tuple(
    tuple(i for i in range(7) if (b >> (7 - i)) & 1)
    for b in range(256)
)
_HAS_FX: tuple[bool, ...] = tuple(bool(b & 1) for b in range(256))

_STANDARD_BP_MIN = 1013.0
_STANDARD_BP_MAX = 1013.4
_MODE_C_STANDARD_BP = 1013.2
_TRANSITION_FL = 60.0


def parse_fspec(data_record: bytes) -> tuple[list[int], bytes]:
    """Return the FRNs present in a record and the remaining data fields."""
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


def _load_uap_dataframe() -> pd.DataFrame:
    return pd.concat([uap021_df, uap048_df], ignore_index=True)


def _discover_item_classes(
    uap_df: pd.DataFrame,
) -> dict[tuple[int, str], type]:
    """Map (cat, item_id) -> class loaded dynamically from UAP-defined modules."""
    class_map: dict[tuple[int, str], type] = {}

    expected_items = (
        uap_df[["cat", "item_id"]]
        .dropna()
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )

    for cat_raw, item_id_raw in expected_items:
        cat = int(cat_raw)
        item_id = str(item_id_raw).strip()
        if "/" not in item_id:
            continue

        item_suffix = item_id.split("/", 1)[1]
        package_name = f"asterix_decoder.data_items.CAT{cat:03d}"
        module_candidates = [
            f"{package_name}.item_{item_suffix}",
            f"{package_name}.item_{item_suffix.upper()}",
            f"{package_name}.item_{item_suffix.lower()}",
        ]

        module = None
        for module_name in dict.fromkeys(module_candidates):
            try:
                module = importlib.import_module(module_name)
                break
            except Exception:
                continue

        if module is None:
            continue

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            get_item_id = getattr(cls, "get_item_id", None)
            if not callable(get_item_id):
                continue
            if str(get_item_id()).strip() == item_id:
                class_map[(cat, item_id)] = cls
                break

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


@lru_cache(maxsize=1)
def get_frn_map() -> dict[tuple[int, int], Any]:
    """Build the cached FRN -> decoder instance lookup."""
    uap_df = _load_uap_dataframe()
    class_map = _discover_item_classes(uap_df)
    uap_df = uap_df.copy()
    uap_df["instance"] = uap_df.apply(
        lambda r: _build_instance(r, class_map), axis=1
    )
    return dict(
        zip(
            uap_df[["cat", "frn"]].apply(tuple, axis=1),
            uap_df["instance"],
        )
    )


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


def _parse_decimal_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def _normalize_target_identification(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if not normalized or normalized == "NV":
        return None
    return normalized


def _is_standard_bp(bp_value: float) -> bool:
    return _STANDARD_BP_MIN <= bp_value <= _STANDARD_BP_MAX


def _apply_mode_c_correction(messages_df: pd.DataFrame) -> None:
    """Compute MODE_C_CORRECTED with per-aircraft previous non-standard BP memory."""
    previous_non_standard_bp: dict[str, float] = {}

    for record in messages_df["data"]:
        if not isinstance(record, dict):
            continue

        fl_value = _parse_decimal_value(record.get("FL"))
        bp_value = _parse_decimal_value(record.get("BP"))
        if fl_value is None or bp_value is None or fl_value >= _TRANSITION_FL:
            continue

        target_id = _normalize_target_identification(record.get("TARGET_IDENTIFICATION"))
        effective_bp = bp_value

        if _is_standard_bp(bp_value):
            if target_id is not None:
                previous_bp = previous_non_standard_bp.get(target_id)
                if previous_bp is not None:
                    effective_bp = previous_bp
        elif target_id is not None:
            previous_non_standard_bp[target_id] = bp_value

        record["MODE_C_CORRECTED"] = round(
            fl_value * 100 + (effective_bp - _MODE_C_STANDARD_BP) * 30,
            2,
        )


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

    if FL is None:
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
        target_cols = CAT048_COLUMNS.copy()
    elif cats_present == {21}:
        target_cols = CAT021_COLUMNS.copy()
        target_cols.append("GBS")
    else:
        target_cols = COMBINED_COLUMNS.copy()
        target_cols.append("GBS")


    # Ensure CAT is the first column
    target_cols = [c for c in target_cols if c != "CAT"]
    target_cols = ["CAT"] + target_cols

    # Pandas and AG Grid both expect unique column names. Keep the first
    # occurrence so the schema stays stable even if a source list repeats a name.
    unique_cols: list[str] = []
    seen_cols: set[str] = set()
    for col in target_cols:
        if col in seen_cols:
            continue
        unique_cols.append(col)
        seen_cols.add(col)
    target_cols = unique_cols

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

    # ── Filter 3 · Drop rows with no decoded payload fields ───────────────
    payload_cols = [c for c in final_df.columns if c != "CAT"]
    if payload_cols:
        has_payload = final_df[payload_cols].notna().any(axis=1)
        final_df = final_df[has_payload].reset_index(drop=True)

    return final_df


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def decode_asterix(
    raw_bytes: bytes,
    *,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    workers: int | None = None,
    batch_size: int | None = None,
) -> pd.DataFrame:
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

    emit_progress(
        progress_callback,
        stage="Reading file .ast",
        current=0,
        total=100,
        percent=0.0,
    )

    # Step 1: split binary into message blocks
    messages_df = _split_messages(raw_bytes)
    print(f"[Decoder] Messages found: {len(messages_df):,}")

    emit_progress(
        progress_callback,
        stage="Splitting messages",
        current=len(messages_df),
        total=len(messages_df) or 1,
        percent=10.0,
    )

    # Step 2: parse FSPEC and build decode specs in a single pass
    message_specs: list[tuple[int, int, list[int], bytes]] = []
    for index, row in enumerate(messages_df[["cat", "data_record"]].itertuples(index=False)):
        frns, data_fields = parse_fspec(row.data_record)
        message_specs.append((index, int(row.cat), frns, data_fields))

    emit_progress(
        progress_callback,
        stage="Reading FSPEC",
        current=len(message_specs),
        total=len(message_specs) or 1,
        percent=15.0,
    )

    # Step 3: ensure UAP decoders are ready (cached after first call)
    get_frn_map()

    emit_progress(
        progress_callback,
        stage="Preparing decoders",
        current=len(messages_df),
        total=len(messages_df) or 1,
        percent=20.0,
    )

    # Step 4: decode every message
    decoded_rows = decode_messages(
        message_specs,
        _decode_message,
        get_frn_map,
        progress_callback=progress_callback,
        workers=workers,
        batch_size=batch_size,
    )
    messages_df["data"] = decoded_rows
    _apply_mode_c_correction(messages_df)

    # Step 5: build final table + apply default filters
    final_df = _build_final_df(messages_df)

    if len(messages_df) > 0 and len(final_df) == 0:
        decoded_payload_rows = 0
        for payload in decoded_rows:
            if isinstance(payload, dict) and len(payload) > 0:
                decoded_payload_rows += 1

        if decoded_payload_rows == 0:
            raise RuntimeError(
                "No message payload could be decoded. "
                "This usually means ASTERIX item decoder modules were not loaded "
                "in the packaged build (check PyInstaller hiddenimports)."
            )

    emit_progress(
        progress_callback,
        stage="Finalizing table",
        current=len(final_df),
        total=len(final_df) or 1,
        percent=100.0,
    )
    print(f"[Decoder] Final records: {len(final_df):,}")

    return final_df
