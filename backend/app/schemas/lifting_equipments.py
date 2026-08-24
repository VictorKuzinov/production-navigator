from pydantic import BaseModel, ConfigDict, Field, field_validator


class LiftingEquipmentBase(BaseModel):
    crane_type_code: str = Field(min_length=1, max_length=50)
    facility_id: int | None = None
    warehouse_id: int | None = None
    load_capacity_tons: float
    max_lift_height: float | None = None
    quantity: int = 1


class LiftingEquipmentCreate(LiftingEquipmentBase):
    pass


class LiftingEquipmentUpdate(BaseModel):
    crane_type_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    facility_id: int | None = None
    warehouse_id: int | None = None
    load_capacity_tons: float | None = None
    max_lift_height: float | None = None
    quantity: int | None = None

    @field_validator(
        "crane_type_code",
        "load_capacity_tons",
        "quantity",
        mode="before",
    )
    @classmethod
    def reject_null_for_non_nullable_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null.")
        return value


class LiftingEquipmentRead(LiftingEquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
