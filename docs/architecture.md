# Architecture - AI IT Support Assistant

This document is the dedicated architecture diagram/reference for the project (see
also [README.md](../README.md) for the narrative overview).

## 1. System / Component Architecture

```mermaid
flowchart TB
    subgraph UI["Presentation Layer"]
        ST["Streamlit Chat UI<br/>app.py"]
    end

    subgraph AGENT["Agentic Orchestration Layer - LangGraph"]
        G["Compiled StateGraph<br/>src/agent/graph.py"]
        MS[("MemorySaver Checkpointer<br/>keyed by per-session thread_id")]
        G <--> MS
    end

    subgraph REASONING["Reasoning Layer"]
        LLM["LLM Provider (optional)<br/>OpenAI / Gemini<br/>tool / function calling<br/>src/agent/llm.py"]
        RULES["Deterministic Rule-based Fallback<br/>src/agent/rules.py"]
    end

    subgraph TOOLS["Tool Layer - LangChain @tool functions"]
        T1["knowledge_search"]
        T2["ticket_lookup"]
        T3["create_ticket<br/>+ find_duplicate_ticket"]
        T4["employee_lookup"]
        T5["system_status_check"]
    end

    subgraph DATA["Data Layer"]
        DB[("In-memory SQLite<br/>src/database/db.py")]
        JSON["data/*.json sample seed files"]
        JSON -->|seeded once at startup| DB
    end

    ST -->|"1. user message"| G
    G -->|"2. classify_intent node"| LLM
    G -.->|"fallback when no API key configured"| RULES
    LLM -->|"tool_name + tool_args"| G
    RULES -->|"tool_name + tool_args"| G
    G -->|"3. conditional routing"| T1 & T2 & T3 & T4 & T5
    T1 & T2 & T3 & T4 & T5 -->|"4. SQL query / insert"| DB
    T1 & T2 & T3 & T4 & T5 -->|"5. tool_result"| G
    G -->|"6. final_response"| ST
```

## 2. LangGraph Workflow (State, Nodes, Conditional Routing)

```mermaid
flowchart TD
    U["User message"] --> CI["classify_intent<br/>(Intent / Decision Node)"]

    CI -->|"tool: employee_lookup"| EL["employee_lookup node"]
    CI -->|"tool: knowledge_search"| KS["knowledge_search node"]
    CI -->|"tool: ticket_lookup"| TL["ticket_lookup node"]
    CI -->|"tool: create_ticket"| TC["ticket_creation node<br/>(validation + duplicate check<br/>+ confirmation)"]
    CI -->|"tool: system_status_check"| SS["system_status node"]
    CI -->|"no tool / chit-chat / cancel"| DR["direct_response node"]

    EL --> RG["response_generation node"]
    KS --> RG
    TL --> RG
    TC --> RG
    SS --> RG

    RG --> END1(["Final Answer"])
    DR --> END2(["Final Answer"])
```

## 3. Component Responsibilities

| Component | File(s) | Responsibility |
|---|---|---|
| Streamlit UI | `app.py` | Chat input/history, sidebar (session status, tool trace, clear/reset), error display |
| Agent state | `src/agent/state.py` | `AgentState` TypedDict - messages, employee identity, pending confirmations, ticket draft, trace |
| Intent/decision | `src/agent/nodes.py::classify_intent_node` | LLM tool-calling or rule-based fallback; interprets replies to pending confirmations |
| Conditional routing | `src/agent/nodes.py::route_after_intent` | Chooses next node from tool_name / pending_action / reply type |
| Tool nodes | `src/agent/nodes.py` | Slot validation, calls the matching `@tool`, updates state |
| Tools | `src/tools/*.py` | LangChain `@tool` functions executing SQL against the in-memory DB |
| Data layer | `src/database/db.py`, `data/*.json` | In-memory SQLite schema + seeding + reset |
| LLM selection | `src/agent/llm.py` | Picks OpenAI/Gemini based on `.env`, or `None` for fallback mode |
| Rule-based fallback | `src/agent/rules.py` | Regex/keyword classification, confirmations, category inference - used with or without an LLM |
| Response generation | `src/agent/nodes.py::response_generation_node` | Turns tool_result into the final user-facing message |
