import pytest
from pydantic import ValidationError

from app.schemas import WarehouseUpdate


def test_empty_warehouse_update_excludes_all_omitted_fields() -> None:
    update = WarehouseUpdate()

    assert update.model_fields_set == set()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_warehouse_rejects_null_warehouse_type_code() -> None:
    with pytest.raises(ValidationError):
        WarehouseUpdate(warehouse_type_code=None)


def test_update_warehouse_rejects_null_total_capacity() -> None:
    with pytest.raises(ValidationError):
        WarehouseUpdate(total_capacity_cube=None)


def test_update_warehouse_rejects_null_temperature_control() -> None:
    with pytest.raises(ValidationError):
        WarehouseUpdate(temperature_control=None)


def test_update_warehouse_allows_clearing_max_load() -> None:
    update = WarehouseUpdate(max_load_sqm=None)

    assert "max_load_sqm" in update.model_fields_set
    assert update.model_dump(exclude_unset=True) == {"max_load_sqm": None}


def test_update_warehouse_keeps_supplied_reference_code() -> None:
    update = WarehouseUpdate(warehouse_type_code="UNIVERSAL")

    assert "warehouse_type_code" in update.model_fields_set
    assert update.model_dump(exclude_unset=True) == {
        "warehouse_type_code": "UNIVERSAL"
    }
