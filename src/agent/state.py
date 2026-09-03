"""LangGraph agent state schema."""
import operator
from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # Full conversation history - accumulated automatically via the add_messages reducer.
    messages: Annotated[list, add_messages]

    # Verified employee context, retained across turns.
    employee_id: Optional[str]
    employee_name: Optional[str]
    employee_verified: bool

    # Multi-turn slot-filling / confirmation state machine.
    pending_action: Optional[str]
    resume_intent: Optional[str]
    pending_ticket_draft: Optional[dict]

    # Current-turn routing decision.
    tool_name: Optional[str]
    tool_args: Optional[dict]
    tool_result: Optional[dict]
    last_tool: Optional[str]
    last_user_reply_type: Optional[str]
    assistant_text: Optional[str]

    # Output.
    final_response: Optional[str]
    last_ticket_id: Optional[str]

    # Tool/action audit trail - accumulated automatically, shown in the UI sidebar.
    trace: Annotated[list, operator.add]
