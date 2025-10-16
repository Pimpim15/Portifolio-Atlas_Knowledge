"""Middleware para adicionar cabeçalhos de segurança padrão."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

RequestHandler = Callable[[Request], Awaitable[Response]]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Garante que respostas tenham cabeçalhos de segurança opinativos."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestHandler) -> Response:
        response = await call_next(request)
        self._apply_headers(response)
        return response

    @staticmethod
    def _apply_headers(response: Response) -> None:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
        )
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
