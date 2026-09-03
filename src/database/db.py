"""In-memory SQLite database layer.

The application never connects to any external/remote database. A single
SQLite connection opened with ``:memory:`` is created for the lifetime of the
Streamlit process and seeded from the local JSON sample data in ``data/``.
"""
import json
import sqlite3
from pathlib import Path
from threading import Lock

from src.utils.logging_config import logger

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

SCHEMA = """
CREATE TABLE employees (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT,
    email TEXT,
    role TEXT
);

CREATE TABLE tickets (
    ticket_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    category TEXT,
    description TEXT,
    status TEXT,
    priority TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE knowledge_base (
    article_id TEXT PRIMARY KEY,
    title TEXT,
    category TEXT,
    keywords TEXT,
    content TEXT
);

CREATE TABLE system_status (
    service_name TEXT PRIMARY KEY,
    status TEXT,
    last_updated TEXT,
    details TEXT
);
"""

_connection: sqlite3.Connection | None = None
_lock = Lock()


def _load_json(filename: str) -> list:
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def _seed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    for e in _load_json("employees.json"):
        cur.execute(
            "INSERT INTO employees VALUES (?,?,?,?,?)",
            (e["employee_id"], e["name"], e["department"], e["email"], e["role"]),
        )

    for t in _load_json("tickets_seed.json"):
        cur.execute(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?)",
            (
                t["ticket_id"], t["employee_id"], t["category"], t["description"],
                t["status"], t["priority"], t["created_at"], t["updated_at"],
            ),
        )

    for k in _load_json("knowledge_base.json"):
        cur.execute(
            "INSERT INTO knowledge_base VALUES (?,?,?,?,?)",
            (k["article_id"], k["title"], k["category"], json.dumps(k["keywords"]), k["content"]),
        )

    for s in _load_json("system_status.json"):
        cur.execute(
            "INSERT INTO system_status VALUES (?,?,?,?)",
            (s["service_name"], s["status"], s["last_updated"], s["details"]),
        )

    conn.commit()
    logger.info("Seeded in-memory SQLite database from sample data in %s", DATA_DIR)


def init_db() -> sqlite3.Connection:
    """Create (once) a fresh in-memory SQLite database seeded from local JSON sample data."""
    global _connection
    with _lock:
        if _connection is None:
            conn = sqlite3.connect(":memory:", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.executescript(SCHEMA)
            _seed(conn)
            _connection = conn
    return _connection


def get_connection() -> sqlite3.Connection:
    return _connection if _connection is not None else init_db()


def reset_db() -> sqlite3.Connection:
    """Wipe and recreate the in-memory database from the original sample data."""
    global _connection
    with _lock:
        _connection = None
    logger.info("Resetting in-memory database to original sample data")
    return init_db()


def next_ticket_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT ticket_id FROM tickets ORDER BY ROWID DESC LIMIT 1").fetchone()
    if not row:
        return "TCK-1001"
    last_num = int(row["ticket_id"].split("-")[1])
    return f"TCK-{last_num + 1:04d}"
