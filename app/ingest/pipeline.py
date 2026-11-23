"""Import orchestration: normalize, validate, report duplicates, then commit all-or-nothing.

run_import never deletes existing live records. A batch is either committed in full
(every record valid) or not written at all (any record invalid).
"""

import datetime

from . import db
from .dedupe import find_duplicates
from .normalize import normalize_record
from .validate import detect_contradictions, validate_scheme

CHANGE_FIELDS = (
    "deadline",
    "application_url",
    "official_information_url",
    "eligibility",
    "benefits",
    "verification_status",
    "scheme_name",
)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _new_report(source_id) -> dict:
    return {
        "source_id": source_id,
        "accepted": 0,
        "rejected": 0,
        "rejected_details": [],
        "duplicates": [],
        "warnings": [],
        "committed": False,
        "error": None,
        "changes": {"added": [], "removed": [], "changed": {}},
    }


def _safe_id(item):
    if isinstance(item, dict) and isinstance(item.get("scheme_id"), str):
        return item["scheme_id"]
    return None


def _index_by_id(records) -> dict:
    return {
        r["scheme_id"]: r
        for r in records
        if isinstance(r, dict) and r.get("scheme_id")
    }


def _record_failure(report: dict, message: str) -> dict:
    """Set the report error and try to log a failed sync. Logging errors are swallowed."""
    report["error"] = message
    try:
        db.write_sync_log(report["source_id"], "failed", 0, 0, message)
    except Exception:
        pass
    return report


def change_summary(old_records: list, new_records: list) -> dict:
    """Compare two record lists by scheme_id. Informational only; nothing is deleted."""
    old_by = _index_by_id(old_records)
    new_by = _index_by_id(new_records)
    added = [sid for sid in new_by if sid not in old_by]
    removed = [sid for sid in old_by if sid not in new_by]
    changed = {}
    for sid, new in new_by.items():
        old = old_by.get(sid)
        if old is None:
            continue
        fields = [f for f in CHANGE_FIELDS if old.get(f) != new.get(f)]
        if fields:
            changed[sid] = fields
    return {"added": added, "removed": removed, "changed": changed}


def run_import(raw_records: list, source_id: str) -> dict:
    """Normalize, validate and commit a batch of raw scheme records. Never raises."""
    report = _new_report(source_id)

    if not isinstance(raw_records, list):
        return _record_failure(report, "input is not a list")

    accepted = []
    rejected = []
    warnings = []

    for index, item in enumerate(raw_records):
        if not isinstance(item, dict):
            rejected.append({"index": index, "scheme_id": None,
                             "errors": ["record is not an object"]})
            continue
        try:
            rec = normalize_record(item)
        except Exception as exc:
            rejected.append({"index": index, "scheme_id": _safe_id(item),
                             "errors": [f"normalize failed: {exc}"]})
            continue

        if rec.get("source_id") is None:
            rec["source_id"] = source_id
        rec["last_checked_at"] = _now()

        for warning in detect_contradictions(rec):
            warnings.append(f"{rec.get('scheme_id')}: {warning}")

        errors = validate_scheme(rec)
        if errors:
            rejected.append({"index": index, "scheme_id": rec.get("scheme_id"),
                             "errors": errors})
        else:
            accepted.append(rec)

    report["rejected"] = len(rejected)
    report["rejected_details"] = rejected
    report["warnings"] = warnings

    batch_ids = {r["scheme_id"] for r in accepted}

    try:
        live = db.list_live_schemes()
        live_by_id = _index_by_id(live)

        duplicates = []
        for rec in accepted:
            prior = live_by_id.get(rec["scheme_id"])
            if prior is not None and prior.get("source_id") != rec.get("source_id"):
                duplicates.append({
                    "a": rec["scheme_id"],
                    "b": rec["scheme_id"],
                    "reason": (f"scheme_id already live from source "
                               f"'{prior.get('source_id')}', batch source "
                               f"'{rec.get('source_id')}'"),
                })
        pool = [r for r in live if r.get("scheme_id") not in batch_ids] + accepted
        for id_a, id_b, reason in find_duplicates(pool):
            if id_a in batch_ids or id_b in batch_ids:
                duplicates.append({"a": id_a, "b": id_b, "reason": reason})
        report["duplicates"] = duplicates

        if rejected:
            message = f"batch rejected: {len(rejected)} invalid records"
            db.write_sync_log(source_id, "failed", 0, len(rejected), message)
            return report

        report["changes"] = change_summary(live, accepted)

        try:
            db.replace_live_schemes_in_transaction(accepted)
        except Exception as exc:
            return _record_failure(report, f"commit failed: {exc}")

        report["committed"] = True
        report["accepted"] = len(accepted)
        db.write_sync_log(source_id, "ok", len(accepted), 0,
                          f"committed {len(accepted)} records")
    except Exception as exc:
        return _record_failure(report, f"database error: {exc}")

    return report
