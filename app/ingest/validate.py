"""Validation and contradiction checks for normalized scheme records."""

import datetime
import re
from urllib.parse import urlparse

from .normalize import VERIFICATION_STATUSES
from .sources import is_allowed_url

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMERIC_FIELDS = ("age_min", "age_max", "income_max")
_URL_FIELDS = ("official_information_url", "application_url")


def _is_iso_date(value) -> bool:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_https_url(value) -> bool:
    try:
        return urlparse(str(value)).scheme == "https"
    except Exception:
        return False


def validate_scheme(rec: dict) -> list:
    """Return a list of error strings. An empty list means the record is valid."""
    if not isinstance(rec, dict):
        return ["record is not a dict"]

    errors = []

    if not rec.get("scheme_id"):
        errors.append("missing scheme_id")
    if not rec.get("scheme_name"):
        errors.append("missing scheme_name")
    if not rec.get("source_id"):
        errors.append("source_id missing")

    source_url = rec.get("source_url")
    if not source_url:
        errors.append("source_url missing")
    elif not is_allowed_url(source_url):
        errors.append("source_url is not an allowed https official domain")

    if rec.get("verification_status") not in VERIFICATION_STATUSES:
        errors.append("verification_status not in VERIFICATION_STATUSES")

    deadline = rec.get("deadline")
    if deadline is not None and not _is_iso_date(deadline):
        errors.append("deadline is not a YYYY-MM-DD date")

    for field in _NUMERIC_FIELDS:
        if field in rec and rec[field] is not None:
            value = rec[field]
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"{field} is not an integer")
            elif value < 0:
                errors.append(f"{field} is negative")

    for field in _URL_FIELDS:
        if field in rec and rec[field] is not None and not _is_https_url(rec[field]):
            errors.append(f"{field} is not an https URL")

    return errors


def detect_contradictions(rec: dict) -> list:
    """Return a list of warning strings for internally inconsistent records."""
    if not isinstance(rec, dict):
        return []

    warnings = []

    age_min = rec.get("age_min")
    age_max = rec.get("age_max")
    if (isinstance(age_min, int) and not isinstance(age_min, bool)
            and isinstance(age_max, int) and not isinstance(age_max, bool)
            and age_min > age_max):
        warnings.append("age_min is greater than age_max")

    level = rec.get("government_level")
    state = rec.get("state")
    if level == "central" and state is not None:
        warnings.append("central scheme has a non-null state")
    if level == "state" and state is None:
        warnings.append("state scheme has a null state")

    deadline = rec.get("deadline")
    if _is_iso_date(deadline) and datetime.date.fromisoformat(deadline) < datetime.date.today():
        warnings.append("deadline has passed")

    return warnings
