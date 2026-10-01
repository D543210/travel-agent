"""用户长期偏好持久化。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import UserPreference
from ..models.planning_schemas import UserPreferenceUpdate


def get_user_preference(db: Session, user_id):
    return db.scalar(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )


def upsert_user_preference(
    db: Session,
    user_id,
    request: UserPreferenceUpdate,
) -> UserPreference:
    preference = get_user_preference(db, user_id)
    values = request.model_dump()

    if preference is None:
        preference = UserPreference(user_id=user_id, **values)
        db.add(preference)
    else:
        for key, value in values.items():
            setattr(preference, key, value)
        preference.version += 1

    db.commit()
    db.refresh(preference)
    return preference


def delete_user_preference(db: Session, user_id) -> bool:
    preference = get_user_preference(db, user_id)
    if preference is None:
        return False
    db.delete(preference)
    db.commit()
    return True


def preference_snapshot(preference: UserPreference | None) -> dict:
    if preference is None:
        return {}
    return {
        "attraction_types": list(preference.attraction_types or []),
        "dietary_restrictions": list(preference.dietary_restrictions or []),
        "travel_pace": preference.travel_pace,
        "transportation_preference": preference.transportation_preference,
        "accommodation_preference": preference.accommodation_preference,
        "version": preference.version,
    }
