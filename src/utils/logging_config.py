"""Basic application-wide logging configuration."""
import logging

from src.config import settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _configured = True


configure_logging()
logger = logging.getLogger("support_assistant")
