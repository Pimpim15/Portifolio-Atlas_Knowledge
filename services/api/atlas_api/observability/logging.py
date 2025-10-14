"""Configuração de logs estruturados."""

import logging
from typing import Any, cast

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars, unbind_contextvars
from structlog.stdlib import BoundLogger


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.filter_by_level,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(**initial_values: Any) -> BoundLogger:
    return cast(BoundLogger, structlog.get_logger().bind(**initial_values))


def bind_context(**values: Any) -> None:
    """Associe valores ao contexto de log atual."""

    bind_contextvars(**values)


def unbind_context(*keys: str) -> None:
    """Remove chaves específicas do contexto de log."""

    if keys:
        unbind_contextvars(*keys)
    else:
        clear_contextvars()
