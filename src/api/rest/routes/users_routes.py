from fastapi import APIRouter, Depends

from src.api.rest.dependencies import get_current_user
from src.models.user_models import User

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> dict[str, str | bool]:
    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
