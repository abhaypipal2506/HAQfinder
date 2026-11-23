"""Normalize raw scheme records into the canonical schema. Never invents values."""

import datetime
import re

VERIFICATION_STATUSES = (
    "VERIFIED_FROM_OFFICIAL_SOURCE",
    "OFFICIAL_SOURCE_FOUND_DETAILS_REQUIRE_REVIEW",
    "AUTOMATICALLY_RETRIEVED_NOT_FULLY_VERIFIED",
    "SOURCE_UNAVAILABLE",
    "OUTDATED_NEEDS_REVIEW",
)

ALLOWED_CATEGORIES = (
    "education",
    "agriculture",
    "health",
    "housing",
    "pension",
    "finance",
    "employment",
    "women",
    "disability",
    "entrepreneurship",
    "social_security",
    "social_justice",
    "tribal_welfare",
    "food_security",
    "rural_development",
    "msme",
    "other",
)

_CATEGORY_ALIASES = {
    "agri": "agriculture",
    "farmer": "agriculture",
    "farmers": "agriculture",
    "disabled": "disability",
    "pensions": "pension",
    "entrepreneur": "entrepreneurship",
    "health_care": "health",
    "social_welfare": "social_security",
    "women_and_child": "women",
    "tribal": "tribal_welfare",
    "food": "food_security",
    "rural": "rural_development",
    "micro_small_medium_enterprises": "msme",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def slugify(text) -> str:
    """Lowercase, replace runs of non-alphanumerics with '-', and strip '-' from ends."""
    if text is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _parse_date(value):
    """Return value if it is a real YYYY-MM-DD date string, else None."""
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return None
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _as_list(value) -> list:
    return list(value) if isinstance(value, list) else []


def _map_category(raw) -> str:
    if not isinstance(raw, str):
        return "other"
    key = slugify(raw).replace("-", "_")
    key = _CATEGORY_ALIASES.get(key, key)
    return key if key in ALLOWED_CATEGORIES else "other"


def _map_government_level(raw) -> str:
    if isinstance(raw, str) and raw.strip().lower() in ("central", "state"):
        return raw.strip().lower()
    return "unknown"


def normalize_record(raw: dict) -> dict:
    """Return a canonical scheme record built from a raw dict. Raises TypeError for non-dicts."""
    if not isinstance(raw, dict):
        raise TypeError("raw record must be a dict")

    scheme_name = raw.get("scheme_name") or None
    scheme_id = raw.get("scheme_id") or (slugify(scheme_name) or None)

    eligibility = raw.get("eligibility")

    return {
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "scheme_name_local": None,
        "description": raw.get("description") or None,
        "government_level": _map_government_level(raw.get("government_level")),
        "state": raw.get("state"),
        "department": raw.get("department") or None,
        "category": _map_category(raw.get("category")),
        "beneficiaries": _as_list(raw.get("beneficiaries")),
        "eligibility": dict(eligibility) if isinstance(eligibility, dict) else {},
        "eligibility_criteria": _as_list(raw.get("eligibility_criteria")),
        "benefits": _as_list(raw.get("benefits")),
        "required_documents": _as_list(raw.get("required_documents")),
        "application_steps": _as_list(raw.get("application_steps")),
        "deadline": _parse_date(raw.get("deadline")),
        "official_information_url": raw.get("official_information_url") or None,
        "application_url": raw.get("application_url") or None,
        "source_id": raw.get("source_id") or None,
        "source_name": raw.get("source_name") or None,
        "source_url": raw.get("source_url") or None,
        "source_published_date": _parse_date(raw.get("source_published_date")),
        "last_checked_at": None,
        "last_verified_at": None,
        "verification_status": raw.get("verification_status")
        or "AUTOMATICALLY_RETRIEVED_NOT_FULLY_VERIFIED",
        "data_confidence": raw.get("data_confidence") or "low",
        "notes": raw.get("notes") or "",
    }
