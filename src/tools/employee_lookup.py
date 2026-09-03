"""Employee directory lookup - used to verify an employee ID before ticket operations."""
from langchain_core.tools import tool

from src.database.db import get_connection


@tool
def employee_lookup(employee_id: str) -> dict:
    """Verify whether an employee ID exists in the company directory and return basic
    profile details (name, department, role, email) if found."""
    conn = get_connection()
    row = conn.execute(
        "SELECT employee_id, name, department, email, role FROM employees WHERE employee_id = ?",
        (employee_id.strip().upper(),),
    ).fetchone()

    if not row:
        return {"found": False, "employee_id": employee_id}

    return {
        "found": True,
        "employee": {
            "employee_id": row["employee_id"],
            "name": row["name"],
            "department": row["department"],
            "email": row["email"],
            "role": row["role"],
        },
    }
