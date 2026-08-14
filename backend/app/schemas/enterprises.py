from pydantic import BaseModel, ConfigDict, Field


class EnterpriseProfileBase(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    inn: str | None = Field(default=None, min_length=10, max_length=12)
    ogrn: str | None = Field(default=None, min_length=13, max_length=15)
    website: str | None = Field(default=None, max_length=255)
    employees_count: int | None = Field(default=None, ge=0)
    company_size_code: str | None = Field(default=None, max_length=50)
    region_code: str | None = Field(default=None, max_length=50)


class EnterpriseProfileCreate(EnterpriseProfileBase):
    pass


class EnterpriseProfileUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    inn: str | None = Field(default=None, min_length=10, max_length=12)
    ogrn: str | None = Field(default=None, min_length=13, max_length=15)
    website: str | None = Field(default=None, max_length=255)
    employees_count: int | None = Field(default=None, ge=0)
    company_size_code: str | None = Field(default=None, max_length=50)
    region_code: str | None = Field(default=None, max_length=50)


class EnterpriseProfileRead(EnterpriseProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
