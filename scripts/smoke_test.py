"""Manual smoke test that exercises the LangGraph agent end-to-end in
rule-based fallback mode (no LLM API key configured). Not part of the
graded submission - purely used during development to validate flows."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage

from src.agent.graph import build_graph

graph = build_graph()
config = {"configurable": {"thread_id": "smoke-test-1"}}


def send(text: str):
    result = graph.invoke({"messages": [HumanMessage(content=text)]}, config=config)
    print(f"USER: {text}")
    print(f"BOT : {result.get('final_response')}")
    print("-" * 60)


print("=== Scenario 1: Knowledge search ===")
send("How do I reset my VPN password?")

print("=== Scenario 2: Ticket lookup with missing employee id ===")
send("What is the status of my laptop issue?")
send("EMP1024")
send("yes")

print("=== Scenario 3: Ticket creation with confirmation ===")
send("My VPN is not working, please raise a ticket")
send("yes")

print("=== Scenario 4: Duplicate ticket detection ===")
send("My VPN is still not working, please raise another ticket")

print("=== Scenario 5: System status ===")
send("Is the WiFi down?")

print("=== Scenario 6: Greeting ===")
send("hello")

print("=== Scenario 7: Unknown employee id ===")
send("What is the status of my ticket?")
send("EMP9999")

print("=== Scenario 8: Reject ticket creation ===")
send("My email is not syncing, please raise a ticket")
send("no")
