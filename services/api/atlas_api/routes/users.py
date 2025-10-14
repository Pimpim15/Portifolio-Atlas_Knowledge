"""Rotas de usuário."""

from fastapi import APIRouter, Depends, Request

from ..config import get_settings
from ..deps import CurrentUser, RBACGuard
from ..security.ratelimit import init_rate_limiter

router = APIRouter()
settings = get_settings()
limiter = init_rate_limiter()


@router.get("/me")
@limiter.limit(settings.rate_limit_default)
async def read_me(
    request: Request,
    current_user: CurrentUser = Depends(RBACGuard(["viewer", "editor", "admin"])),
) -> dict[str, object]:
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "roles": current_user.roles,
        "organizations": [str(org_id) for org_id in current_user.organization_ids],
    }
