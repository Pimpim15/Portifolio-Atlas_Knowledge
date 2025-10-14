"""Ponto de entrada FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .observability.logging import configure_logging
from .observability.tracing import setup_tracing
from .security.ratelimit import init_rate_limiter


def create_app() -> FastAPI:
    configure_logging()
    setup_tracing()

    app = FastAPI(title="Atlas Knowledge", version="0.1.0")

    limiter = init_rate_limiter()
    app.state.limiter = limiter

    from slowapi.middleware import SlowAPIMiddleware

    app.add_middleware(SlowAPIMiddleware)

    from .routes import auth, docs, health, search, users

    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(docs.router, prefix="/docs", tags=["docs"])
    app.include_router(search.router, prefix="/search", tags=["search"])

    from .bootstrap import init_application

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await init_application()
        yield

    app.router.lifespan_context = lifespan

    return app


app = create_app()
