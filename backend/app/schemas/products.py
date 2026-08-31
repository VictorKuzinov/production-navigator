from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    product_type_code: str = Field(min_length=1, max_length=50)
    material_item_id: int
    sku_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    weight_net: float = Field(gt=0, allow_inf_nan=False)
    required_it_grade: int | None = Field(default=None, ge=1, le=18)
    required_ra: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )

    @field_validator("sku_code", "name", mode="before")
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    product_type_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    material_item_id: int | None = None
    sku_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    weight_net: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    required_it_grade: int | None = Field(default=None, ge=1, le=18)
    required_ra: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )

    @field_validator(
        "product_type_code",
        "material_item_id",
        "weight_net",
        mode="before",
    )
    @classmethod
    def reject_null_for_non_nullable_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null.")
        return value

    @field_validator("sku_code", "name", mode="before")
    @classmethod
    def trim_non_nullable_text(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null.")
        if isinstance(value, str):
            return value.strip()
        return value


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
