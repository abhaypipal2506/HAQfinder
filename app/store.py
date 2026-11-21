"""SQLite persistence for HAQfinder applications (stdlib sqlite3 only)."""

import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ALLOWED_STATUSES = ("Not started", "In progress", "Submitted", "Approved", "Rejected")
TERMINAL_STATUSES = ("Submitted", "Approved", "Rejected")
UPDATABLE_FIELDS = ("status", "notes", "deadline")
REMINDER_WINDOW_DAYS = 14

_DEFAULT_DB = Path("data") / "haqfinder.db"

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
    conn.execute(SCHEMA_SQL)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def init_db() -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(SCHEMA_SQL)
    finally:
        conn.close()


def create_application(
    scheme_id: str,
    scheme_name: str | None,
    status: str,
    notes: str | None,
    deadline: str | None,
) -> dict:
    now = _now()
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO applications
                    (scheme_id, scheme_name, status, notes, deadline, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (scheme_id, scheme_name, status, notes, deadline, now, now),
            )
            new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (new_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_applications() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM applications ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_application(app_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_application(app_id: int, **fields) -> dict | None:
    updates = {k: v for k, v in fields.items() if k in UPDATABLE_FIELDS}
    conn = _connect()
    try:
        with conn:
            if updates:
                assignments = ", ".join(f"{k} = ?" for k in updates)
                params = list(updates.values()) + [_now(), app_id]
                cur = conn.execute(
                    f"UPDATE applications SET {assignments}, updated_at = ? WHERE id = ?",
                    params,
                )
                if cur.rowcount == 0:
                    return None
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def delete_application(app_id: int) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def reminders(today: date) -> list[dict]:
    """Open applications with a deadline on or before today + 14 days (overdue included)."""
    cutoff = (today + timedelta(days=REMINDER_WINDOW_DAYS)).isoformat()
    placeholders = ", ".join("?" for _ in TERMINAL_STATUSES)
    conn = _connect()
    try:
        rows = conn.execute(
            f"""
            SELECT * FROM applications
            WHERE deadline IS NOT NULL
              AND status NOT IN ({placeholders})
              AND deadline <= ?
            ORDER BY deadline, id
            """,
            (*TERMINAL_STATUSES, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
