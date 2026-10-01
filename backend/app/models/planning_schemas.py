"""偏好、异步任务和行程版本API模型。"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import TripPlan, TripRequest


class UserPreferenceUpdate(BaseModel):
    attraction_types: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=20)
    dietary_restrictions: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=20)
    travel_pace: Literal["舒缓", "适中", "紧凑"] | None = None
    transportation_preference: Literal["公共交通", "自驾", "步行", "混合"] | None = None
    accommodation_preference: Literal["经济型酒店", "舒适型酒店", "豪华酒店", "民宿"] | None = None


class UserPreferenceResponse(UserPreferenceUpdate):
    model_config = ConfigDict(from_attributes=True)

    version: int
    updated_at: datetime


class TripPlanningJobRequest(TripRequest):
    use_saved_preferences: bool = False


class JobCreatedResponse(BaseModel):
    job_id: UUID
    trip_id: UUID
    status: Literal["queued"] = "queued"


class PlanningJobResponse(BaseModel):
    job_id: UUID
    trip_id: UUID
    kind: Literal["generate_trip", "revise_trip"]
    status: Literal["queued", "running", "succeeded", "failed"]
    stage: str
    progress_current: int
    progress_total: int
    progress_percent: int
    progress_message: str
    attempts: int
    result_version: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TripDetailResponse(BaseModel):
    trip_id: UUID
    version: int
    status: str
    plan: TripPlan


class TripSummaryResponse(BaseModel):
    trip_id: UUID
    title: str
    status: Literal["planning", "ready", "failed"]
    current_version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class TripEditOperation(BaseModel):
    type: Literal[
        "delete_attraction",
        "move_attraction",
        "update_visit_duration",
        "replace_attraction",
    ]
    day_index: int = Field(ge=0)
    attraction_index: int = Field(ge=0)
    target_index: int | None = Field(default=None, ge=0)
    visit_duration: int | None = Field(default=None, ge=30, le=480)
    replacement_poi_id: str | None = None

    @model_validator(mode="after")
    def validate_operation_fields(self):
        required_field = {
            "move_attraction": ("target_index", self.target_index),
            "update_visit_duration": ("visit_duration", self.visit_duration),
            "replace_attraction": ("replacement_poi_id", self.replacement_poi_id),
        }.get(self.type)
        if required_field is not None and required_field[1] is None:
            raise ValueError(f"{self.type}需要{required_field[0]}")
        return self


class TripRevisionJobRequest(BaseModel):
    expected_version: int = Field(ge=1)
    operations: list[TripEditOperation] = Field(min_length=1, max_length=20)
