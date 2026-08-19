from pydantic import BaseModel, ConfigDict, Field


class ProductionFacilityBase(BaseModel):
    facility_name: str = Field(min_length=1, max_length=255)
    total_area: float = Field(ge=0)
    available_area: float = Field(ge=0)
    power_capacity: float | None = Field(default=None, ge=0)
    gas_supply: bool = False
    compressed_air: bool = False
    water_supply: bool = False
    steam_supply: bool = False


class ProductionFacilityCreate(ProductionFacilityBase):
    pass


class ProductionFacilityUpdate(BaseModel):
    facility_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    total_area: float | None = Field(default=None, ge=0)
    available_area: float | None = Field(default=None, ge=0)
    power_capacity: float | None = Field(default=None, ge=0)
    gas_supply: bool | None = None
    compressed_air: bool | None = None
    water_supply: bool | None = None
    steam_supply: bool | None = None


class ProductionFacilityRead(ProductionFacilityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int