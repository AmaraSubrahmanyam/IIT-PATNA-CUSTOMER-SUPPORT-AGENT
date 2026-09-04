"""LangGraph node implementations for the AI IT Support Assistant.

Each node is a plain function: ``(state: dict) -> dict`` that returns a
partial state update. Nodes never talk to Streamlit directly - they only read
from and write to the shared ``AgentState``.
"""
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.llm import get_llm
from src.agent.rules import classify_category, clean_issue_description, extract_employee_id, is_affirmative, is_negative, rule_based_classify
from src.tools.employee_lookup import employee_lookup
from src.tools.knowledge_search import knowledge_search
from src.tools.system_status import system_status_check
from src.tools.ticket_creation import create_ticket, find_duplicate_ticket
from src.tools.ticket_lookup import ticket_lookup
from src.utils.logging_config import logger

ALL_TOOLS = [knowledge_search, ticket_lookup, create_ticket, employee_lookup, system_status_check]

SYSTEM_PROMPT = (
    "You are an AI IT Support Assistant for a company's internal helpdesk. "
    "Call exactly one tool when the user's request requires it: "
    "knowledge_search - use this whenever the user describes a problem, symptom, or topic and wants "
    "help or troubleshooting steps, even a short phrase or a single word/topic (e.g. 'wifi', 'vpn "
    "password', 'wifi is not working', 'laptop won't turn on', 'how do I set up email'). "
    "ticket_lookup (checking the status of existing tickets, requires employee_id), "
    "create_ticket (raising a new ticket, requires employee_id and issue_description), "
    "employee_lookup (verifying an employee id on its own), "
    "system_status_check - use ONLY for explicit questions about whether a service is having a "
    "known outage right now (e.g. 'is there an outage', 'what is the system status', 'is VPN down "
    "for everyone'). Do NOT use system_status_check when the user is describing their own individual "
    "problem and wants it fixed - use knowledge_search for that instead, even if their wording "
    "includes 'down' or 'not working'. "
    "If the user is only greeting you or asking something unrelated to these tools, reply directly "
    "without calling a tool. Never invent ticket IDs, employee names, or knowledge base content - "
    "only use information returned by tools."
)


def _last_human_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content
    return ""


def _phrase_with_llm(system_hint: str, context: str) -> Optional[str]:
    llm = get_llm()
    if llm is None:
        return None
    try:
        response = llm.invoke([SystemMessage(content=system_hint), HumanMessage(content=context)])
        return response.content
    except Exception:
        logger.exception("LLM phrasing call failed, falling back to template response")
        return None


def _fresh_classify(state: dict) -> dict:
    """Classify the latest user message with no assumptions about pending state -
    via LLM function-calling when available, otherwise the deterministic rules."""
    llm = get_llm()
    if llm is not None:
        llm_with_tools = llm.bind_tools(ALL_TOOLS)
        history = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
        response = llm_with_tools.invoke(history)
        if response.tool_calls:
            call = response.tool_calls[0]
            return {"tool_name": call["name"], "tool_args": call["args"], "assistant_text": None, "mode": "llm"}
        return {"tool_name": None, "tool_args": {}, "assistant_text": response.content, "mode": "llm"}

    classification = rule_based_classify(_last_human_text(state["messages"]))
    return {**classification, "assistant_text": None, "mode": "rules"}


# ---------------------------------------------------------------------------
# Node: classify_intent - the "Intent / Decision" node of the workflow.
# ---------------------------------------------------------------------------
def classify_intent_node(state: dict) -> dict:
    user_text = _last_human_text(state["messages"])
    pending = state.get("pending_action")

    if pending == "await_employee_id":
        emp_id = extract_employee_id(user_text)
        if emp_id:
            return {
                "tool_args": {"employee_id": emp_id},
                "last_user_reply_type": "info",
                "trace": [{"node": "classify_intent", "pending": pending, "resolved_employee_id": emp_id}],
            }
        escape = _fresh_classify(state)
        if escape.get("tool_name"):
            return {
                **escape,
                "last_user_reply_type": None,
                "pending_action": None,
                "resume_intent": None,
                "trace": [{"node": "classify_intent", "pending": pending, "status": "topic_changed", **escape}],
            }
        return {
            "tool_args": {},
            "last_user_reply_type": "unrecognized",
            "trace": [{"node": "classify_intent", "pending": pending, "status": "no_employee_id_found"}],
        }

    if pending == "await_action_confirmation":
        if is_affirmative(user_text):
            return {"last_user_reply_type": "affirmative", "trace": [{"node": "classify_intent", "pending": pending, "reply": "affirmative"}]}
        if is_negative(user_text):
            return {"last_user_reply_type": "negative", "trace": [{"node": "classify_intent", "pending": pending, "reply": "negative"}]}
        escape = _fresh_classify(state)
        if escape.get("tool_name"):
            return {
                **escape,
                "last_user_reply_type": None,
                "pending_action": None,
                "resume_intent": None,
                "trace": [{"node": "classify_intent", "pending": pending, "status": "topic_changed", **escape}],
            }
        return {"last_user_reply_type": "unrecognized", "trace": [{"node": "classify_intent", "pending": pending, "reply": "unrecognized"}]}

    if pending == "await_ticket_details":
        return {
            "tool_args": {"issue_description": clean_issue_description(user_text)},
            "last_user_reply_type": "info",
            "trace": [{"node": "classify_intent", "pending": pending}],
        }

    if pending in ("await_ticket_confirmation", "await_duplicate_confirmation"):
        if is_affirmative(user_text):
            return {"last_user_reply_type": "affirmative", "trace": [{"node": "classify_intent", "pending": pending, "reply": "affirmative"}]}
        if is_negative(user_text):
            return {"last_user_reply_type": "negative", "trace": [{"node": "classify_intent", "pending": pending, "reply": "negative"}]}
        escape = _fresh_classify(state)
        if escape.get("tool_name"):
            return {
                **escape,
                "last_user_reply_type": None,
                "pending_action": None,
                "resume_intent": None,
                "pending_ticket_draft": None,
                "trace": [{"node": "classify_intent", "pending": pending, "status": "topic_changed", **escape}],
            }
        return {"last_user_reply_type": "unrecognized", "trace": [{"node": "classify_intent", "pending": pending, "reply": "unrecognized"}]}

    # No pending slot-filling - classify the message fresh.
    classification = _fresh_classify(state)
    return {
        **classification,
        "last_user_reply_type": None,
        "trace": [{"node": "classify_intent", **classification}],
    }


# ---------------------------------------------------------------------------
# Conditional routing after intent classification.
# ---------------------------------------------------------------------------
TOOL_ROUTE = {
    "knowledge_search": "knowledge_search",
    "ticket_lookup": "ticket_lookup",
    "create_ticket": "ticket_creation",
    "employee_lookup": "employee_lookup",
    "system_status_check": "system_status",
}
RESUME_ROUTE = {"ticket_lookup": "ticket_lookup", "ticket_creation": "ticket_creation"}


def route_after_intent(state: dict) -> str:
    pending = state.get("pending_action")
    reply_type = state.get("last_user_reply_type")

    if pending == "await_employee_id":
        return "employee_lookup" if reply_type == "info" else "direct_response"

    if pending == "await_action_confirmation":
        if reply_type == "affirmative":
            return RESUME_ROUTE.get(state.get("resume_intent"), "direct_response")
        return "direct_response"

    if pending == "await_ticket_details":
        return "ticket_creation" if reply_type == "info" else "direct_response"

    if pending in ("await_ticket_confirmation", "await_duplicate_confirmation"):
        return "ticket_creation" if reply_type == "affirmative" else "direct_response"

    return TOOL_ROUTE.get(state.get("tool_name"), "direct_response")


# ---------------------------------------------------------------------------
# Node: employee_lookup - reached only when resuming after an employee ID was
# explicitly requested from the user (adds a courtesy confirmation prompt).
# ---------------------------------------------------------------------------
def employee_lookup_node(state: dict) -> dict:
    args = state.get("tool_args") or {}
    employee_id = args.get("employee_id")
    result = employee_lookup.invoke({"employee_id": employee_id})
    trace_entry = {"node": "employee_lookup", "employee_id": employee_id, "found": result.get("found")}

    if not result.get("found"):
        return {
            "tool_result": result,
            "last_tool": "employee_lookup",
            "pending_action": "await_employee_id",
            "trace": [trace_entry],
        }

    employee = result["employee"]
    updates = {
        "tool_result": result,
        "last_tool": "employee_lookup",
        "employee_id": employee["employee_id"],
        "employee_name": employee["name"],
        "employee_verified": True,
        "trace": [trace_entry],
    }
    updates["pending_action"] = "await_action_confirmation" if state.get("resume_intent") else None
    return updates


def _ensure_employee_verified(state: dict, employee_id: Optional[str]) -> tuple[bool, dict]:
    """Inline verification used when an employee_id is already supplied with the
    current request (no extra confirmation round needed)."""
    if not employee_id:
        return False, {}
    normalized = employee_id.strip().upper()
    if state.get("employee_verified") and state.get("employee_id") == normalized:
        return True, {}
    result = employee_lookup.invoke({"employee_id": employee_id})
    if not result.get("found"):
        return False, {"tool_result": result, "last_tool": "employee_lookup"}
    employee = result["employee"]
    return True, {"employee_id": employee["employee_id"], "employee_name": employee["name"], "employee_verified": True}


# ---------------------------------------------------------------------------
# Node: knowledge_search (Tool 1)
# ---------------------------------------------------------------------------
def knowledge_search_node(state: dict) -> dict:
    args = state.get("tool_args") or {}
    query = args.get("query") or _last_human_text(state["messages"])
    result = knowledge_search.invoke({"query": query})
    return {
        "tool_result": result,
        "last_tool": "knowledge_search",
        "trace": [{"node": "knowledge_search", "query": query, "found": result.get("found")}],
    }


# ---------------------------------------------------------------------------
# Node: ticket_lookup (Tool 2)
# ---------------------------------------------------------------------------
def ticket_lookup_node(state: dict) -> dict:
    args = dict(state.get("tool_args") or {})
    employee_id = args.get("employee_id") or state.get("employee_id")

    if not employee_id:
        return {
            "pending_action": "await_employee_id",
            "resume_intent": "ticket_lookup",
            "tool_result": None,
            "last_tool": "ticket_lookup",
            "trace": [{"node": "ticket_lookup", "status": "missing_employee_id"}],
        }

    verified, updates = _ensure_employee_verified(state, employee_id)
    if not verified:
        updates["pending_action"] = "await_employee_id"
        updates["resume_intent"] = "ticket_lookup"
        updates["trace"] = [{"node": "ticket_lookup", "status": "employee_not_found", "employee_id": employee_id}]
        return updates

    employee_id = updates.get("employee_id", employee_id)
    result = ticket_lookup.invoke({"employee_id": employee_id, "ticket_id": args.get("ticket_id")})
    updates.update(
        {
            "tool_result": result,
            "last_tool": "ticket_lookup",
            "pending_action": None,
            "resume_intent": None,
            "trace": [{"node": "ticket_lookup", "employee_id": employee_id, "found": result.get("found")}],
        }
    )
    return updates


# ---------------------------------------------------------------------------
# Node: ticket_creation (Tool 3) - the most validation-heavy node.
# ---------------------------------------------------------------------------
def ticket_creation_node(state: dict) -> dict:
    args = dict(state.get("tool_args") or {})
    draft = dict(state.get("pending_ticket_draft") or {})
    for key in ("employee_id", "issue_description", "category", "priority"):
        if args.get(key):
            draft[key] = args[key]

    employee_id = draft.get("employee_id") or state.get("employee_id")
    if employee_id:
        draft["employee_id"] = employee_id.strip().upper()

    # Step 1: require a verified employee.
    if not draft.get("employee_id"):
        return {
            "pending_action": "await_employee_id",
            "resume_intent": "ticket_creation",
            "pending_ticket_draft": draft,
            "tool_result": None,
            "last_tool": "create_ticket",
            "trace": [{"node": "ticket_creation", "status": "missing_employee_id"}],
        }

    verified, employee_updates = _ensure_employee_verified(state, draft["employee_id"])
    if not verified:
        result = {
            "pending_action": "await_employee_id",
            "resume_intent": "ticket_creation",
            "pending_ticket_draft": draft,
            "last_tool": "create_ticket",
            "trace": [{"node": "ticket_creation", "status": "employee_not_found"}],
        }
        result.update(employee_updates)
        return result
    draft.update({k: v for k, v in employee_updates.items() if k != "tool_result" and k != "last_tool"})

    # Step 2: require an issue description.
    if not draft.get("issue_description"):
        return {
            "pending_action": "await_ticket_details",
            "resume_intent": "ticket_creation",
            "pending_ticket_draft": draft,
            "tool_result": None,
            "last_tool": "create_ticket",
            "trace": [{"node": "ticket_creation", "status": "missing_description"}],
        }

    draft.setdefault("category", classify_category(draft["issue_description"]))
    draft.setdefault("priority", "Medium")

    already_confirming = state.get("pending_action") in ("await_ticket_confirmation", "await_duplicate_confirmation")
    confirmed_now = already_confirming and state.get("last_user_reply_type") == "affirmative"

    # Step 3: safety checks - duplicate detection, then explicit confirmation before creating.
    if not confirmed_now:
        duplicate = find_duplicate_ticket(draft["employee_id"], draft["issue_description"])
        if duplicate:
            return {
                "pending_action": "await_duplicate_confirmation",
                "resume_intent": "ticket_creation",
                "pending_ticket_draft": draft,
                "tool_result": {"duplicate": duplicate},
                "last_tool": "create_ticket",
                "trace": [{"node": "ticket_creation", "status": "duplicate_found", "duplicate_id": duplicate["ticket_id"]}],
            }
        return {
            "pending_action": "await_ticket_confirmation",
            "resume_intent": "ticket_creation",
            "pending_ticket_draft": draft,
            "tool_result": None,
            "last_tool": "create_ticket",
            "trace": [{"node": "ticket_creation", "status": "awaiting_confirmation", "draft": draft}],
        }

    # Step 4: user confirmed - actually create the ticket.
    result = create_ticket.invoke(
        {
            "employee_id": draft["employee_id"],
            "issue_description": draft["issue_description"],
            "category": draft["category"],
            "priority": draft["priority"],
        }
    )
    return {
        "tool_result": result,
        "last_tool": "create_ticket",
        "pending_action": None,
        "resume_intent": None,
        "pending_ticket_draft": None,
        "last_ticket_id": result["ticket"]["ticket_id"],
        "trace": [{"node": "ticket_creation", "status": "created", "ticket_id": result["ticket"]["ticket_id"]}],
    }


# ---------------------------------------------------------------------------
# Node: system_status (bonus tool)
# ---------------------------------------------------------------------------
def system_status_node(state: dict) -> dict:
    args = state.get("tool_args") or {}
    result = system_status_check.invoke({"service_name": args.get("service_name")})
    return {
        "tool_result": result,
        "last_tool": "system_status",
        "trace": [{"node": "system_status", "found": result.get("found")}],
    }


# ---------------------------------------------------------------------------
# Response formatting helpers.
# ---------------------------------------------------------------------------
def _format_knowledge_answer(result: dict) -> str:
    if not result.get("found"):
        return "I couldn't find a knowledge base article matching that. Would you like me to raise a support ticket instead?"

    article = result["articles"][0]
    phrased = _phrase_with_llm(
        "You are an IT support assistant. Using ONLY the retrieved article content below, answer the "
        "user's question clearly and concisely. Do not invent steps that aren't in the article.",
        f"Article title: {article['title']}\nArticle content: {article['content']}\n\nUser question: {result['query']}",
    )
    if phrased:
        return f"{phrased}\n\n*(Source: KB article \u201c{article['title']}\u201d)*"
    return f"**{article['title']}**\n\n{article['content']}"


def _format_ticket_lookup_answer(result: dict) -> str:
    if not result.get("found"):
        return f"I couldn't find any tickets for employee {result.get('employee_id')}."
    lines = ["Here are your tickets:"]
    for ticket in result["tickets"]:
        lines.append(
            f"- **{ticket['ticket_id']}** [{ticket['status']}] {ticket['category']} - "
            f"{ticket['description']} (Priority: {ticket['priority']})"
        )
    return "\n".join(lines)


def _format_system_status_answer(result: dict) -> str:
    if not result.get("found"):
        return "I couldn't find status information for that service."
    lines = ["Current system status:"]
    for service in result["services"]:
        lines.append(f"- **{service['service_name']}**: {service['status']} - {service['details']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Node: response_generation - phrases the tool result into a final answer.
# ---------------------------------------------------------------------------
def response_generation_node(state: dict) -> dict:
    last_tool = state.get("last_tool")
    result = state.get("tool_result") or {}
    pending = state.get("pending_action")

    if last_tool == "employee_lookup":
        if result.get("found"):
            action_label = {
                "ticket_lookup": "check your existing tickets",
                "ticket_creation": "continue creating your support ticket",
            }.get(state.get("resume_intent"), "continue")
            employee = result["employee"]
            text = (
                f"Thanks, I found your profile: **{employee['name']}** ({employee['department']}). "
                f"Would you like me to {action_label}? (yes/no)"
            )
        else:
            text = "I couldn't find an employee record for that ID. Please double-check your employee ID (format: EMP1024) and try again."

    elif last_tool == "knowledge_search":
        text = _format_knowledge_answer(result)

    elif last_tool == "ticket_lookup":
        text = _format_ticket_lookup_answer(result)

    elif last_tool == "create_ticket":
        if pending == "await_ticket_confirmation":
            draft = state.get("pending_ticket_draft") or {}
            text = (
                "I'd like to create the following ticket:\n\n"
                f"- Category: {draft.get('category')}\n- Priority: {draft.get('priority')}\n"
                f"- Description: {draft.get('issue_description')}\n\nShall I proceed? (yes/no)"
            )
        elif pending == "await_duplicate_confirmation":
            duplicate = result.get("duplicate", {})
            text = (
                f"You already have an open ticket **{duplicate.get('ticket_id')}** that looks similar: "
                f"\u201c{duplicate.get('description')}\u201d (Status: {duplicate.get('status')}). "
                "Would you still like me to create a new ticket anyway? (yes/no)"
            )
        elif pending == "await_employee_id":
            text = "To raise a ticket, I first need to verify you. Could you share your employee ID (e.g. EMP1024)?"
        elif pending == "await_ticket_details":
            text = "Sure, I can raise a ticket - could you briefly describe the issue?"
        else:
            ticket = result["ticket"]
            text = (
                f"\u2705 Your ticket has been created: **{ticket['ticket_id']}** "
                f"({ticket['category']}, {ticket['priority']} priority, status: {ticket['status']})."
            )

    elif last_tool == "system_status":
        text = _format_system_status_answer(result)

    else:
        text = "Here is what I found."

    return {
        "messages": [AIMessage(content=text)],
        "final_response": text,
        "trace": [{"node": "response_generation", "last_tool": last_tool}],
    }


# ---------------------------------------------------------------------------
# Node: direct_response - handles chit-chat, cancellations, and unrecognized replies.
# ---------------------------------------------------------------------------
def direct_response_node(state: dict) -> dict:
    pending = state.get("pending_action")
    reply_type = state.get("last_user_reply_type")
    updates: dict = {}

    if pending == "await_employee_id" and reply_type != "info":
        text = "I couldn't find a valid employee ID in your message. Could you share it, e.g. EMP1024?"

    elif pending == "await_action_confirmation":
        if reply_type == "negative":
            text = "No problem, let me know if there's anything else I can help with."
            updates.update({"pending_action": None, "resume_intent": None})
        else:
            action_label = {
                "ticket_lookup": "check your existing tickets",
                "ticket_creation": "continue creating your support ticket",
            }.get(state.get("resume_intent"), "proceed")
            text = f"Sorry, I didn't quite catch that - would you like me to {action_label}? (yes/no)"

    elif pending == "await_ticket_details" and reply_type != "info":
        text = "Could you briefly describe the issue so I can log a ticket for you?"

    elif pending in ("await_ticket_confirmation", "await_duplicate_confirmation"):
        if reply_type == "negative":
            text = "Okay, I won't create the ticket. Let me know if you'd like to try again."
            updates.update({"pending_action": None, "resume_intent": None, "pending_ticket_draft": None})
        else:
            draft = state.get("pending_ticket_draft") or {}
            text = (
                f"Sorry, please reply yes or no - shall I create a {draft.get('priority', 'Medium')}-priority "
                f"'{draft.get('category', 'General')}' ticket for: \u201c{draft.get('issue_description', '')}\u201d?"
            )

    elif state.get("assistant_text"):
        text = state["assistant_text"]

    else:
        text = _phrase_with_llm(
            "You are a friendly IT support assistant. Respond briefly and helpfully.",
            _last_human_text(state["messages"]),
        ) or (
            "I'm here to help with IT support - password resets, checking ticket status, "
            "raising new tickets, or checking system status. What do you need help with?"
        )

    updates["messages"] = [AIMessage(content=text)]
    updates["final_response"] = text
    updates["trace"] = [{"node": "direct_response", "text": text}]
    return updates
