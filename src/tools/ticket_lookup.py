"""Tool 2: Ticket Lookup - search existing support tickets stored locally."""
from typing import Optional

from langchain_core.tools import tool

from src.database.db import get_connection


@tool
def ticket_lookup(employee_id: str, ticket_id: Optional[str] = None) -> dict:
    """Search existing IT support tickets for a given employee, optionally filtered to a
    single ticket_id, and return their current status."""
    conn = get_connection()

    if ticket_id:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE employee_id = ? AND ticket_id = ?",
            (employee_id.strip().upper(), ticket_id.strip().upper()),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE employee_id = ? ORDER BY created_at DESC",
            (employee_id.strip().upper(),),
        ).fetchall()

    tickets = [dict(row) for row in rows]
    return {"found": bool(tickets), "employee_id": employee_id, "tickets": tickets}
