"""Endpoints de healthcheck."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readiness")
def readiness() -> dict[str, str]:
    return {"status": "ready"}
