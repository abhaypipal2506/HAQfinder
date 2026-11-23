"""Duplicate detection. Reports candidate pairs only; never deletes anything."""

import difflib
import re

SIMILARITY_THRESHOLD = 0.9


def _norm_name(s) -> str:
    """Lowercase and strip everything except letters and digits."""
    if s is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _record_id(rec: dict) -> str:
    return str(rec.get("scheme_id") or rec.get("scheme_name") or "")


def find_duplicates(records: list) -> list:
    """Return (id_a, id_b, reason) for each unordered pair that looks duplicated."""
    items = [r for r in records if isinstance(r, dict)]
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a = items[i]
            b = items[j]
            url_a = a.get("source_url")
            if url_a and url_a == b.get("source_url"):
                pairs.append((_record_id(a), _record_id(b), "same source_url"))
                continue
            na = _norm_name(a.get("scheme_name"))
            nb = _norm_name(b.get("scheme_name"))
            if na and nb and difflib.SequenceMatcher(None, na, nb).ratio() >= SIMILARITY_THRESHOLD:
                pairs.append((_record_id(a), _record_id(b), "similar name"))
    return pairs
