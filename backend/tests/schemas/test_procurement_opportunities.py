from copy import deepcopy
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.models import (
    ProcurementOpportunityStatus,
    RequirementCollectionState,
    RequirementStrength,
)
from app.schemas.procurement_opportunities import (
    PreparedOpportunityDocument,
    PreparedOpportunityInput,
    canonical_payload,
    canonical_payload_json,
)

SIGNAL_FIELDS = (
    "okpd2_codes",
    "product_type_codes",
    "material_requirements",
    "technology_requirements",
    "equipment_requirements",
    "dimensional_mass_requirements",
    "quality_requirements",
    "required_certificates",
)


def opportunity_payload() -> dict[str, object]:
    return {
        "source": " EIS ",
        "external_id": " Lot-A ",
        "procurement_number": " 42 ",
        "title": " Test opportunity ",
        "customer": " Customer ",
        "source_url": " https://example.test/opportunity/42 ",
        "status": "OPEN",
        "procurement_type": "44-fz",
        "okpd2_codes": ["25.62.10.000"],
        "product_type_codes": None,
        "price_amount": "100.00",
        "price_currency": "RUB",
        "region_code": "PNC_REG_66",
        "quantity": "2.000000",
        "unit": "pcs",
        "application_deadline": "2026-09-20T09:00:00+05:00",
        "execution_deadline": "2026-11-30",
        "material_requirements": [],
        "technology_requirements": [],
        "equipment_requirements": [],
        "dimensional_mass_requirements": [],
        "quality_requirements": [],
        "required_certificates": [],
    }


def test_enums_have_exact_approved_values() -> None:
    assert [item.value for item in ProcurementOpportunityStatus] == [
        "OPEN",
        "CLOSED",
        "CANCELLED",
        "AWARDED",
        "UNKNOWN",
    ]
    assert [item.value for item in RequirementStrength] == [
        "MANDATORY",
        "PREFERRED",
        "UNKNOWN",
    ]
    assert [item.value for item in RequirementCollectionState] == [
        "UNKNOWN",
        "KNOWN",
    ]


def test_document_accepts_any_nonempty_batch_and_rejects_empty() -> None:
    item = opportunity_payload()
    one = PreparedOpportunityDocument.model_validate({"opportunities": [item]})
    three = PreparedOpportunityDocument.model_validate(
        {"opportunities": [item, item, item]}
    )
    assert len(one.opportunities) == 1
    assert len(three.opportunities) == 3

    with pytest.raises(ValidationError):
        PreparedOpportunityDocument.model_validate({"opportunities": []})


def test_identity_and_text_are_canonicalized_without_external_id_case_loss() -> None:
    record = PreparedOpportunityInput.model_validate(opportunity_payload())

    assert record.source == "eis"
    assert record.external_id == "Lot-A"
    assert record.title == "Test opportunity"
    assert record.customer == "Customer"
    assert record.procurement_number == "42"
    assert record.application_deadline == datetime(
        2026,
        9,
        20,
        4,
        tzinfo=UTC,
    )
    assert record.execution_deadline == date(2026, 11, 30)


@pytest.mark.parametrize("field", SIGNAL_FIELDS)
def test_each_structured_signal_key_is_required(field: str) -> None:
    payload = opportunity_payload()
    payload.pop(field)
    with pytest.raises(ValidationError):
        PreparedOpportunityInput.model_validate(payload)


@pytest.mark.parametrize("field", SIGNAL_FIELDS)
def test_each_structured_signal_can_independently_satisfy_signal_invariant(
    field: str,
) -> None:
    payload = opportunity_payload()
    for signal in SIGNAL_FIELDS:
        payload[signal] = None
    examples: dict[str, object] = {
        "okpd2_codes": ["25.62.10.000"],
        "product_type_codes": ["FINISHED_GOOD"],
        "material_requirements": [
            {
                "material_group_code": "STEEL_CARBON",
                "material_id": None,
                "requirement_strength": "MANDATORY",
            }
        ],
        "technology_requirements": [
            {
                "technology_code": "MACHINING",
                "requirement_strength": "PREFERRED",
            }
        ],
        "equipment_requirements": [
            {
                "equipment_type_code": "TURNING",
                "requirement_strength": "UNKNOWN",
            }
        ],
        "dimensional_mass_requirements": [
            {
                "mass_kg": "1.000",
                "requirement_strength": "MANDATORY",
            }
        ],
        "quality_requirements": [
            {
                "measuring_capability_required": False,
                "requirement_strength": "PREFERRED",
            }
        ],
        "required_certificates": [
            {
                "certificate_type_code": "PNC_CERT_ISO9001",
                "requirement_strength": "MANDATORY",
            }
        ],
    }
    payload[field] = examples[field]

    assert PreparedOpportunityInput.model_validate(payload)


@pytest.mark.parametrize("empty_value", [None, []])
def test_all_unknown_or_empty_signals_are_rejected(empty_value: object) -> None:
    payload = opportunity_payload()
    for field in SIGNAL_FIELDS:
        payload[field] = empty_value
    with pytest.raises(ValidationError, match="structured signal"):
        PreparedOpportunityInput.model_validate(payload)


@pytest.mark.parametrize(
    ("changes", "valid"),
    [
        ({"price_amount": None, "price_currency": None}, True),
        ({"price_amount": None, "price_currency": "RUB"}, True),
        ({"price_amount": "0.00", "price_currency": "RUB"}, True),
        ({"price_amount": "1.00", "price_currency": None}, False),
        ({"quantity": None, "unit": None}, True),
        ({"quantity": None, "unit": "pcs"}, True),
        ({"quantity": "1.000000", "unit": "pcs"}, True),
        ({"quantity": "1.000000", "unit": None}, False),
    ],
)
def test_one_directional_price_and_quantity_invariants(
    changes: dict[str, object],
    valid: bool,
) -> None:
    payload = opportunity_payload() | changes
    if valid:
        assert PreparedOpportunityInput.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            PreparedOpportunityInput.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price_amount", -1),
        ("price_amount", "1.001"),
        ("price_amount", "NaN"),
        ("price_amount", "Infinity"),
        ("quantity", "0.000000"),
        ("quantity", "1.0000001"),
        ("quantity", 1),
    ],
)
def test_decimal_shape_precision_and_finiteness_are_strict(
    field: str,
    value: object,
) -> None:
    payload = opportunity_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        PreparedOpportunityInput.model_validate(payload)


def test_deadlines_preserve_date_and_require_timezone_for_datetime() -> None:
    payload = opportunity_payload()
    payload["application_deadline"] = "2026-09-20"
    payload["execution_deadline"] = "2026-09-20T10:00:00Z"
    record = PreparedOpportunityInput.model_validate(payload)
    assert type(record.application_deadline) is date
    assert record.execution_deadline == datetime(2026, 9, 20, 10, tzinfo=UTC)

    payload["execution_deadline"] = "2026-09-20T10:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        PreparedOpportunityInput.model_validate(payload)


@pytest.mark.parametrize(
    "field", ["dimensional_mass_requirements", "quality_requirements"]
)
def test_summary_blocks_require_domain_values_and_have_maximum_one_item(
    field: str,
) -> None:
    payload = opportunity_payload()
    empty_block = {"requirement_strength": "MANDATORY"}
    payload[field] = [empty_block]
    with pytest.raises(ValidationError, match="domain value"):
        PreparedOpportunityInput.model_validate(payload)

    valid_block = (
        {"length_mm": "1.000", "requirement_strength": "MANDATORY"}
        if field == "dimensional_mass_requirements"
        else {"cmm_required": False, "requirement_strength": "MANDATORY"}
    )
    payload[field] = [valid_block, valid_block]
    with pytest.raises(ValidationError):
        PreparedOpportunityInput.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "items"),
    [
        ("okpd2_codes", ["25.62.10.000", "25.62.10.000"]),
        ("product_type_codes", ["FINISHED_GOOD", "FINISHED_GOOD"]),
        (
            "technology_requirements",
            [
                {"technology_code": "MACHINING", "requirement_strength": "UNKNOWN"},
                {"technology_code": "MACHINING", "requirement_strength": "MANDATORY"},
            ],
        ),
        (
            "equipment_requirements",
            [
                {"equipment_type_code": "TURNING", "requirement_strength": "UNKNOWN"},
                {"equipment_type_code": "TURNING", "requirement_strength": "MANDATORY"},
            ],
        ),
        (
            "required_certificates",
            [
                {
                    "certificate_type_code": "PNC_CERT_ISO9001",
                    "requirement_strength": "UNKNOWN",
                },
                {
                    "certificate_type_code": "PNC_CERT_ISO9001",
                    "requirement_strength": "MANDATORY",
                },
            ],
        ),
    ],
)
def test_duplicate_semantic_targets_are_rejected(
    field: str,
    items: list[object],
) -> None:
    payload = opportunity_payload()
    payload[field] = items
    with pytest.raises(ValidationError, match="Duplicate"):
        PreparedOpportunityInput.model_validate(payload)


def test_material_duplicate_target_uses_group_for_generic_and_id_for_exact() -> None:
    payload = opportunity_payload()
    payload["material_requirements"] = [
        {
            "material_group_code": "STEEL_CARBON",
            "material_id": 7,
            "requirement_strength": "UNKNOWN",
        },
        {
            "material_group_code": "STEEL_ALLOY",
            "material_id": 7,
            "requirement_strength": "MANDATORY",
        },
    ]
    with pytest.raises(ValidationError, match="Duplicate"):
        PreparedOpportunityInput.model_validate(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        {"source": "не-ascii"},
        {"source": "bad source"},
        {"external_id": "   "},
        {"title": "\u2003"},
        {"customer": "   "},
        {"price_currency": "rub"},
        {"region_code": "bad code"},
        {"okpd2_codes": ["25.62"]},
        {"status": "DRAFT"},
        {"unexpected": True},
    ],
)
def test_invalid_codes_enums_blank_and_extra_fields_are_rejected(
    mutation: dict[str, object],
) -> None:
    payload = opportunity_payload() | mutation
    with pytest.raises(ValidationError):
        PreparedOpportunityInput.model_validate(payload)


def test_canonical_payload_is_order_insensitive_and_fixed_scale() -> None:
    payload = opportunity_payload()
    payload["okpd2_codes"] = ["28.41.20.000", "25.62.10.000"]
    payload["technology_requirements"] = [
        {"technology_code": "CONTROL", "requirement_strength": "PREFERRED"},
        {"technology_code": "MACHINING", "requirement_strength": "MANDATORY"},
    ]
    first = PreparedOpportunityInput.model_validate(payload)
    reversed_payload = deepcopy(payload)
    reversed_payload["okpd2_codes"] = list(reversed(payload["okpd2_codes"]))
    reversed_payload["technology_requirements"] = list(
        reversed(payload["technology_requirements"])
    )
    second = PreparedOpportunityInput.model_validate(reversed_payload)

    assert canonical_payload_json(first) == canonical_payload_json(second)
    projected = canonical_payload(first)
    assert projected["price_amount"] == "100.00"
    assert projected["quantity"] == "2.000000"
    assert projected["application_deadline"] == "2026-09-20T04:00:00Z"
