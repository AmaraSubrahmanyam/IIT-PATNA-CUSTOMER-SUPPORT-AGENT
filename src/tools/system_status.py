"""Bonus tool: System Status - check operational status of IT services."""
from typing import Optional

from langchain_core.tools import tool

from src.database.db import get_connection


@tool
def system_status_check(service_name: Optional[str] = None) -> dict:
    """Check the current operational status of IT services (e.g. VPN, Email, WiFi,
    Printers, HR Portal). Omit service_name to list the status of all services."""
    conn = get_connection()

    if service_name:
        rows = conn.execute(
            "SELECT * FROM system_status WHERE lower(service_name) LIKE ?",
            (f"%{service_name.strip().lower()}%",),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM system_status").fetchall()

    return {"found": bool(rows), "services": [dict(row) for row in rows]}
