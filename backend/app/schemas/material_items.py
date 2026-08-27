from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MaterialUnit = Literal["kg", "m", "m2", "m3", "l", "pcs"]


class MaterialItemBase(BaseModel):
    material_id: int
    material_form_code: str = Field(min_length=1, max_length=50)
    dimension_1: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    unit_of_measure: MaterialUnit

    @model_validator(mode="after")
    def validate_dimension_for_form(self) -> Self:
        if (
            self.material_form_code == "LIQUID_CHEMICAL"
            and self.dimension_1 is not None
        ):
            raise ValueError("dimension_1 must be null for LIQUID_CHEMICAL.")
        return self


class MaterialItemCreate(MaterialItemBase):
    pass


class MaterialItemUpdate(BaseModel):
    material_id: int | None = None
    material_form_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    dimension_1: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    unit_of_measure: MaterialUnit | None = None

    @field_validator(
        "material_id",
        "material_form_code",
        "unit_of_measure",
        mode="before",
    )
    @classmethod
    def reject_null_for_non_nullable_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null.")
        return value

    @model_validator(mode="after")
    def reject_non_null_dimension_for_explicit_liquid_form(self) -> Self:
        if (
            self.material_form_code == "LIQUID_CHEMICAL"
            and "dimension_1" in self.model_fields_set
            and self.dimension_1 is not None
        ):
            raise ValueError("dimension_1 must be null for LIQUID_CHEMICAL.")
        return self


class MaterialItemRead(MaterialItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
