import sqlite3
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import engine
from app.main import app


def _client(tmp_path, monkeypatch):
    database = tmp_path / "haqfinder.db"
    monkeypatch.setenv("HAQFINDER_DB", str(database))
    return TestClient(app), database


def _register(client, email="citizen@example.in"):
    return client.post(
        "/api/auth/register",
        json={"full_name": "Asha Citizen", "email": email, "password": "secure-passphrase"},
    )


def test_registration_hashes_password_and_login_logout(tmp_path, monkeypatch):
    client, database = _client(tmp_path, monkeypatch)
    registered = _register(client)
    assert registered.status_code == 201
    assert registered.json()["user"]["email"] == "citizen@example.in"
    assert registered.headers["set-cookie"].lower().find("httponly") >= 0

    connection = sqlite3.connect(database)
    stored_hash = connection.execute("SELECT password_hash FROM users").fetchone()[0]
    connection.close()
    assert stored_hash != "secure-passphrase"
    assert stored_hash.startswith("pbkdf2_sha256$")

    assert client.get("/api/auth/me").json()["user"]["email"] == "citizen@example.in"
    assert client.post(
        "/api/auth/login",
        json={"email": "citizen@example.in", "password": "wrong-password"},
    ).status_code == 401
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json()["user"] is None

    logged_in = client.post(
        "/api/auth/login",
        json={"email": "citizen@example.in", "password": "secure-passphrase"},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["full_name"] == "Asha Citizen"


def test_registration_rejects_duplicate_and_weak_password(tmp_path, monkeypatch):
    client, _database = _client(tmp_path, monkeypatch)
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409
    weak = client.post(
        "/api/auth/register",
        json={"full_name": "Asha Citizen", "email": "other@example.in", "password": "short"},
    )
    assert weak.status_code == 422


def test_profile_bookmarks_and_application_tracker_persist_per_account(tmp_path, monkeypatch):
    client, _database = _client(tmp_path, monkeypatch)
    assert client.get("/api/bookmarks").status_code == 401
    assert _register(client).status_code == 201

    profile = {
        "state": "Punjab",
        "age": 45,
        "occupation": "farmer",
        "annual_income": 150000,
        "special_answers": {"owns_agricultural_land": True},
    }
    assert client.put("/api/profile", json=profile).json()["profile"]["state"] == "Punjab"
    matches = client.post(
        "/api/match",
        json={"description": "I want to find support for my family"},
    ).json()
    pm_kisan = next(row for row in matches["results"] if row["scheme_id"] == "pm-kisan")
    assert pm_kisan["status"] == "likely_eligible"

    saved = client.put("/api/bookmarks/pm-kisan")
    assert saved.status_code == 201
    assert client.get("/api/bookmarks").json()[0]["scheme_id"] == "pm-kisan"

    created = client.post("/api/applications", json={"scheme_id": "pm-kisan"})
    assert created.status_code == 201
    application = created.json()
    assert application["user_id"] is not None
    assert application["documents"]
    application["documents"][0]["checked"] = True
    patched = client.patch(
        f"/api/applications/{application['id']}",
        json={"documents": application["documents"]},
    )
    assert patched.json()["documents"][0]["checked"] is True
    assert len(client.get("/api/applications").json()) == 1

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/bookmarks").status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": "citizen@example.in", "password": "secure-passphrase"},
    ).status_code == 200
    assert client.get("/api/profile").json()["profile"]["state"] == "Punjab"
    assert client.get("/api/auth/me").json()["profile"]["state"] == "Punjab"
    assert client.get("/api/bookmarks").json()[0]["scheme_id"] == "pm-kisan"
    assert client.get("/api/applications").json()[0]["documents"][0]["checked"] is True


def test_account_cannot_read_or_change_another_accounts_application(tmp_path, monkeypatch):
    client, _database = _client(tmp_path, monkeypatch)
    assert _register(client).status_code == 201
    created = client.post("/api/applications", json={"scheme_id": "pm-kisan"}).json()
    app_id = created["id"]
    client.post("/api/auth/logout")

    assert _register(client, "other@example.in").status_code == 201
    assert client.get("/api/applications").json() == []
    assert client.patch(f"/api/applications/{app_id}", json={"status": "Approved"}).status_code == 404
    assert client.delete(f"/api/applications/{app_id}").status_code == 404


def test_saved_scheme_deadlines_appear_in_personal_reminders(tmp_path, monkeypatch):
    client, _database = _client(tmp_path, monkeypatch)
    scheme = next(item for item in engine.SCHEMES if item["id"] == "pm-kisan")
    monkeypatch.setitem(scheme, "deadline", (date.today() + timedelta(days=5)).isoformat())
    assert _register(client).status_code == 201
    assert client.put("/api/bookmarks/pm-kisan").status_code == 201

    reminders = client.get("/api/reminders").json()
    assert any(
        row["scheme_id"] == "pm-kisan" and row["status"] == "Saved scheme"
        for row in reminders
    )
