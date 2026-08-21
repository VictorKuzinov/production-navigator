from pydantic import BaseModel, ConfigDict, Field


class EquipmentBase(BaseModel):
    equipment_type_code: str = Field(min_length=1, max_length=50)
    model_name: str | None = Field(default=None, max_length=255)
    cnc: bool = False
    axes: int | None = None
    quantity: int = 1
    max_diameter: float | None = None
    working_zone_x: float | None = None
    working_zone_y: float | None = None
    working_zone_z: float | None = None


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    equipment_type_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    model_name: str | None = Field(
        default=None,
        max_length=255
    )
    cnc: bool | None = None
    axes: int | None = None
    quantity: int | None = None
    max_diameter: float | None = None
    working_zone_x: float | None = None
    working_zone_y: float | None = None
    working_zone_z: float | None = None


class EquipmentRead(EquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
    facility_id: int