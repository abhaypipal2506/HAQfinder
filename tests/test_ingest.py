"""Tests for the ingestion pipeline. No network access: link checks use injected fetchers,
and fetch_url is tested only on the path that refuses before any request is made."""

import json

import pytest

from app.ingest import db
from app.ingest import fetch as fetch_module
from app.ingest.dedupe import find_duplicates
from app.ingest.fetch import FetchResult, clear_cache, fetch_url
from app.ingest.normalize import normalize_record
from app.ingest.pipeline import change_summary, run_import
from app.ingest.seed import load_seed_records
from app.ingest.sources import is_allowed_url
from app.ingest.validate import validate_scheme
from app.ingest.validate_link import check_link

PENDING = "AUTOMATICALLY_RETRIEVED_NOT_FULLY_VERIFIED"


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("HAQFINDER_DB", str(path))
    db.init_ingest_tables()
    return path


def make_raw(scheme_id="a", **overrides):
    raw = {
        "scheme_id": scheme_id,
        "scheme_name": f"Scheme {scheme_id}",
        "source_url": f"https://nsp.gov.in/scheme/{scheme_id}",
        "verification_status": PENDING,
        "deadline": "2030-01-01",
    }
    raw.update(overrides)
    return raw


def valid_rec():
    rec = normalize_record(make_raw("a"))
    rec["source_id"] = "nsp"
    return rec


def fake_fetcher(status=None, error=None):
    def _fetch(url, timeout=15):
        return FetchResult(url=url, final_url=url if status else None,
                           status=status, body=None, error=error)
    return _fetch


def refusing_fetcher(url, timeout=15):
    raise AssertionError("fetcher must not be called")


# --- allow-list and fetch -------------------------------------------------

def test_is_allowed_url_accepts_subdomains():
    assert is_allowed_url("https://www.myscheme.gov.in/search")
    assert is_allowed_url("https://api.nsp.gov.in/x")


def test_is_allowed_url_rejects_http_and_other_domains():
    assert not is_allowed_url("http://nsp.gov.in/x")
    assert not is_allowed_url("https://example.com/x")
    assert not is_allowed_url("https://nsp.gov.in.evil.com/x")


def test_official_domains_and_expanded_scheme_categories_are_supported():
    assert is_allowed_url("https://pmmvy.wcd.gov.in/")
    assert is_allowed_url("https://mksy.up.gov.in/women_welfare/")
    assert is_allowed_url("https://pmvishwakarma.gov.in/")
    assert is_allowed_url("https://nha.gov.in/PM-JAY")
    assert is_allowed_url("https://pmayg.dord.gov.in/")
    assert normalize_record(make_raw("new", category="rural_development"))["category"] == "rural_development"
    assert normalize_record(make_raw("new", category="social_justice"))["category"] == "social_justice"


def test_fetch_url_refuses_disallowed_domain_without_network(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network used")
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", no_network)
    clear_cache()
    result = fetch_url("https://example.com/x")
    assert result.status is None
    assert result.error == "domain not allowed"


# --- validation -----------------------------------------------------------

def test_validate_scheme_accepts_valid_record():
    assert validate_scheme(valid_rec()) == []


def test_validate_scheme_flags_missing_source_url():
    rec = valid_rec()
    rec["source_url"] = None
    assert "source_url missing" in validate_scheme(rec)


def test_validate_scheme_flags_non_https_source_url():
    rec = valid_rec()
    rec["source_url"] = "http://nsp.gov.in/scheme/a"
    assert "source_url is not an allowed https official domain" in validate_scheme(rec)


def test_validate_scheme_flags_bad_deadline_format():
    rec = valid_rec()
    rec["deadline"] = "31/12/2030"
    assert "deadline is not a YYYY-MM-DD date" in validate_scheme(rec)


def test_validate_scheme_flags_invalid_verification_status():
    rec = valid_rec()
    rec["verification_status"] = "VERIFIED"
    assert "verification_status not in VERIFICATION_STATUSES" in validate_scheme(rec)


def test_normalize_leaves_unknown_fields_null_and_invents_no_deadline():
    rec = normalize_record({"scheme_name": "Sample Scheme"})
    assert rec["scheme_id"] == "sample-scheme"
    assert rec["deadline"] is None
    assert rec["state"] is None
    assert rec["source_url"] is None
    assert rec["official_information_url"] is None
    assert rec["source_published_date"] is None


# --- duplicates -----------------------------------------------------------

def test_find_duplicates_flags_identical_source_url():
    url = "https://nsp.gov.in/scheme/x"
    pairs = find_duplicates([
        {"scheme_id": "a", "scheme_name": "Alpha Scheme", "source_url": url},
        {"scheme_id": "b", "scheme_name": "Totally Different", "source_url": url},
    ])
    assert pairs == [("a", "b", "same source_url")]


def test_find_duplicates_flags_similar_names():
    pairs = find_duplicates([
        {"scheme_id": "a", "scheme_name": "PM Kisan Yojana", "source_url": "https://pmkisan.gov.in/a"},
        {"scheme_id": "b", "scheme_name": "PM-Kisan Yojana", "source_url": "https://pmkisan.gov.in/b"},
    ])
    assert len(pairs) == 1
    assert pairs[0][2] == "similar name"


# --- pipeline and storage -------------------------------------------------

def test_invalid_record_commits_nothing_and_logs_failed(db_path):
    report = run_import(
        [make_raw("a"), make_raw("b", source_url="http://nsp.gov.in/b")],
        "nsp",
    )
    assert report["rejected"] == 1
    assert report["committed"] is False
    assert db.list_live_schemes() == []
    assert db.recent_sync_log(1)[0]["status"] == "failed"


def test_non_list_input_returns_error_and_does_not_raise(db_path):
    report = run_import({"schemes": []}, "nsp")
    assert report["error"] == "input is not a list"
    assert report["accepted"] == 0
    assert report["committed"] is False


def test_empty_list_is_accepted_with_no_error(db_path):
    report = run_import([], "nsp")
    assert report["accepted"] == 0
    assert report["error"] is None


def test_valid_batch_commits_and_logs_ok(db_path):
    report = run_import([make_raw("a")], "nsp")
    assert report["committed"] is True
    assert report["accepted"] == 1
    assert report["error"] is None
    assert [r["scheme_id"] for r in db.list_live_schemes()] == ["a"]
    assert db.recent_sync_log(1)[0]["status"] == "ok"


def test_changed_deadline_is_reflected_and_summarised(db_path):
    run_import([make_raw("a", deadline="2030-01-01")], "nsp")
    old = db.list_live_schemes()
    report = run_import([make_raw("a", deadline="2031-06-30")], "nsp")
    assert report["committed"] is True
    assert "deadline" in report["changes"]["changed"]["a"]
    assert db.get_live_scheme("a")["deadline"] == "2031-06-30"

    summary = change_summary(old, [normalize_record(make_raw("a", deadline="2031-06-30"))])
    assert summary["changed"]["a"] == ["deadline"]
    assert summary["added"] == []
    assert summary["removed"] == []


def test_run_import_never_deletes_existing_records(db_path):
    run_import([make_raw("a")], "nsp")
    run_import([make_raw("b")], "pmkisan")
    assert [r["scheme_id"] for r in db.list_live_schemes()] == ["a", "b"]


def test_seed_loader_marks_records_low_confidence(tmp_path):
    seed_file = tmp_path / "schemes.json"
    seed_file.write_text(json.dumps({"schemes": [make_raw("a")]}), encoding="utf-8")
    records = load_seed_records(str(seed_file))
    assert len(records) == 1
    assert records[0]["source_id"] == "seed_existing_dataset"
    assert records[0]["data_confidence"] == "low"
    assert records[0]["verification_status"] == PENDING
    assert "Hand-entered seed record" in records[0]["notes"]


# --- link verification ----------------------------------------------------

def test_check_link_timeout_is_unable_to_verify():
    verdict = check_link("https://nsp.gov.in/a", fetcher=fake_fetcher(error="timed out"))
    assert verdict["verdict"] == "UNABLE_TO_VERIFY"


def test_check_link_not_allowed_domain_never_calls_fetcher():
    verdict = check_link("https://example.com/a", fetcher=refusing_fetcher)
    assert verdict["verdict"] == "NOT_ALLOWED_DOMAIN"
    assert verdict["detail"] == "host is not on the allowed official-source list"


def test_check_link_404_is_broken():
    verdict = check_link("https://nsp.gov.in/a", fetcher=fake_fetcher(status=404, error="Not Found"))
    assert verdict["verdict"] == "BROKEN"


def test_check_link_403_is_unable_to_verify():
    verdict = check_link("https://nsp.gov.in/a", fetcher=fake_fetcher(status=403, error="Forbidden"))
    assert verdict["verdict"] == "UNABLE_TO_VERIFY"


# --- sync log -------------------------------------------------------------

def test_last_successful_sync_none_before_then_timestamp_after_ok(db_path):
    assert db.last_successful_sync("nsp") is None
    db.write_sync_log("nsp", "ok", 1, 0, "committed 1 records")
    assert db.last_successful_sync("nsp") is not None


def test_failed_sync_does_not_change_last_successful_sync(db_path):
    db.write_sync_log("nsp", "ok", 1, 0, "committed 1 records")
    before = db.last_successful_sync("nsp")
    db.write_sync_log("nsp", "failed", 0, 1, "batch rejected")
    assert before is not None
    assert db.last_successful_sync("nsp") == before
