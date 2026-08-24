import pytest
from pydantic import ValidationError

from app.schemas import LiftingEquipmentCreate, LiftingEquipmentUpdate


@pytest.mark.parametrize(
    ("facility_id", "warehouse_id"),
    [
        (10, None),
        (None, 20),
        (10, 20),
        (None, None),
    ],
)
def test_create_accepts_all_documented_location_combinations(
    facility_id: int | None,
    warehouse_id: int | None,
) -> None:
    lifting_equipment = LiftingEquipmentCreate(
        crane_type_code="OVERHEAD_CRANE",
        facility_id=facility_id,
        warehouse_id=warehouse_id,
        load_capacity_tons=5.0,
    )

    assert lifting_equipment.facility_id == facility_id
    assert lifting_equipment.warehouse_id == warehouse_id
    assert lifting_equipment.max_lift_height is None
    assert lifting_equipment.quantity == 1


def test_empty_update_excludes_all_omitted_fields() -> None:
    update = LiftingEquipmentUpdate()

    assert update.model_fields_set == set()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_can_explicitly_clear_all_nullable_fields() -> None:
    update = LiftingEquipmentUpdate(
        facility_id=None,
        warehouse_id=None,
        max_lift_height=None,
    )

    assert update.model_fields_set == {
        "facility_id",
        "warehouse_id",
        "max_lift_height",
    }
    assert update.model_dump(exclude_unset=True) == {
        "facility_id": None,
        "warehouse_id": None,
        "max_lift_height": None,
    }


@pytest.mark.parametrize(
    "field_name",
    ["crane_type_code", "load_capacity_tons", "quantity"],
)
def test_update_rejects_null_for_non_nullable_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        LiftingEquipmentUpdate(**{field_name: None})


@pytest.mark.parametrize(
    "field_name",
    ["crane_type_code", "load_capacity_tons", "quantity"],
)
def test_create_rejects_explicit_null_for_non_nullable_fields(
    field_name: str,
) -> None:
    payload = {
        "crane_type_code": "OVERHEAD_CRANE",
        "load_capacity_tons": 5.0,
        "quantity": 1,
    }
    payload[field_name] = None

    with pytest.raises(ValidationError):
        LiftingEquipmentCreate(**payload)
