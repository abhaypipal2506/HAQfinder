"""JSON file storage for scheme records: atomic writes, upsert by scheme_id (stdlib only)."""

import json
import os


def load_records(path: str) -> list:
    """Return the stored record list, or [] if the file does not exist."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} does not contain a JSON list")
    return [r for r in data if isinstance(r, dict)]


def save_records(path: str, records: list) -> None:
    """Write records atomically: write to a temp file, then replace the target."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp_path, path)


def upsert_records(existing: list, incoming: list) -> list:
    """Merge incoming records into existing by scheme_id. Incoming wins. Never deletes.

    Records without a scheme_id are appended as-is.
    """
    merged = {}
    order = []
    anonymous = []
    for rec in existing:
        if not isinstance(rec, dict):
            continue
        key = rec.get("scheme_id")
        if key:
            if key not in merged:
                order.append(key)
            merged[key] = rec
        else:
            anonymous.append(rec)
    for rec in incoming:
        if not isinstance(rec, dict):
            continue
        key = rec.get("scheme_id")
        if key:
            if key not in merged:
                order.append(key)
            merged[key] = rec
        else:
            anonymous.append(rec)
    return [merged[k] for k in order] + anonymous
