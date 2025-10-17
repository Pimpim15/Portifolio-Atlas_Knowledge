"""Configuração de logs estruturados com proteção de PII."""

import logging
import re
from types import ModuleType
from typing import Any, Iterable, cast

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars, unbind_contextvars
from structlog.stdlib import BoundLogger
from structlog.typing import EventDict, Processor, WrappedLogger

from ..config import get_settings

MASKED = "***redacted***"
EMAIL_PATTERN = re.compile(r"([^@\s]+)@([^@\s]+)")
TOKEN_KEYS = ("token", "secret", "password", "key")


def _load_trace_module() -> ModuleType | None:
    try:
        from opentelemetry import trace as trace_module
    except ImportError:  # pragma: no cover
        return None
    return trace_module


ot_trace = _load_trace_module()


def _add_trace_context(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    if ot_trace is None:  # pragma: no cover - defensive
        return event_dict

    span = ot_trace.get_current_span()
    context = span.get_span_context()
    if context is not None and context.trace_id != 0:
        event_dict.setdefault("trace_id", f"{context.trace_id:032x}")
        event_dict.setdefault("span_id", f"{context.span_id:016x}")
    return event_dict


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        masked = EMAIL_PATTERN.sub(MASKED, value)
        if any(keyword in value.lower() for keyword in TOKEN_KEYS):
            return MASKED
        return masked
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return type(value)(_mask_value(item) for item in value)
    if isinstance(value, dict):
        return {key: _mask_value(val) for key, val in value.items()}
    return value


def _mask_sensitive_fields(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    settings = get_settings()
    for field in settings.log_mask_fields:
        if field in event_dict:
            event_dict[field] = _mask_value(event_dict[field])
    for key in list(event_dict.keys()):
        if any(suspicious in key.lower() for suspicious in TOKEN_KEYS):
            event_dict[key] = MASKED
    return event_dict


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    processors: list[Processor] = [
        merge_contextvars,
        _add_trace_context,
        _mask_sensitive_fields,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.filter_by_level,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
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
