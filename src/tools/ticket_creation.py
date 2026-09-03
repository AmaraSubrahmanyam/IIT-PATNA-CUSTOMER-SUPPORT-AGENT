"""Tool 3: Ticket Creation - create a new support ticket in the local SQLite database."""
from datetime import datetime, timezone
from typing import Optional

from langchain_core.tools import tool

from src.database.db import get_connection, next_ticket_id
from src.utils.logging_config import logger


def find_duplicate_ticket(employee_id: str, issue_description: str) -> Optional[dict]:
    """Return an existing open/in-progress ticket for this employee that appears to
    describe the same issue (simple keyword-overlap heuristic), if any.

    This is deliberately kept outside the LLM-callable tool so duplicate checking is
    always enforced by the agent, regardless of what the LLM decides to do.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE employee_id = ? AND status IN ('Open', 'In Progress')",
        (employee_id.strip().upper(),),
    ).fetchall()

    new_words = {w.lower() for w in issue_description.split() if len(w) > 3}
    for row in rows:
        existing_words = {w.lower() for w in row["description"].split() if len(w) > 3}
        if not new_words or not existing_words:
            continue
        overlap = len(new_words & existing_words) / len(new_words | existing_words)
        if overlap >= 0.3:
            return dict(row)
    return None


@tool
def create_ticket(employee_id: str, issue_description: str, category: str = "General", priority: str = "Medium") -> dict:
    """Create a new IT support ticket for a verified employee. Only call this after all
    required details (employee_id, issue_description) have been confirmed with the user -
    never invent or assume ticket details."""
    conn = get_connection()
    ticket_id = next_ticket_id(conn)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn.execute(
        "INSERT INTO tickets (ticket_id, employee_id, category, description, status, priority, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (ticket_id, employee_id.strip().upper(), category, issue_description, "Open", priority, now, now),
    )
    conn.commit()
    logger.info("Created ticket %s for %s (category=%s, priority=%s)", ticket_id, employee_id, category, priority)

    ticket = {
        "ticket_id": ticket_id,
        "employee_id": employee_id.strip().upper(),
        "category": category,
        "description": issue_description,
        "status": "Open",
        "priority": priority,
        "created_at": now,
        "updated_at": now,
    }
    return {"created": True, "ticket": ticket}
