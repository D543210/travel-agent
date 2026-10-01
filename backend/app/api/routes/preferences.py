"""用户长期偏好API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user
from ...db.models import User
from ...db.session import get_db
from ...models.planning_schemas import (
    UserPreferenceResponse,
    UserPreferenceUpdate,
)
from ...services.preference_service import (
    delete_user_preference,
    get_user_preference,
    upsert_user_preference,
)


router = APIRouter(prefix="/preferences", tags=["用户偏好"])


@router.get("/me", response_model=UserPreferenceResponse | None)
def read_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return get_user_preference(db, current_user.id)


@router.put("/me", response_model=UserPreferenceResponse)
def save_preferences(
    request: UserPreferenceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return upsert_user_preference(db, current_user.id, request)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def remove_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    delete_user_preference(db, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
