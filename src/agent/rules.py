"""Deterministic helpers used both as a no-LLM fallback and for safety-critical
parsing (confirmations, employee IDs) that should not depend on an LLM call."""
import re
from typing import Optional

AFFIRMATIVE_WORDS = {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "correct", "proceed", "please"}
NEGATIVE_WORDS = {"no", "n", "nope", "cancel", "stop", "don't", "dont", "never"}
GREETING_WORDS = {"hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye", "ok", "okay", "yes", "no"}

EMPLOYEE_ID_PATTERN = re.compile(r"\bEMP\d{3,6}\b", re.IGNORECASE)

CATEGORY_KEYWORDS = {
    "VPN": ["vpn", "remote access"],
    "Hardware": ["laptop", "hardware", "battery", "screen", "keyboard", "mouse", "monitor", "desktop"],
    "Network": ["wifi", "wi-fi", "network", "internet", "lan", "connectivity"],
    "Email": ["email", "outlook", "mailbox"],
    "Software": ["software", "install", "application", "license", "app"],
    "Security": ["mfa", "2fa", "password", "authenticator", "security", "login", "otp"],
}


def is_affirmative(text: str) -> bool:
    words = set(re.findall(r"[a-z']+", text.lower()))
    return bool(words & AFFIRMATIVE_WORDS)


def is_negative(text: str) -> bool:
    words = set(re.findall(r"[a-z']+", text.lower()))
    return bool(words & NEGATIVE_WORDS)


def extract_employee_id(text: str) -> Optional[str]:
    match = EMPLOYEE_ID_PATTERN.search(text)
    return match.group(0).upper() if match else None


def classify_category(description: str) -> str:
    text = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "General"


_REQUEST_BOILERPLATE = re.compile(
    r"\b(please\s+)?(raise|create|log|open)\s+(a|another|new)?\s*(support\s+)?ticket\b"
    r"|\bplease\s+raise\b"
    r"|\bfor\s+me\b",
    re.IGNORECASE,
)


def clean_issue_description(text: str) -> str:
    """Strip common ticket-request boilerplate (e.g. 'please raise a ticket') so the
    stored ticket description reflects only the actual issue, not the request phrasing."""
    cleaned = _REQUEST_BOILERPLATE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.")
    return cleaned or text


def rule_based_classify(text: str) -> dict:
    """Small deterministic intent classifier used when no LLM API key is configured."""
    lower = text.lower()
    employee_id = extract_employee_id(text)
    service_names = ["vpn", "email", "wifi", "wi-fi", "printer", "hr portal"]
    mentions_service = any(s in lower for s in service_names)

    if any(p in lower for p in ["down", "outage", "system status", "service status"]) and (mentions_service or "status" in lower):
        return {"tool_name": "system_status_check", "tool_args": {}}

    if any(p in lower for p in ["status of my", "check my ticket", "existing ticket", "my ticket", "ticket status"]):
        args = {"employee_id": employee_id} if employee_id else {}
        return {"tool_name": "ticket_lookup", "tool_args": args}

    if any(p in lower for p in ["raise a ticket", "create a ticket", "log a ticket", "open a ticket", "please raise", "raise another ticket"]):
        args = {"issue_description": clean_issue_description(text)}
        if employee_id:
            args["employee_id"] = employee_id
        return {"tool_name": "create_ticket", "tool_args": args}

    if any(p in lower for p in ["how do i", "how to", "reset", "help with", "issue with", "problem with", "not working", "trouble", "won't", "wont"]):
        return {"tool_name": "knowledge_search", "tool_args": {"query": text}}

    if employee_id:
        return {"tool_name": "employee_lookup", "tool_args": {"employee_id": employee_id}}

    # Short bare-topic queries (e.g. "wifi", "vpn password", "printer") don't match any
    # trigger phrase above but still clearly want knowledge base help, not small talk.
    word_count = len(lower.split())
    if word_count <= 4 and not any(g in lower for g in GREETING_WORDS):
        return {"tool_name": "knowledge_search", "tool_args": {"query": text}}

    return {"tool_name": None, "tool_args": {}}
