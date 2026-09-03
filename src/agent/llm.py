"""LLM provider selection.

Supports OpenAI and Google Gemini via LangChain, chosen automatically based on
which API key is configured. If no key is configured, ``get_llm`` returns
``None`` and the agent falls back to the deterministic rule-based logic in
``src/agent/rules.py`` so the app remains fully functional without any paid
external service.
"""
from functools import lru_cache
from typing import Optional

from src.config import settings
from src.utils.logging_config import logger


@lru_cache(maxsize=1)
def get_llm():
    """Return a LangChain chat model instance, or None if no provider is available."""
    provider = settings.llm_provider

    if provider in ("auto", "openai") and settings.openai_api_key:
        try:
            from langchain_openai import ChatOpenAI

            logger.info("Using OpenAI model '%s' for LLM reasoning", settings.openai_model)
            return ChatOpenAI(model=settings.openai_model, temperature=0, api_key=settings.openai_api_key)
        except Exception:
            logger.exception("Failed to initialize OpenAI LLM, falling back")

    if provider in ("auto", "gemini") and settings.google_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            logger.info("Using Gemini model '%s' for LLM reasoning", settings.google_model)
            return ChatGoogleGenerativeAI(model=settings.google_model, temperature=0, google_api_key=settings.google_api_key)
        except Exception:
            logger.exception("Failed to initialize Gemini LLM, falling back")

    logger.warning("No LLM API key configured - running in rule-based fallback mode")
    return None


def is_llm_available() -> bool:
    return get_llm() is not None
