"""
VLT AI — structlog configuration.

Call configure_structlog() once from AppConfig.ready() or settings.
Provides structured JSON logs for VLT AI components so tool calls,
permissions, and LLM interactions are easily queryable in production.
"""
from __future__ import annotations

import logging
import sys


def configure_structlog() -> None:
    """Wire structlog to emit JSON-structured records via stdlib logging."""
    try:
        import structlog
    except ImportError:
        # structlog is optional; fall back to standard logging silently
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Attach to the vlt_ai logger hierarchy only — no side effects on other apps
    vlt_logger = logging.getLogger("apps.vlt_ai")
    if not vlt_logger.handlers:
        vlt_logger.addHandler(handler)
        vlt_logger.propagate = False
    vlt_logger.setLevel(logging.DEBUG)


def get_logger(name: str):
    """Return a structlog logger, falling back to stdlib if structlog absent."""
    try:
        import structlog

        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)
