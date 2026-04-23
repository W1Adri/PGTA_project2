from __future__ import annotations

import math
import multiprocessing as mp
import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from typing import Any, Callable

_WORKER_FRN_MAP: dict[tuple[int, int], Any] | None = None
_WORKER_DECODE_ONE: Callable[[int, list[int], bytes, dict[tuple[int, int], Any]], dict[str, Any]] | None = None
_WORKER_GET_FRN_MAP: Callable[[], dict[tuple[int, int], Any]] | None = None

PARALLEL_MIN_MESSAGES = 256
PARALLEL_BATCH_MIN = 64
PARALLEL_BATCH_MAX = 512


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


def resolve_worker_count(
    total_messages: int,
    workers: int | None = None,
) -> int:
    """Pick a worker count that matches the current machine and workload."""
    if total_messages < PARALLEL_MIN_MESSAGES:
        return 1

    if workers is not None:
        return max(1, min(int(workers), total_messages))

    visible_cpus = _available_cpu_count()

    # Use around half the visible CPUs to keep headroom for the app/UI.
    cpu_budget = max(2, visible_cpus // 2)

    # Scale workers for smaller jobs to avoid paying startup/IPC overhead.
    workload_budget = max(2, math.ceil(total_messages / 40_000))

    return max(1, min(total_messages, cpu_budget, workload_budget))


def resolve_batch_size(
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
        PARALLEL_BATCH_MIN,
        min(PARALLEL_BATCH_MAX, auto_batch_size),
    )


def resolve_parallel_config(
    total_messages: int,
    workers: int | None = None,
    batch_size: int | None = None,
) -> tuple[int, int]:
    worker_count = resolve_worker_count(total_messages, workers)
    resolved_batch_size = resolve_batch_size(total_messages, worker_count, batch_size)
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


def _worker_bootstrap(
    decode_one: Callable[[int, list[int], bytes, dict[tuple[int, int], Any]], dict[str, Any]],
    get_frn_map: Callable[[], dict[tuple[int, int], Any]],
) -> None:
    global _WORKER_DECODE_ONE, _WORKER_GET_FRN_MAP, _WORKER_FRN_MAP
    _WORKER_DECODE_ONE = decode_one
    _WORKER_GET_FRN_MAP = get_frn_map
    _WORKER_FRN_MAP = _WORKER_GET_FRN_MAP()


def _decode_message_batch(
    batch: list[tuple[int, int, list[int], bytes]],
) -> list[tuple[int, dict[str, Any]]]:
    if _WORKER_DECODE_ONE is None or _WORKER_GET_FRN_MAP is None:
        raise RuntimeError("Worker has not been initialized.")

    global _WORKER_FRN_MAP
    if _WORKER_FRN_MAP is None:
        _WORKER_FRN_MAP = _WORKER_GET_FRN_MAP()

    decoded: list[tuple[int, dict[str, Any]]] = []
    for index, cat, frns, data_fields in batch:
        decoded.append((index, _WORKER_DECODE_ONE(cat, frns, data_fields, _WORKER_FRN_MAP)))

    return decoded


def decode_messages_sequential(
    message_specs: list[tuple[int, int, list[int], bytes]],
    decode_one: Callable[[int, list[int], bytes, dict[tuple[int, int], Any]], dict[str, Any]],
    get_frn_map: Callable[[], dict[tuple[int, int], Any]],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    total = len(message_specs)
    frn_map = get_frn_map()
    decoded: list[dict[str, Any]] = []

    for index, (_, cat, frns, data_fields) in enumerate(message_specs, start=1):
        decoded.append(decode_one(cat, frns, data_fields, frn_map))
        _emit_progress(
            progress_callback,
            stage="Decodificando mensajes",
            current=index,
            total=total,
            percent=20.0 + (60.0 * index / total) if total else 80.0,
        )

    return decoded


def decode_messages(
    message_specs: list[tuple[int, int, list[int], bytes]],
    decode_one: Callable[[int, list[int], bytes, dict[tuple[int, int], Any]], dict[str, Any]],
    get_frn_map: Callable[[], dict[tuple[int, int], Any]],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    workers: int | None = None,
    batch_size: int | None = None,
) -> list[dict[str, Any]]:
    total = len(message_specs)
    worker_count, resolved_batch_size = resolve_parallel_config(
        total,
        workers=workers,
        batch_size=batch_size,
    )

    if worker_count < 2 or total < PARALLEL_MIN_MESSAGES:
        return decode_messages_sequential(
            message_specs,
            decode_one,
            get_frn_map,
            progress_callback,
        )

    estimated_batches = math.ceil(total / resolved_batch_size)
    decoded: list[dict[str, Any] | None] = [None] * total
    completed = 0

    print(
        f"[Decoder] Parallel decode: {total:,} messages, "
        f"{worker_count} workers, {estimated_batches} batches "
        f"(batch_size={resolved_batch_size})"
    )

    try:
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=ctx,
            initializer=_worker_bootstrap,
            initargs=(decode_one, get_frn_map),
        ) as executor:
            pending: dict[Any, int] = {}
            chunk_iter = iter(_chunk_message_specs(message_specs, resolved_batch_size))
            max_pending = max(1, worker_count * 2)

            def submit_next() -> bool:
                try:
                    batch = next(chunk_iter)
                except StopIteration:
                    return False
                future = executor.submit(_decode_message_batch, batch)
                pending[future] = len(batch)
                return True

            for _ in range(max_pending):
                if not submit_next():
                    break

            while pending:
                done, _ = wait(set(pending.keys()), return_when=FIRST_COMPLETED)
                for future in done:
                    batch_count = pending.pop(future)
                    batch_results = future.result()
                    for index, data in batch_results:
                        decoded[index] = data

                    completed += batch_count
                    _emit_progress(
                        progress_callback,
                        stage="Decodificando mensajes",
                        current=completed,
                        total=total,
                        percent=20.0 + (79.0 * completed / total) if total else 99.0,
                    )
                    submit_next()

    except Exception as exc:
        if completed == 0:
            print(f"[Decoder] Parallel decode fallback: {exc}")
            return decode_messages_sequential(
                message_specs,
                decode_one,
                get_frn_map,
                progress_callback,
            )
        raise

    if any(item is None for item in decoded):
        raise RuntimeError("Parallel decode finished with missing rows.")

    return [item for item in decoded if item is not None]
