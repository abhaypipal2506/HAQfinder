"""SQLite persistence for HAQfinder accounts, profiles, bookmarks, and applications."""

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ALLOWED_STATUSES = ("Not started", "In progress", "Submitted", "Approved", "Rejected")
TERMINAL_STATUSES = ("Submitted", "Approved", "Rejected")
UPDATABLE_FIELDS = ("status", "notes", "deadline", "checklist_json")
REMINDER_WINDOW_DAYS = 14
PASSWORD_ITERATIONS = 260_000

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "haqfinder.db"

SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheme_id TEXT NOT NULL,
        scheme_name TEXT,
        status TEXT NOT NULL,
        notes TEXT,
        deadline TEXT NULL,
        created_at TEXT,
        updated_at TEXT
    )
"""

ACCOUNT_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
        full_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS profiles (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        profile_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bookmarks (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        scheme_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (user_id, scheme_id)
    )
    """,
)


def db_path() -> Path:
    """Resolve the DB path at call time so tests can override HAQFINDER_DB."""
    env = os.environ.get("HAQFINDER_DB")
    return Path(env) if env else _DEFAULT_DB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    path = db_path()
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(SCHEMA_SQL)
    for statement in ACCOUNT_SCHEMA_SQL:
        conn.execute(statement)

    app_columns = {row["name"] for row in conn.execute("PRAGMA table_info(applications)")}
    if "user_id" not in app_columns:
        conn.execute("ALTER TABLE applications ADD COLUMN user_id INTEGER REFERENCES users(id)")
    if "checklist_json" not in app_columns:
        conn.execute(
            "ALTER TABLE applications ADD COLUMN checklist_json TEXT NOT NULL DEFAULT '[]'"
        )
    conn.execute("CREATE INDEX IF NOT EXISTS applications_user_id ON applications(user_id)")
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    if "checklist_json" in result:
        try:
            result["documents"] = json.loads(result.pop("checklist_json") or "[]")
        except (TypeError, json.JSONDecodeError):
            result["documents"] = []
    return result


def _public_user(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    return {key: row[key] for key in ("id", "email", "full_name", "created_at")}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def init_db() -> None:
    conn = _connect()
    conn.close()


def create_user(email: str, full_name: str, password_hash: str) -> dict:
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (email, full_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (email.strip().lower(), full_name.strip(), password_hash, _now()),
            )
            row = conn.execute(
                "SELECT id, email, full_name, created_at FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, email, full_name, password_hash, created_at FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def get_user(user_id: int) -> dict | None:
    conn = _connect()
    try:
        return _public_user(
            conn.execute(
                "SELECT id, email, full_name, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        )
    finally:
        conn.close()


def create_session(user_id: int, token: str, expires_at: datetime) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO auth_sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token_hash, user_id, expires_at.isoformat(timespec="seconds"), _now()),
            )
    finally:
        conn.close()


def get_session_user(token: str) -> dict | None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT users.id, users.email, users.full_name, users.created_at,
                   auth_sessions.expires_at
            FROM auth_sessions JOIN users ON users.id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= _now():
            with conn:
                conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
            return None
        return _public_user(row)
    finally:
        conn.close()


def delete_session(token: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
    finally:
        conn.close()


def get_profile(user_id: int) -> dict:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT profile_json FROM profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        return json.loads(row["profile_json"]) if row else {}
    finally:
        conn.close()


def save_profile(user_id: int, fields: dict) -> dict:
    profile = get_profile(user_id)
    profile.update(fields)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO profiles (user_id, profile_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    profile_json = excluded.profile_json, updated_at = excluded.updated_at
                """,
                (user_id, json.dumps(profile, ensure_ascii=False), _now()),
            )
        return profile
    finally:
        conn.close()


def add_bookmark(user_id: int, scheme_id: str) -> bool:
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO bookmarks (user_id, scheme_id, created_at) VALUES (?, ?, ?)",
                (user_id, scheme_id, _now()),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def remove_bookmark(user_id: int, scheme_id: str) -> bool:
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                "DELETE FROM bookmarks WHERE user_id = ? AND scheme_id = ?",
                (user_id, scheme_id),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def list_bookmarks(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT scheme_id, created_at FROM bookmarks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_application(
    scheme_id: str,
    scheme_name: str | None,
    status: str,
    notes: str | None,
    deadline: str | None,
    user_id: int | None = None,
    required_documents: list[str] | None = None,
) -> dict:
    now = _now()
    checklist = [{"name": name, "checked": False} for name in (required_documents or [])]
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO applications
                    (scheme_id, scheme_name, status, notes, deadline, created_at, updated_at,
                     user_id, checklist_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scheme_id, scheme_name, status, notes, deadline, now, now, user_id,
                    json.dumps(checklist, ensure_ascii=False),
                ),
            )
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_applications(user_id: int | None = None) -> list[dict]:
    conn = _connect()
    try:
        if user_id is None:
            rows = conn.execute(
                "SELECT * FROM applications WHERE user_id IS NULL ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications WHERE user_id = ? ORDER BY id", (user_id,)
            ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_application(app_id: int, user_id: int | None = None) -> dict | None:
    conn = _connect()
    try:
        if user_id is None:
            row = conn.execute(
                "SELECT * FROM applications WHERE id = ? AND user_id IS NULL", (app_id,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM applications WHERE id = ? AND user_id = ?", (app_id, user_id)
            ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_application(app_id: int, user_id: int | None = None, **fields) -> dict | None:
    updates = {key: value for key, value in fields.items() if key in UPDATABLE_FIELDS}
    if "documents" in fields:
        updates["checklist_json"] = json.dumps(fields["documents"], ensure_ascii=False)
    conn = _connect()
    try:
        with conn:
            owner_clause = "user_id IS NULL" if user_id is None else "user_id = ?"
            owner_params = [] if user_id is None else [user_id]
            if updates:
                assignments = ", ".join(f"{key} = ?" for key in updates)
                params = list(updates.values()) + [_now(), app_id] + owner_params
                cur = conn.execute(
                    f"UPDATE applications SET {assignments}, updated_at = ? WHERE id = ? AND {owner_clause}",
                    params,
                )
                if cur.rowcount == 0:
                    return None
            row = conn.execute(
                f"SELECT * FROM applications WHERE id = ? AND {owner_clause}",
                [app_id] + owner_params,
            ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def delete_application(app_id: int, user_id: int | None = None) -> bool:
    conn = _connect()
    try:
        with conn:
            if user_id is None:
                cur = conn.execute(
                    "DELETE FROM applications WHERE id = ? AND user_id IS NULL", (app_id,)
                )
            else:
                cur = conn.execute(
                    "DELETE FROM applications WHERE id = ? AND user_id = ?", (app_id, user_id)
                )
            return cur.rowcount > 0
    finally:
        conn.close()


def reminders(today: date, user_id: int | None = None) -> list[dict]:
    """Open applications with a deadline on or before today + 14 days (overdue included)."""
    cutoff = (today + timedelta(days=REMINDER_WINDOW_DAYS)).isoformat()
    placeholders = ", ".join("?" for _ in TERMINAL_STATUSES)
    conn = _connect()
    try:
        owner_clause = "user_id IS NULL" if user_id is None else "user_id = ?"
        owner_params = [] if user_id is None else [user_id]
        rows = conn.execute(
            f"""
            SELECT * FROM applications
            WHERE {owner_clause}
              AND deadline IS NOT NULL
              AND status NOT IN ({placeholders})
              AND deadline <= ?
            ORDER BY deadline, id
            """,
            (*owner_params, *TERMINAL_STATUSES, cutoff),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()
