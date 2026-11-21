"""API tests for app.main using FastAPI's TestClient.

Temp DB: HAQFINDER_DB is set to a temporary file BEFORE app.main is imported, so the
store opens a throwaway database instead of the real one. This assumes the store reads
HAQFINDER_DB when it is imported (not per request). pytest's tmp_path is not usable at
module level, so tempfile.mkdtemp() is used instead.

Assumed endpoint shapes (app/ was not present when this file was written; verify):
  POST   /api/applications            body {"scheme_id", "status"} -> 201 with "id"
  PATCH  /api/applications/{id}       body {"status"}
  GET    /api/applications/{id}/reminders
  DELETE /api/applications/{id}       -> 204
"""

import os
import tempfile

os.environ["HAQFINDER_DB"] = os.path.join(tempfile.mkdtemp(prefix="haqfinder_test_"), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200


def test_match_returns_profile_results_questions():
    r = client.post(
        "/api/match",
        json={"description": "Main Bihar se hoon, SC category mein hoon, 12th ke baad college mein padhta hoon"},
    )
    assert r.status_code == 200
    body = r.json()
    assert {"profile", "results", "questions"} <= set(body.keys())


def test_unknown_scheme_returns_404():
    r = client.get("/api/schemes/does-not-exist")
    assert r.status_code == 404


def test_application_with_unknown_scheme_returns_404():
    r = client.post("/api/applications", json={"scheme_id": "does-not-exist", "status": "saved"})
    assert r.status_code == 404


def test_application_with_invalid_status_returns_422():
    r = client.post("/api/applications", json={"scheme_id": "pm-kisan", "status": "not-a-real-status"})
    assert r.status_code == 422


def test_application_lifecycle_create_patch_reminders_delete():
    created = client.post("/api/applications", json={"scheme_id": "pm-kisan", "status": "In progress"})
    assert created.status_code in (200, 201)
    app_id = created.json()["id"]

    patched = client.patch(f"/api/applications/{app_id}", json={"status": "Submitted"})
    assert patched.status_code == 200

    reminders = client.get("/api/reminders")
    assert reminders.status_code == 200

    deleted = client.delete(f"/api/applications/{app_id}")
    assert deleted.status_code == 204
