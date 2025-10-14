"""Configuração de logs estruturados."""

import logging
from typing import Any, cast

import structlog
try:
    from opentelemetry import trace  # type: ignore[import]
except ImportError:  # pragma: no cover
    trace = None

from structlog.contextvars import (  # type: ignore[import]
    bind_contextvars,
    clear_contextvars,
    merge_contextvars,
    unbind_contextvars,
)
from structlog.stdlib import BoundLogger  # type: ignore[import]


def _add_trace_context(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    if trace is None:  # pragma: no cover - defensive
        return event_dict

    span = trace.get_current_span()
    context = span.get_span_context()
    if context is not None and context.trace_id != 0:
        event_dict.setdefault("trace_id", f"{context.trace_id:032x}")
        event_dict.setdefault("span_id", f"{context.span_id:016x}")
    return event_dict


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            merge_contextvars,
            _add_trace_context,
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
