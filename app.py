"""Streamlit UI for the AI IT Support Assistant.

Run with:  streamlit run app.py
"""
from uuid import uuid4

import streamlit as st
from langchain_core.messages import HumanMessage

from src.agent.graph import build_graph
from src.agent.llm import is_llm_available
from src.config import settings
from src.database.db import init_db, reset_db
from src.utils.logging_config import logger

st.set_page_config(page_title="AI IT Support Assistant", page_icon="🛠️", layout="wide")


@st.cache_resource
def get_db():
    return init_db()


@st.cache_resource
def get_graph():
    return build_graph()


get_db()
graph = get_graph()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid4())


def _config() -> dict:
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _current_state() -> dict:
    try:
        snapshot = graph.get_state(_config())
        return snapshot.values if snapshot and snapshot.values else {}
    except Exception:
        return {}


state = _current_state()

st.title("🛠️ AI IT Support Assistant")
st.caption("Agentic AI helpdesk assistant - LangChain + LangGraph + in-memory SQLite (no external services required)")

with st.sidebar:
    st.subheader("Session")
    if is_llm_available():
        st.success(f"LLM mode active ({settings.llm_provider})")
    else:
        st.warning("No LLM API key detected - using rule-based fallback mode.")
        st.caption("Add OPENAI_API_KEY or GOOGLE_API_KEY to your .env file for LLM-powered understanding.")

    if state.get("employee_verified"):
        st.info(f"👤 Verified: **{state.get('employee_name')}** ({state.get('employee_id')})")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧹 Clear chat", use_container_width=True, help="Reset the conversation and agent memory."):
            st.session_state.thread_id = str(uuid4())
            st.rerun()
    with col2:
        if st.button("🔄 Reset data", use_container_width=True, help="Reset tickets/employees back to sample data."):
            reset_db()
            st.session_state.thread_id = str(uuid4())
            st.rerun()

    st.divider()
    st.subheader("Sample employee IDs")
    st.code("EMP1001  EMP1002  EMP1003\nEMP1004  EMP1024  EMP1030", language=None)

    st.divider()
    st.subheader("🔍 Tool activity (this session)")
    trace = state.get("trace", [])
    if trace:
        for entry in reversed(trace[-8:]):
            st.json(entry, expanded=False)
    else:
        st.caption("Tool calls will appear here once you start chatting.")

messages = state.get("messages", [])

if not messages:
    with st.chat_message("assistant"):
        st.markdown(
            "👋 Hi! I'm your IT Support Assistant. I can help you:\n"
            "- 🔎 Find answers in the knowledge base\n"
            "- 🎫 Check the status of your support tickets\n"
            "- 🆕 Raise a new support ticket\n"
            "- 📡 Check system/service status\n\n"
            "What can I help you with today?"
        )

for message in messages:
    role = "user" if isinstance(message, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(message.content)

user_input = st.chat_input("Describe your IT issue, ask about a ticket, or say hello...")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = graph.invoke({"messages": [HumanMessage(content=user_input)]}, config=_config())
                st.markdown(result.get("final_response") or "Sorry, I wasn't able to process that.")
            except Exception as exc:
                logger.exception("Agent invocation failed")
                st.error(f"Something went wrong while processing your request: {exc}")
    st.rerun()
