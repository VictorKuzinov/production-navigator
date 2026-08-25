from pydantic import BaseModel, ConfigDict, Field, field_validator


class MaterialBase(BaseModel):
    group_code: str = Field(min_length=1, max_length=50)
    grade_name: str = Field(min_length=1, max_length=100)
    density: float | None = Field(default=None, gt=0)

    @field_validator("grade_name")
    @classmethod
    def reject_blank_grade_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Grade name must contain non-whitespace characters.")
        return value


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    group_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    grade_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    density: float | None = Field(default=None, gt=0)

    @field_validator("group_code", "grade_name", mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null.")
        return value

    @field_validator("grade_name")
    @classmethod
    def reject_blank_grade_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Grade name must contain non-whitespace characters.")
        return value


class MaterialRead(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
