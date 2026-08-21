import pytest
from pydantic import ValidationError

from app.schemas import ProductionFacilityCreate, ProductionFacilityUpdate


def test_facility_create_applies_utility_defaults() -> None:
    facility = ProductionFacilityCreate(
        facility_name="Test facility",
        total_area=200.0,
        available_area=80.0,
    )

    assert facility.power_capacity is None
    assert facility.gas_supply is False
    assert facility.compressed_air is False
    assert facility.water_supply is False
    assert facility.steam_supply is False


def test_facility_schema_rejects_negative_capacity_values() -> None:
    invalid_payloads = [
        {"total_area": -1.0, "available_area": 0.0},
        {"total_area": 1.0, "available_area": -1.0},
        {"total_area": 1.0, "available_area": 0.0, "power_capacity": -1.0},
    ]

    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            ProductionFacilityCreate(
                facility_name="Test facility",
                **payload,
            )


def test_facility_update_excludes_omitted_fields() -> None:
    update = ProductionFacilityUpdate(available_area=75.0)

    assert update.model_fields_set == {"available_area"}
    assert update.model_dump(exclude_unset=True) == {"available_area": 75.0}
