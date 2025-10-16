"""Middlewares de observabilidade (logs + métricas)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .logging import bind_context, get_logger, unbind_context
from .metrics import REQUEST_COUNT, REQUEST_LATENCY

RequestHandler = Callable[[Request], Awaitable[Response]]


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Mede latência, registra métricas e enriquece logs estruturados."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestHandler) -> Response:
        start = time.perf_counter()
        route_template = request.scope.get("route")
        route = getattr(route_template, "path", request.url.path)
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        bind_context(request_id=request_id, route=route, method=request.method)
        logger = get_logger(component="api")

        try:
            response = await call_next(request)
        except Exception:
            status = 500
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(request.method, route, str(status)).inc()
            REQUEST_LATENCY.labels(route).observe(duration)
            logger.exception("request_failed", status=status, duration=duration)
            raise
        else:
            status = response.status_code
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(request.method, route, str(status)).inc()
            REQUEST_LATENCY.labels(route).observe(duration)
            logger.info("request_completed", status=status, duration=duration)
            response.headers.setdefault("x-request-id", request_id)
            return response
        finally:
            unbind_context()
