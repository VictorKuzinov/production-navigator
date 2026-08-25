from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransportBase(BaseModel):
    transport_type_code: str = Field(min_length=1, max_length=50)
    transport_scope_code: str = Field(min_length=1, max_length=50)
    transport_ownership_code: str = Field(min_length=1, max_length=50)
    payload_tons: float = Field(gt=0)
    body_volume_cube: float | None = Field(default=None, gt=0)
    has_refrigeration: bool | None = None
    quantity: int = Field(default=1, ge=1)


class TransportCreate(TransportBase):
    pass


class TransportUpdate(BaseModel):
    transport_type_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    transport_scope_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    transport_ownership_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    payload_tons: float | None = Field(default=None, gt=0)
    body_volume_cube: float | None = Field(default=None, gt=0)
    has_refrigeration: bool | None = None
    quantity: int | None = Field(default=None, ge=1)

    @field_validator(
        "transport_type_code",
        "transport_scope_code",
        "transport_ownership_code",
        "payload_tons",
        "quantity",
        mode="before",
    )
    @classmethod
    def reject_null_for_non_nullable_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null.")
        return value


class TransportRead(TransportBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
