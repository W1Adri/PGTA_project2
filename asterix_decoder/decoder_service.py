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
import math
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

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
_WORKER_FRN_MAP: dict[tuple[int, int], Any] | None = None

_PARALLEL_MIN_MESSAGES = 256
_PARALLEL_BATCH_MIN = 64
_PARALLEL_BATCH_MAX = 512

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


def _available_cpu_count() -> int:
    """Return the CPU budget visible to this process."""
    try:
        affinity = len(os.sched_getaffinity(0))
        if affinity > 0:
            return affinity
    except AttributeError:
        pass
    except NotImplementedError:
        pass

    return os.cpu_count() or 1


def _resolve_worker_count(
    total_messages: int,
    workers: int | None = None,
) -> int:
    """Pick a worker count that matches the current machine and workload."""
    if total_messages < _PARALLEL_MIN_MESSAGES:
        return 1

    if workers is not None:
        return max(1, min(int(workers), total_messages))

    visible_cpus = _available_cpu_count()

    # On this machine the best throughput came from using roughly half of the
    # visible CPUs for the CPU-bound decode, while leaving some headroom for
    # the GUI and the interpreter overhead.
    cpu_budget = max(2, visible_cpus // 2)

    # Small uploads do not benefit from the full pool because worker start-up
    # and IPC dominate; scale the pool with the size of the job.
    workload_budget = max(2, math.ceil(total_messages / 40_000))

    return max(1, min(total_messages, cpu_budget, workload_budget))


def _resolve_batch_size(
    total_messages: int,
    worker_count: int,
    batch_size: int | None = None,
) -> int:
    """Pick a batch size that balances process overhead and load balance."""
    if total_messages <= 0:
        return 1

    if batch_size is not None:
        return max(1, min(int(batch_size), total_messages))

    target_batches_per_worker = 6
    auto_batch_size = math.ceil(total_messages / max(1, worker_count * target_batches_per_worker))
    return max(
        _PARALLEL_BATCH_MIN,
        min(_PARALLEL_BATCH_MAX, auto_batch_size),
    )


def _resolve_parallel_config(
    total_messages: int,
    workers: int | None = None,
    batch_size: int | None = None,
) -> tuple[int, int]:
    worker_count = _resolve_worker_count(total_messages, workers)
    resolved_batch_size = _resolve_batch_size(total_messages, worker_count, batch_size)
    return worker_count, resolved_batch_size


def _emit_progress(
    progress_callback: Callable[[dict[str, Any]], None] | None,
    *,
    stage: str,
    current: int,
    total: int,
    percent: float,
) -> None:
    if progress_callback is None:
        return

    payload = {
        "stage": stage,
        "current": int(current),
        "total": int(total),
        "percent": round(max(0.0, min(100.0, float(percent))), 1),
    }

    try:
        progress_callback(payload)
    except Exception:
        pass


def _chunk_message_specs(
    message_specs: list[tuple[int, int, list[int], bytes]],
    chunk_size: int,
):
    for start in range(0, len(message_specs), chunk_size):
        yield message_specs[start:start + chunk_size]


def _worker_bootstrap() -> None:
    global _WORKER_FRN_MAP
    _WORKER_FRN_MAP = _ensure_uap_ready()


def _decode_message_batch(
    batch: list[tuple[int, int, list[int], bytes]],
) -> list[tuple[int, dict[str, Any]]]:
    if _WORKER_FRN_MAP is None:
        _worker_bootstrap()

    assert _WORKER_FRN_MAP is not None
    decoded: list[tuple[int, dict[str, Any]]] = []

    for index, cat, frns, data_fields in batch:
        decoded.append((index, _decode_message(cat, frns, data_fields, _WORKER_FRN_MAP)))

    return decoded


def _decode_messages_sequential(
    message_specs: list[tuple[int, int, list[int], bytes]],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    total = len(message_specs)
    frn_map = _ensure_uap_ready()
    decoded: list[dict[str, Any]] = []

    for index, (_, cat, frns, data_fields) in enumerate(message_specs, start=1):
        decoded.append(_decode_message(cat, frns, data_fields, frn_map))
        _emit_progress(
            progress_callback,
            stage="Decodificando mensajes",
            current=index,
            total=total,
            percent=25.0 + (70.0 * index / total) if total else 95.0,
        )

    return decoded


def _decode_messages_parallel(
    message_specs: list[tuple[int, int, list[int], bytes]],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    workers: int | None = None,
    batch_size: int | None = None,
) -> list[dict[str, Any]]:
    total = len(message_specs)
    worker_count, resolved_batch_size = _resolve_parallel_config(
        total,
        workers=workers,
        batch_size=batch_size,
    )

    if worker_count < 2 or total < _PARALLEL_MIN_MESSAGES:
        return _decode_messages_sequential(message_specs, progress_callback)

    batches = list(_chunk_message_specs(message_specs, resolved_batch_size))
    decoded: list[dict[str, Any] | None] = [None] * total
    completed = 0

    print(
        f"[Decoder] Parallel decode: {total:,} messages, "
        f"{worker_count} workers, {len(batches)} batches "
        f"(batch_size={resolved_batch_size})"
    )

    try:
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=ctx,
            initializer=_worker_bootstrap,
        ) as executor:
            future_map = {
                executor.submit(_decode_message_batch, batch): len(batch)
                for batch in batches
            }

            for future in as_completed(future_map):
                batch_results = future.result()
                for index, data in batch_results:
                    decoded[index] = data

                completed += future_map[future]
                _emit_progress(
                    progress_callback,
                    stage="Decodificando mensajes",
                    current=completed,
                    total=total,
                    percent=25.0 + (70.0 * completed / total) if total else 95.0,
                )

    except Exception as exc:
        if completed == 0:
            print(f"[Decoder] Parallel decode fallback: {exc}")
            return _decode_messages_sequential(message_specs, progress_callback)
        raise

    if any(item is None for item in decoded):
        raise RuntimeError("Parallel decode finished with missing rows.")

    return [item for item in decoded if item is not None]


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

    _emit_progress(
        progress_callback,
        stage="Leyendo archivo ASTERIX",
        current=0,
        total=100,
        percent=0.0,
    )

    # Step 1: split binary into message blocks
    messages_df = _split_messages(raw_bytes)
    print(f"[Decoder] Messages found: {len(messages_df):,}")

    _emit_progress(
        progress_callback,
        stage="Separando mensajes",
        current=len(messages_df),
        total=len(messages_df) or 1,
        percent=10.0,
    )

    # Step 2: parse FSPEC for each message
    records = messages_df["data_record"].tolist()
    parsed = list(map(_parse_fspec, records))
    messages_df = messages_df.assign(
        frns=[p[0] for p in parsed],
        data_fields=[p[1] for p in parsed],
    )

    _emit_progress(
        progress_callback,
        stage="Leyendo FSPEC",
        current=len(messages_df),
        total=len(messages_df) or 1,
        percent=20.0,
    )

    # Step 3: ensure UAP decoders are ready (cached after first call)
    _ensure_uap_ready()

    _emit_progress(
        progress_callback,
        stage="Preparando decodificadores",
        current=len(messages_df),
        total=len(messages_df) or 1,
        percent=25.0,
    )

    message_specs: list[tuple[int, int, list[int], bytes]] = [
        (index, int(row.cat), row.frns, row.data_fields)
        for index, row in enumerate(messages_df.itertuples(index=False))
    ]

    # Step 4: decode every message
    decoded_rows = _decode_messages_parallel(
        message_specs,
        progress_callback=progress_callback,
        workers=workers,
        batch_size=batch_size,
    )
    messages_df["data"] = decoded_rows

    # Step 5: build final table + apply default filters
    final_df = _build_final_df(messages_df)
    _emit_progress(
        progress_callback,
        stage="Finalizando tabla",
        current=len(final_df),
        total=len(final_df) or 1,
        percent=100.0,
    )
    print(f"[Decoder] Final records: {len(final_df):,}")

    return final_df
