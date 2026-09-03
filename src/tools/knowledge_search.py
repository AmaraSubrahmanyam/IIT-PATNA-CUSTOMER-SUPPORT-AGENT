"""Tool 1: Knowledge Search - search the local IT knowledge base."""
import json

from langchain_core.tools import tool

from src.database.db import get_connection


def _score(query_words: list[str], keywords: list[str], title: str, content: str) -> int:
    text = (title + " " + content).lower()
    score = 0
    for word in query_words:
        if word in keywords:
            score += 3
        if word in text:
            score += 1
    return score


@tool
def knowledge_search(query: str) -> dict:
    """Search the local IT knowledge base for articles relevant to the user's question and
    return the best matching article(s) with title, category and full content."""
    conn = get_connection()
    rows = conn.execute("SELECT article_id, title, category, keywords, content FROM knowledge_base").fetchall()

    query_words = [w.strip(".,?!'\"").lower() for w in query.split() if len(w) > 2]
    scored = []
    for row in rows:
        keywords = [k.lower() for k in json.loads(row["keywords"])]
        score = _score(query_words, keywords, row["title"], row["content"])
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    top = scored[:2]
    if not top:
        return {"found": False, "query": query, "articles": []}

    return {
        "found": True,
        "query": query,
        "articles": [
            {
                "article_id": row["article_id"],
                "title": row["title"],
                "category": row["category"],
                "content": row["content"],
            }
            for _, row in top
        ],
    }
