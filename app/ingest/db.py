"""SQLite storage for ingested scheme records and the sync log.

Uses the same database file as app/store.py. The path is resolved on every call
(via app.store.db_path()) so tests can point HAQFINDER_DB elsewhere. Each call
opens a fresh connection and closes it. Stdlib only.
"""

import datetime
import json
import sqlite3

from .. import store as _store

INGEST_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS schemes (
        scheme_id TEXT PRIMARY KEY,
        json TEXT NOT NULL,
        source_id TEXT,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL,
        ran_at TEXT NOT NULL,
        status TEXT NOT NULL,
        accepted INTEGER NOT NULL,
        rejected INTEGER NOT NULL,
        message TEXT
    )
    """,
)

_UPSERT_SQL = """
    INSERT INTO schemes (scheme_id, json, source_id, updated_at)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(scheme_id) DO UPDATE SET
        json = excluded.json,
        source_id = excluded.source_id,
        updated_at = excluded.updated_at
"""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    path = _store.db_path()
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path))


def init_ingest_tables() -> None:
    """Create the schemes and sync_log tables if they do not exist."""
    conn = _connect()
    try:
        with conn:
            for statement in INGEST_SCHEMA_SQL:
                conn.execute(statement)
    finally:
        conn.close()


def list_live_schemes() -> list[dict]:
    """Return all live scheme records, ordered by scheme_id."""
    init_ingest_tables()
    conn = _connect()
    try:
        rows = conn.execute("SELECT json FROM schemes ORDER BY scheme_id").fetchall()
        return [json.loads(row[0]) for row in rows]
    finally:
        conn.close()


def get_live_scheme(scheme_id: str) -> dict | None:
    """Return one live scheme record by scheme_id, or None."""
    init_ingest_tables()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT json FROM schemes WHERE scheme_id = ?", (scheme_id,)
        ).fetchone()
        return json.loads(row[0]) if row is not None else None
    finally:
        conn.close()


def replace_live_schemes_in_transaction(records: list[dict]) -> None:
    """Upsert every record in ONE transaction. Records not in the batch are kept.

    Any error rolls the whole batch back and is re-raised for the caller.
    """
    init_ingest_tables()
    conn = _connect()
    try:
        with conn:
            for rec in records:
                scheme_id = rec.get("scheme_id")
                if not scheme_id:
                    raise ValueError("record without scheme_id cannot be stored")
                conn.execute(
                    _UPSERT_SQL,
                    (
                        scheme_id,
                        json.dumps(rec, ensure_ascii=False, sort_keys=True),
                        rec.get("source_id"),
                        _now(),
                    ),
                )
    finally:
        conn.close()


def write_sync_log(source_id: str, status: str, accepted: int, rejected: int,
                   message: str | None) -> None:
    """Append one row to sync_log. status is 'ok' or 'failed'."""
    init_ingest_tables()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO sync_log (source_id, ran_at, status, accepted, rejected, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source_id, _now(), status, int(accepted), int(rejected), message),
            )
    finally:
        conn.close()


def last_successful_sync(source_id: str) -> str | None:
    """Return ran_at of the latest 'ok' sync for source_id, or None."""
    init_ingest_tables()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT ran_at FROM sync_log
            WHERE source_id = ? AND status = 'ok'
            ORDER BY id DESC LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()


def recent_sync_log(limit: int = 20) -> list[dict]:
    """Return the newest sync_log rows first."""
    init_ingest_tables()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, source_id, ran_at, status, accepted, rejected, message
            FROM sync_log ORDER BY id DESC LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        keys = ("id", "source_id", "ran_at", "status", "accepted", "rejected", "message")
        return [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()
