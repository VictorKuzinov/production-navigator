import pytest
from pydantic import ValidationError

from app.schemas import TransportCreate, TransportUpdate


def valid_create_data() -> dict[str, object]:
    return {
        "transport_type_code": "LIGHT_COMMERCIAL",
        "transport_scope_code": "REGIONAL",
        "transport_ownership_code": "PNC_OWN_OWNED",
        "payload_tons": 1.5,
    }


def test_create_accepts_valid_transport_and_nullable_defaults() -> None:
    transport = TransportCreate(**valid_create_data())

    assert transport.payload_tons == 1.5
    assert transport.body_volume_cube is None
    assert transport.has_refrigeration is None
    assert transport.quantity == 1


@pytest.mark.parametrize("value", [True, False, None])
def test_create_accepts_all_refrigeration_states(value: bool | None) -> None:
    transport = TransportCreate(
        **valid_create_data(),
        has_refrigeration=value,
    )

    assert transport.has_refrigeration is value


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("payload_tons", 0),
        ("payload_tons", -0.1),
        ("body_volume_cube", 0),
        ("body_volume_cube", -0.1),
        ("quantity", 0),
        ("quantity", -1),
    ],
)
def test_create_rejects_invalid_ranges(
    field_name: str,
    invalid_value: float | int,
) -> None:
    payload = valid_create_data()
    payload[field_name] = invalid_value

    with pytest.raises(ValidationError):
        TransportCreate(**payload)


def test_create_accepts_explicit_null_body_volume() -> None:
    transport = TransportCreate(
        **valid_create_data(),
        body_volume_cube=None,
    )

    assert transport.body_volume_cube is None


def test_empty_update_excludes_all_omitted_fields() -> None:
    update = TransportUpdate()

    assert update.model_fields_set == set()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_distinguishes_explicit_null_from_omitted_nullable_fields() -> None:
    update = TransportUpdate(
        body_volume_cube=None,
        has_refrigeration=None,
    )

    assert update.model_fields_set == {
        "body_volume_cube",
        "has_refrigeration",
    }
    assert update.model_dump(exclude_unset=True) == {
        "body_volume_cube": None,
        "has_refrigeration": None,
    }


def test_update_preserves_explicit_false_refrigeration() -> None:
    update = TransportUpdate(has_refrigeration=False)

    assert "has_refrigeration" in update.model_fields_set
    assert update.model_dump(exclude_unset=True) == {
        "has_refrigeration": False,
    }


@pytest.mark.parametrize(
    "field_name",
    [
        "transport_type_code",
        "transport_scope_code",
        "transport_ownership_code",
        "payload_tons",
        "quantity",
    ],
)
def test_update_rejects_null_for_non_nullable_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        TransportUpdate(**{field_name: None})
