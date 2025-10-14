"""Rotas de usuário."""

from fastapi import APIRouter, Depends

from ..deps import RBACGuard

router = APIRouter()


@router.get("/me", dependencies=[Depends(RBACGuard(["viewer", "editor", "admin"]))])
def read_me() -> dict[str, list[str] | str]:
    return {"email": "admin@acme.com", "roles": ["admin"]}
