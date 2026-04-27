from __future__ import annotations

from typing import Any, Callable


def emit_progress(
    progress_callback: Callable[[dict[str, Any]], None] | None,
    *,
    stage: str,
    current: int,
    total: int,
    percent: float,
) -> None:
    """Send a normalized progress payload to the UI, if a callback exists."""
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
