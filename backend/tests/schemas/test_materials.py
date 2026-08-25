import pytest
from pydantic import ValidationError

from app.schemas import MaterialCreate, MaterialUpdate


def test_create_accepts_valid_material_and_preserves_grade_name() -> None:
    material = MaterialCreate(
        group_code="STEEL_STAINLESS",
        grade_name=" 12Х18Н10Т ",
        density=7900.0,
    )

    assert material.group_code == "STEEL_STAINLESS"
    assert material.grade_name == " 12Х18Н10Т "
    assert material.density == 7900.0


def test_create_allows_omitted_density() -> None:
    material = MaterialCreate(
        group_code="STEEL_CARBON",
        grade_name="Сталь 45",
    )

    assert material.density is None
    assert "density" not in material.model_fields_set


def test_create_allows_explicit_null_density() -> None:
    material = MaterialCreate(
        group_code="STEEL_CARBON",
        grade_name="Сталь 20",
        density=None,
    )

    assert material.density is None
    assert "density" in material.model_fields_set


@pytest.mark.parametrize("field_name", ["group_code", "grade_name"])
def test_create_rejects_null_for_required_fields(field_name: str) -> None:
    payload = {
        "group_code": "STEEL_CARBON",
        "grade_name": "Сталь 20",
    }
    payload[field_name] = None

    with pytest.raises(ValidationError):
        MaterialCreate(**payload)


@pytest.mark.parametrize("density", [0, -1])
def test_create_rejects_non_positive_density(density: float) -> None:
    with pytest.raises(ValidationError):
        MaterialCreate(
            group_code="STEEL_CARBON",
            grade_name="Сталь 3",
            density=density,
        )


@pytest.mark.parametrize("grade_name", ["", "   "])
def test_create_rejects_empty_or_whitespace_grade_name(
    grade_name: str,
) -> None:
    with pytest.raises(ValidationError):
        MaterialCreate(
            group_code="STEEL_CARBON",
            grade_name=grade_name,
        )


def test_empty_update_is_no_op_and_excludes_omitted_fields() -> None:
    update = MaterialUpdate()

    assert update.model_fields_set == set()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_distinguishes_explicit_null_density_from_omitted() -> None:
    clear_update = MaterialUpdate(density=None)
    grade_update = MaterialUpdate(grade_name="Сталь 40Х")

    assert clear_update.model_fields_set == {"density"}
    assert clear_update.model_dump(exclude_unset=True) == {"density": None}
    assert "density" not in grade_update.model_fields_set


def test_update_accepts_positive_density() -> None:
    update = MaterialUpdate(density=0.1)

    assert update.density == 0.1


@pytest.mark.parametrize("field_name", ["group_code", "grade_name"])
def test_update_rejects_null_for_non_nullable_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        MaterialUpdate(**{field_name: None})


@pytest.mark.parametrize("grade_name", ["", "\t\n"])
def test_update_rejects_empty_or_whitespace_grade_name(
    grade_name: str,
) -> None:
    with pytest.raises(ValidationError):
        MaterialUpdate(grade_name=grade_name)


@pytest.mark.parametrize("density", [0, -0.1])
def test_update_rejects_non_positive_density(density: float) -> None:
    with pytest.raises(ValidationError):
        MaterialUpdate(density=density)
