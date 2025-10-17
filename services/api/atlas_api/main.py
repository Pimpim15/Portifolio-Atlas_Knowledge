"""Ponto de entrada FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .observability.logging import configure_logging
from .observability.middleware import ObservabilityMiddleware
from .observability.tracing import setup_tracing
from .security.headers import SecurityHeadersMiddleware
from .security.ratelimit import init_rate_limiter


def create_app() -> FastAPI:
    configure_logging()
    setup_tracing()

    settings = get_settings()
    app = FastAPI(title="Atlas Knowledge", version="0.1.0")

    limiter = init_rate_limiter()
    app.state.limiter = limiter

    from slowapi.middleware import SlowAPIMiddleware

    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        allow_credentials=settings.cors_allow_credentials,
    )

    from .routes import auth, docs, health, search, users

    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(docs.router, prefix="/docs", tags=["docs"])
    app.include_router(search.router, prefix="/search", tags=["search"])

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded",
                "limit": getattr(exc, "detail", None),
            },
        )

    @app.get("/metrics")
    def metrics_endpoint() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    from .bootstrap import init_application

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await init_application()
        yield

    app.router.lifespan_context = lifespan

    return app


app = create_app()
