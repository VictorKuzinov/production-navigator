import pytest
from pydantic import ValidationError

from app.schemas import EnterpriseProfileCreate, EnterpriseProfileUpdate


def test_enterprise_create_preserves_optional_fields() -> None:
    profile = EnterpriseProfileCreate(
        company_name="Test enterprise",
        inn="6671000000",
        ogrn="1069600000000",
        website="https://example.test",
        employees_count=20,
        company_size_code="PNC_SIZE_SMALL",
        region_code="PNC_REG_66",
    )

    assert profile.company_name == "Test enterprise"
    assert profile.website == "https://example.test"
    assert profile.employees_count == 20
    assert profile.company_size_code == "PNC_SIZE_SMALL"
    assert profile.region_code == "PNC_REG_66"


def test_enterprise_schema_rejects_negative_employee_count() -> None:
    with pytest.raises(ValidationError):
        EnterpriseProfileCreate(
            company_name="Test enterprise",
            employees_count=-1,
        )


def test_enterprise_update_distinguishes_omitted_and_explicit_nullable_field() -> None:
    empty_update = EnterpriseProfileUpdate()
    clear_website = EnterpriseProfileUpdate(website=None)

    assert empty_update.model_dump(exclude_unset=True) == {}
    assert "website" in clear_website.model_fields_set
    assert clear_website.model_dump(exclude_unset=True) == {"website": None}
