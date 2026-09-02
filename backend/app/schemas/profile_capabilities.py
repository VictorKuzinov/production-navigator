from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.profile_capabilities import (
    CapabilityState,
    ProfileSectionCode,
    ProfileSectionState,
)


class CapabilityStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: CapabilityState


class ProfileTechnologyCapabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: int
    technology_code: str
    state: CapabilityState


class ProfileMaterialCapabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: int
    material_group_code: str | None
    material_id: int | None
    state: CapabilityState


class ProfileSectionCompletenessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: int
    section_code: ProfileSectionCode
    state: ProfileSectionState
    confirmed_at: datetime | None
    confirmed_by: str | None

    @field_validator("confirmed_at", mode="before")
    @classmethod
    def normalize_server_timestamp_to_utc(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


MutableProfileSectionState = Literal[
    ProfileSectionState.PARTIAL,
    ProfileSectionState.UNKNOWN,
]


class ProfileSectionStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: MutableProfileSectionState


class ProfileSectionConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    confirmed_by: str = Field(min_length=1, max_length=128)

    @field_validator("confirmed_by")
    @classmethod
    def reject_blank_confirmer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Confirmer must contain non-whitespace characters.")
        return value
