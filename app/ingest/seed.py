"""Load the existing hand-entered seed dataset through the normal import pipeline.

data/schemes.json is read only. Seed records are marked low confidence and are never
presented as verified; their criteria were not re-checked against official pages.
"""

import json

from .normalize import normalize_record
from .pipeline import _record_failure, _new_report, run_import

SEED_SOURCE_ID = "seed_existing_dataset"
SEED_SOURCE_NAME = "Existing HAQfinder seed dataset (hand-entered)"
SEED_NOTE = ("Hand-entered seed record. Criteria not re-checked against the official page; "
             "verify before relying on it.")
SEED_DEFAULT_STATUS = "AUTOMATICALLY_RETRIEVED_NOT_FULLY_VERIFIED"


def load_seed_records(path: str = "data/schemes.json") -> list[dict]:
    """Read the seed file and return normalized seed records.

    Non-object entries are passed through unchanged so the pipeline can reject them.
    Raises OSError or ValueError if the file is unreadable or not in the expected shape.
    """
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("schemes"), list):
        raise ValueError('seed file must be a JSON object with a "schemes" array')

    records = []
    for raw in data["schemes"]:
        if not isinstance(raw, dict):
            records.append(raw)
            continue
        rec = normalize_record(raw)
        rec["source_id"] = SEED_SOURCE_ID
        rec["source_name"] = SEED_SOURCE_NAME
        if not raw.get("verification_status"):
            rec["verification_status"] = SEED_DEFAULT_STATUS
        rec["data_confidence"] = "low"
        existing_notes = raw.get("notes")
        rec["notes"] = (f"{SEED_NOTE} {existing_notes}" if existing_notes else SEED_NOTE)
        records.append(rec)
    return records


def seed_database(path: str = "data/schemes.json") -> dict:
    """Load the seed file and run it through run_import. Returns the import report."""
    try:
        records = load_seed_records(path)
    except (OSError, ValueError) as exc:
        return _record_failure(_new_report(SEED_SOURCE_ID), f"could not load seed file: {exc}")
    return run_import(records, SEED_SOURCE_ID)
