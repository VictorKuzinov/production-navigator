import math
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas import ProductCreate, ProductRead, ProductUpdate


def valid_create_data() -> dict[str, object]:
    return {
        "product_type_code": "FINISHED_GOOD",
        "material_item_id": 10,
        "sku_code": "Case-Sensitive-SKU",
        "name": "Тестовое изделие",
        "weight_net": 12.5,
        "required_it_grade": 8,
        "required_ra": 1.6,
    }


def test_create_trims_text_and_preserves_case() -> None:
    data = valid_create_data()
    data["sku_code"] = "  Case-Sensitive-SKU  "
    data["name"] = "  Тестовое изделие  "

    product = ProductCreate(**data)

    assert product.sku_code == "Case-Sensitive-SKU"
    assert product.name == "Тестовое изделие"


def test_create_applies_length_limits_after_trim() -> None:
    data = valid_create_data()
    data["sku_code"] = f"  {'S' * 100}  "
    data["name"] = f"  {'N' * 255}  "

    product = ProductCreate(**data)

    assert product.sku_code == "S" * 100
    assert product.name == "N" * 255


@pytest.mark.parametrize("field_name", ["sku_code", "name"])
@pytest.mark.parametrize("value", ["", "   ", "\t\r\n"])
def test_create_rejects_blank_text(field_name: str, value: str) -> None:
    data = valid_create_data()
    data[field_name] = value

    with pytest.raises(ValidationError):
        ProductCreate(**data)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("sku_code", "S" * 101),
        ("name", "N" * 256),
    ],
)
def test_create_rejects_text_over_orm_length(
    field_name: str,
    value: str,
) -> None:
    data = valid_create_data()
    data[field_name] = value

    with pytest.raises(ValidationError):
        ProductCreate(**data)


@pytest.mark.parametrize(
    "weight_net",
    [0.0, -0.1, math.nan, math.inf, -math.inf],
)
def test_create_rejects_non_positive_or_non_finite_weight(
    weight_net: float,
) -> None:
    data = valid_create_data()
    data["weight_net"] = weight_net

    with pytest.raises(ValidationError):
        ProductCreate(**data)


@pytest.mark.parametrize(
    "required_ra",
    [0.0, -0.1, math.nan, math.inf, -math.inf],
)
def test_create_rejects_non_positive_or_non_finite_required_ra(
    required_ra: float,
) -> None:
    data = valid_create_data()
    data["required_ra"] = required_ra

    with pytest.raises(ValidationError):
        ProductCreate(**data)


@pytest.mark.parametrize("required_it_grade", [0, -1, 19])
def test_create_rejects_it_grade_outside_mvp_subset(
    required_it_grade: int,
) -> None:
    data = valid_create_data()
    data["required_it_grade"] = required_it_grade

    with pytest.raises(ValidationError):
        ProductCreate(**data)


def test_create_accepts_it_boundaries_and_nullable_quality_fields() -> None:
    low = ProductCreate(**(valid_create_data() | {"required_it_grade": 1}))
    high = ProductCreate(**(valid_create_data() | {"required_it_grade": 18}))
    omitted_data = valid_create_data()
    omitted_data.pop("required_it_grade")
    omitted_data.pop("required_ra")
    omitted = ProductCreate(**omitted_data)
    explicit_null = ProductCreate(
        **(
            omitted_data
            | {
                "required_it_grade": None,
                "required_ra": None,
            }
        )
    )

    assert low.required_it_grade == 1
    assert high.required_it_grade == 18
    assert omitted.required_it_grade is None
    assert omitted.required_ra is None
    assert "required_it_grade" not in omitted.model_fields_set
    assert explicit_null.model_fields_set >= {
        "required_it_grade",
        "required_ra",
    }


def test_empty_update_is_no_op_and_excludes_omitted_fields() -> None:
    update = ProductUpdate()

    assert update.model_fields_set == set()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_trims_text_preserves_case_and_tracks_presence() -> None:
    update = ProductUpdate(
        sku_code="  Mixed-Case-SKU  ",
        name="  Новое имя  ",
    )

    assert update.sku_code == "Mixed-Case-SKU"
    assert update.name == "Новое имя"
    assert update.model_fields_set == {"sku_code", "name"}


def test_update_distinguishes_explicit_null_quality_from_omitted() -> None:
    clear = ProductUpdate(required_it_grade=None, required_ra=None)
    omitted = ProductUpdate(name="Изделие")

    assert clear.model_fields_set == {"required_it_grade", "required_ra"}
    assert clear.model_dump(exclude_unset=True) == {
        "required_it_grade": None,
        "required_ra": None,
    }
    assert "required_it_grade" not in omitted.model_fields_set
    assert "required_ra" not in omitted.model_fields_set


@pytest.mark.parametrize(
    "field_name",
    [
        "product_type_code",
        "material_item_id",
        "sku_code",
        "name",
        "weight_net",
    ],
)
def test_update_rejects_null_for_non_nullable_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        ProductUpdate(**{field_name: None})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("weight_net", 0),
        ("weight_net", -1),
        ("weight_net", math.inf),
        ("required_it_grade", 0),
        ("required_it_grade", 19),
        ("required_ra", 0),
        ("required_ra", -1),
        ("required_ra", math.inf),
        ("sku_code", "   "),
        ("name", "   "),
    ],
)
def test_update_rejects_invalid_business_value(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        ProductUpdate(**{field_name: value})


def test_read_uses_attributes_and_exposes_profile_id() -> None:
    product = ProductRead.model_validate(
        SimpleNamespace(
            id=7,
            profile_id=3,
            **valid_create_data(),
        )
    )

    assert product.id == 7
    assert product.profile_id == 3
    assert product.sku_code == "Case-Sensitive-SKU"
