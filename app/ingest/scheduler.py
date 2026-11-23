"""Scheduling logic: decides which sources are due for a re-check. No network or clock reads at import."""

import time

DEFAULT_INTERVAL_SECONDS = 24 * 3600


def due_sources(source_ids, last_run: dict, now: float = None,
                interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> list:
    """Return source ids never run or whose last run is at least interval_seconds old."""
    current = time.time() if now is None else now
    due = []
    for source_id in source_ids:
        last = last_run.get(source_id)
        if last is None or current - last >= interval_seconds:
            due.append(source_id)
    return due


def record_run(last_run: dict, source_id: str, now: float = None) -> dict:
    """Return a new last_run mapping with source_id stamped at now. Does not mutate input."""
    current = time.time() if now is None else now
    updated = dict(last_run)
    updated[source_id] = current
    return updated
