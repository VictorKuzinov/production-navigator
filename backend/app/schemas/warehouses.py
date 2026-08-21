from pydantic import BaseModel, ConfigDict, Field, field_validator


class WarehouseBase(BaseModel):
    warehouse_type_code: str = Field(min_length=1, max_length=50)
    total_capacity_cube: float
    max_load_sqm: float | None = None
    temperature_control: bool = False


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    warehouse_type_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    total_capacity_cube: float | None = None
    max_load_sqm: float | None = None
    temperature_control: bool | None = None

    @field_validator(
        "warehouse_type_code",
        "total_capacity_cube",
        "temperature_control",
        mode="before",
    )
    @classmethod
    def reject_null_for_non_nullable_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null.")
        return value


class WarehouseRead(WarehouseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
