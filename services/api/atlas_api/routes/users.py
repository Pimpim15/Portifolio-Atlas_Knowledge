"""Rotas de usuário."""

from fastapi import APIRouter, Depends

from ..deps import CurrentUser, RBACGuard

router = APIRouter()


@router.get("/me")
async def read_me(current_user: CurrentUser = Depends(RBACGuard(["viewer", "editor", "admin"]))) -> dict[str, object]:
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "roles": current_user.roles,
        "organizations": [str(org_id) for org_id in current_user.organization_ids],
    }
