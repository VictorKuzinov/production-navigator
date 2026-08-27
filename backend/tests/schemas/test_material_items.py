import math

import pytest
from pydantic import ValidationError

from app.schemas import MaterialItemCreate, MaterialItemUpdate


def valid_create_data() -> dict[str, object]:
    return {
        "material_id": 10,
        "material_form_code": "BAR_ROUND",
        "dimension_1": 20.0,
        "unit_of_measure": "kg",
    }


@pytest.mark.parametrize("unit", ["kg", "m", "m2", "m3", "l", "pcs"])
def test_create_accepts_each_canonical_unit(unit: str) -> None:
    data = valid_create_data()
    data["unit_of_measure"] = unit

    material_item = MaterialItemCreate(**data)

    assert material_item.unit_of_measure == unit
    assert material_item.dimension_1 == 20.0


def test_create_allows_omitted_or_explicit_null_optional_dimension() -> None:
    omitted_data = valid_create_data()
    omitted_data.pop("dimension_1")
    omitted = MaterialItemCreate(**omitted_data)
    explicit_null = MaterialItemCreate(**(omitted_data | {"dimension_1": None}))

    assert omitted.dimension_1 is None
    assert "dimension_1" not in omitted.model_fields_set
    assert explicit_null.dimension_1 is None
    assert "dimension_1" in explicit_null.model_fields_set


def test_create_accepts_liquid_with_null_dimension() -> None:
    material_item = MaterialItemCreate(
        material_id=10,
        material_form_code="LIQUID_CHEMICAL",
        dimension_1=None,
        unit_of_measure="l",
    )

    assert material_item.dimension_1 is None


def test_create_rejects_non_null_dimension_for_liquid() -> None:
    with pytest.raises(ValidationError):
        MaterialItemCreate(
            material_id=10,
            material_form_code="LIQUID_CHEMICAL",
            dimension_1=1.0,
            unit_of_measure="l",
        )


@pytest.mark.parametrize(
    "dimension",
    [0.0, -0.1, math.nan, math.inf, -math.inf],
)
def test_create_rejects_non_positive_or_non_finite_dimension(
    dimension: float,
) -> None:
    data = valid_create_data()
    data["dimension_1"] = dimension

    with pytest.raises(ValidationError):
        MaterialItemCreate(**data)


@pytest.mark.parametrize(
    "unit",
    ["KG", "кг", " kg", "kg ", "roll", "sheet", ""],
)
def test_create_rejects_non_canonical_unit_without_normalization(
    unit: str,
) -> None:
    data = valid_create_data()
    data["unit_of_measure"] = unit

    with pytest.raises(ValidationError):
        MaterialItemCreate(**data)


@pytest.mark.parametrize(
    "field_name",
    ["material_id", "material_form_code", "unit_of_measure"],
)
def test_create_rejects_null_for_required_fields(field_name: str) -> None:
    data = valid_create_data()
    data[field_name] = None

    with pytest.raises(ValidationError):
        MaterialItemCreate(**data)


def test_empty_update_is_no_op_and_excludes_omitted_fields() -> None:
    update = MaterialItemUpdate()

    assert update.model_fields_set == set()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_distinguishes_explicit_null_dimension_from_omitted() -> None:
    clear = MaterialItemUpdate(dimension_1=None)
    omitted = MaterialItemUpdate(unit_of_measure="m")

    assert clear.model_fields_set == {"dimension_1"}
    assert clear.model_dump(exclude_unset=True) == {"dimension_1": None}
    assert "dimension_1" not in omitted.model_fields_set


@pytest.mark.parametrize(
    "field_name",
    ["material_id", "material_form_code", "unit_of_measure"],
)
def test_update_rejects_null_for_non_nullable_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        MaterialItemUpdate(**{field_name: None})


def test_update_rejects_explicit_liquid_with_non_null_dimension() -> None:
    with pytest.raises(ValidationError):
        MaterialItemUpdate(
            material_form_code="LIQUID_CHEMICAL",
            dimension_1=1.0,
        )


@pytest.mark.parametrize("dimension", [0.0, -1.0, math.inf])
def test_update_rejects_invalid_dimension(dimension: float) -> None:
    with pytest.raises(ValidationError):
        MaterialItemUpdate(dimension_1=dimension)
