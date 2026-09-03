from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CertificateType,
    EquipmentType,
    Material,
    MaterialGroup,
    ProcurementCertificateRequirement,
    ProcurementEquipmentRequirement,
    ProcurementMaterialRequirement,
    ProcurementOpportunity,
    ProcurementOpportunityProductType,
    ProcurementOpportunityStatus,
    ProcurementTechnologyRequirement,
    ProductType,
    Region,
    RequirementCollectionState,
    RequirementStrength,
    TechnologyType,
)
from app.repositories import ProcurementOpportunityRepository
from app.schemas.procurement_opportunities import PreparedOpportunityInput


def make_record(
    external_id: str = "repo-1",
    **changes: object,
) -> PreparedOpportunityInput:
    payload: dict[str, object] = {
        "source": "fixture",
        "external_id": external_id,
        "procurement_number": None,
        "title": "Repository opportunity",
        "customer": None,
        "source_url": None,
        "status": "OPEN",
        "procurement_type": None,
        "okpd2_codes": ["25.62.10.000"],
        "product_type_codes": None,
        "price_amount": None,
        "price_currency": None,
        "region_code": None,
        "quantity": None,
        "unit": None,
        "application_deadline": None,
        "execution_deadline": None,
        "material_requirements": None,
        "technology_requirements": None,
        "equipment_requirements": None,
        "dimensional_mass_requirements": None,
        "quality_requirements": None,
        "required_certificates": None,
    }
    payload.update(changes)
    return PreparedOpportunityInput.model_validate(payload)


async def test_repository_creates_and_reads_eager_deterministic_aggregate(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    record = make_record(
        source=" EIS ",
        product_type_codes=[
            reference_rows["other_product_type"],
            reference_rows["product_type"],
        ],
        material_requirements=[
            {
                "material_group_code": reference_rows["other_material_group"],
                "material_id": None,
                "requirement_strength": "PREFERRED",
            },
            {
                "material_group_code": reference_rows["material_group"],
                "material_id": None,
                "requirement_strength": "MANDATORY",
            },
        ],
        technology_requirements=[
            {
                "technology_code": reference_rows["other_technology_type"],
                "requirement_strength": "UNKNOWN",
            },
            {
                "technology_code": reference_rows["technology_type"],
                "requirement_strength": "MANDATORY",
            },
        ],
        equipment_requirements=[
            {
                "equipment_type_code": reference_rows["other_equipment_type"],
                "cnc": False,
                "axes": 3,
                "working_zone_x_mm": "500.000",
                "requirement_strength": "PREFERRED",
            },
            {
                "equipment_type_code": reference_rows["equipment_type"],
                "cnc": None,
                "diameter_mm": "125.000",
                "requirement_strength": "MANDATORY",
            },
        ],
        dimensional_mass_requirements=[
            {"mass_kg": "5.250", "requirement_strength": "UNKNOWN"}
        ],
        quality_requirements=[
            {
                "cmm_required": False,
                "maximum_ra_um": "1.6000",
                "requirement_strength": "PREFERRED",
            }
        ],
        required_certificates=[
            {
                "certificate_type_code": reference_rows["certificate_type"],
                "requirement_strength": "MANDATORY",
                "required_by": "2026-10-01",
            }
        ],
        region_code=reference_rows["region"],
        application_deadline="2026-09-20T09:00:00+05:00",
    )
    repository = ProcurementOpportunityRepository(db_session)

    created = await repository.create_from_canonical(record)
    assert created.id is not None
    assert db_session.in_transaction()
    await db_session.commit()

    loaded = await repository.get_by_identity("eis", "repo-1")
    assert loaded is not None
    assert [item.product_type_code for item in loaded.product_types] == [
        reference_rows["product_type"],
        reference_rows["other_product_type"],
    ]
    assert [item.material_group_code for item in loaded.material_requirements] == [
        reference_rows["other_material_group"],
        reference_rows["material_group"],
    ]
    assert [item.technology_code for item in loaded.technology_requirements] == [
        reference_rows["other_technology_type"],
        reference_rows["technology_type"],
    ]
    assert loaded.application_deadline_at is not None
    assert loaded.application_deadline_date is None
    assert loaded.dimensional_mass_requirements == [
        {
            "length_mm": None,
            "width_mm": None,
            "height_mm": None,
            "diameter_mm": None,
            "mass_kg": "5.250",
            "requirement_strength": "UNKNOWN",
        }
    ]


async def test_repository_flush_does_not_commit_and_rollback_removes_create(
    db_session: AsyncSession,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    created = await repository.create_from_canonical(make_record("rollback"))
    assert created.id is not None

    await db_session.rollback()

    assert await repository.get_by_identity("fixture", "rollback") is None


async def test_json_null_empty_and_nonempty_round_trip_as_distinct_values(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    await repository.create_from_canonical(
        make_record(
            "json-null",
            okpd2_codes=None,
            product_type_codes=[reference_rows["product_type"]],
            dimensional_mass_requirements=None,
            quality_requirements=None,
        )
    )
    await repository.create_from_canonical(
        make_record(
            "json-empty",
            okpd2_codes=[],
            product_type_codes=[reference_rows["product_type"]],
            dimensional_mass_requirements=[],
            quality_requirements=[],
        )
    )
    await repository.create_from_canonical(make_record("json-value"))
    await db_session.commit()

    null_row = await repository.get_by_identity("fixture", "json-null")
    empty_row = await repository.get_by_identity("fixture", "json-empty")
    value_row = await repository.get_by_identity("fixture", "json-value")
    assert null_row is not None and null_row.okpd2_codes is None
    assert empty_row is not None and empty_row.okpd2_codes == []
    assert value_row is not None and value_row.okpd2_codes == ["25.62.10.000"]
    assert null_row.dimensional_mass_requirements is None
    assert empty_row.dimensional_mass_requirements == []


async def test_replace_snapshot_preserves_parent_id_and_replaces_children(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    original = make_record(
        "replace",
        product_type_codes=[reference_rows["product_type"]],
        technology_requirements=[
            {
                "technology_code": reference_rows["technology_type"],
                "requirement_strength": "MANDATORY",
            }
        ],
    )
    opportunity = await repository.create_from_canonical(original)
    await db_session.commit()
    opportunity_id = opportunity.id

    replacement = make_record(
        "replace",
        title="Replacement",
        product_type_codes=[],
        technology_requirements=None,
        equipment_requirements=[
            {
                "equipment_type_code": reference_rows["equipment_type"],
                "requirement_strength": "PREFERRED",
            }
        ],
    )
    await repository.replace_snapshot(opportunity, replacement)
    await db_session.commit()

    loaded = await repository.get_by_identity("fixture", "replace")
    assert loaded is not None
    assert loaded.id == opportunity_id
    assert loaded.title == "Replacement"
    assert loaded.product_type_codes_state == RequirementCollectionState.KNOWN
    assert loaded.product_types == []
    assert loaded.technology_requirements_state == RequirementCollectionState.UNKNOWN
    assert loaded.technology_requirements == []
    assert len(loaded.equipment_requirements) == 1


async def test_db_identity_is_unique_and_external_id_case_is_preserved(
    db_session: AsyncSession,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    upper = await repository.create_from_canonical(make_record("Lot-A"))
    lower = await repository.create_from_canonical(make_record("lot-a"))
    await db_session.commit()
    assert upper.external_id == "Lot-A"
    assert lower.external_id == "lot-a"

    db_session.add(
        ProcurementOpportunity(
            source="fixture",
            external_id="Lot-A",
            title="Duplicate",
            status=ProcurementOpportunityStatus.OPEN,
            product_type_codes_state=RequirementCollectionState.UNKNOWN,
            material_requirements_state=RequirementCollectionState.UNKNOWN,
            technology_requirements_state=RequirementCollectionState.UNKNOWN,
            equipment_requirements_state=RequirementCollectionState.UNKNOWN,
            required_certificates_state=RequirementCollectionState.UNKNOWN,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "INVALID"},
        {"product_type_codes_state": "INVALID"},
        {"price_amount": Decimal("1.00"), "price_currency": None},
        {"price_amount": Decimal("-1.00")},
        {"quantity": Decimal("1.000000"), "unit": None},
        {"quantity": Decimal("0.000000")},
        {
            "application_deadline_date": date(2026, 9, 20),
            "application_deadline_at": datetime(2026, 9, 20, tzinfo=UTC),
        },
    ],
)
async def test_parent_database_checks_reject_invalid_snapshots(
    db_session: AsyncSession,
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "source": "fixture",
        "external_id": f"bad-{len(changes)}-{next(iter(changes))}",
        "title": "Invalid parent",
        "status": ProcurementOpportunityStatus.OPEN,
        "product_type_codes_state": RequirementCollectionState.UNKNOWN,
        "material_requirements_state": RequirementCollectionState.UNKNOWN,
        "technology_requirements_state": RequirementCollectionState.UNKNOWN,
        "equipment_requirements_state": RequirementCollectionState.UNKNOWN,
        "required_certificates_state": RequirementCollectionState.UNKNOWN,
    }
    values.update(changes)
    db_session.add(ProcurementOpportunity(**values))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_material_partial_unique_indexes_reject_both_duplicate_targets(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    opportunity = await repository.create_from_canonical(make_record("partial"))
    await db_session.commit()
    opportunity_id = opportunity.id

    for rows in (
        [
            ProcurementMaterialRequirement(
                opportunity_id=opportunity_id,
                material_group_code=reference_rows["material_group"],
                material_id=None,
                requirement_strength=RequirementStrength.MANDATORY,
            ),
            ProcurementMaterialRequirement(
                opportunity_id=opportunity_id,
                material_group_code=reference_rows["material_group"],
                material_id=None,
                requirement_strength=RequirementStrength.PREFERRED,
            ),
        ],
    ):
        db_session.add_all(rows)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    material = Material(
        group_code=reference_rows["material_group"],
        grade_name="Exact fixture grade",
    )
    db_session.add(material)
    await db_session.commit()
    db_session.add_all(
        [
            ProcurementMaterialRequirement(
                opportunity_id=opportunity_id,
                material_group_code=reference_rows["material_group"],
                material_id=material.id,
                requirement_strength=RequirementStrength.MANDATORY,
            ),
            ProcurementMaterialRequirement(
                opportunity_id=opportunity_id,
                material_group_code=reference_rows["material_group"],
                material_id=material.id,
                requirement_strength=RequirementStrength.UNKNOWN,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    "target",
    [
        "region",
        "product_type",
        "material_group",
        "material",
        "technology",
        "equipment",
        "certificate",
    ],
)
async def test_database_rejects_each_unknown_shared_reference(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    target: str,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    opportunity = await repository.create_from_canonical(
        make_record(f"invalid-reference-{target}")
    )
    await db_session.commit()
    opportunity_id = opportunity.id

    if target == "region":
        loaded = await repository.get_by_identity(
            "fixture",
            f"invalid-reference-{target}",
        )
        assert loaded is not None
        loaded.region_code = "PNC_REG_MISSING"
        invalid_row = loaded
    elif target == "product_type":
        invalid_row = ProcurementOpportunityProductType(
            opportunity_id=opportunity_id,
            product_type_code="MISSING_PRODUCT",
        )
    elif target == "material_group":
        invalid_row = ProcurementMaterialRequirement(
            opportunity_id=opportunity_id,
            material_group_code="MISSING_GROUP",
            requirement_strength=RequirementStrength.MANDATORY,
        )
    elif target == "material":
        invalid_row = ProcurementMaterialRequirement(
            opportunity_id=opportunity_id,
            material_group_code=reference_rows["material_group"],
            material_id=999999,
            requirement_strength=RequirementStrength.MANDATORY,
        )
    elif target == "technology":
        invalid_row = ProcurementTechnologyRequirement(
            opportunity_id=opportunity_id,
            technology_code="MISSING_TECHNOLOGY",
            requirement_strength=RequirementStrength.MANDATORY,
        )
    elif target == "equipment":
        invalid_row = ProcurementEquipmentRequirement(
            opportunity_id=opportunity_id,
            equipment_type_code="MISSING_EQUIPMENT",
            requirement_strength=RequirementStrength.MANDATORY,
        )
    else:
        invalid_row = ProcurementCertificateRequirement(
            opportunity_id=opportunity_id,
            certificate_type_code="PNC_CERT_MISSING",
            requirement_strength=RequirementStrength.MANDATORY,
        )
    db_session.add(invalid_row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.parametrize(
    "kind",
    ["material", "technology", "equipment", "certificate"],
)
async def test_database_rejects_invalid_requirement_strength(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
    kind: str,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    opportunity = await repository.create_from_canonical(
        make_record(f"invalid-strength-{kind}")
    )
    await db_session.commit()
    opportunity_id = opportunity.id

    if kind == "material":
        row = ProcurementMaterialRequirement(
            opportunity_id=opportunity_id,
            material_group_code=reference_rows["material_group"],
            requirement_strength="INVALID",
        )
    elif kind == "technology":
        row = ProcurementTechnologyRequirement(
            opportunity_id=opportunity_id,
            technology_code=reference_rows["technology_type"],
            requirement_strength="INVALID",
        )
    elif kind == "equipment":
        row = ProcurementEquipmentRequirement(
            opportunity_id=opportunity_id,
            equipment_type_code=reference_rows["equipment_type"],
            requirement_strength="INVALID",
        )
    else:
        row = ProcurementCertificateRequirement(
            opportunity_id=opportunity_id,
            certificate_type_code=reference_rows["certificate_type"],
            requirement_strength="INVALID",
        )
    db_session.add(row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_parent_delete_cascades_all_children_and_references_are_restricted(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    material = Material(
        group_code=reference_rows["material_group"],
        grade_name="Lifecycle exact grade",
    )
    db_session.add(material)
    await db_session.commit()
    material_id = material.id
    record = make_record(
        "lifecycle",
        region_code=reference_rows["region"],
        product_type_codes=[reference_rows["product_type"]],
        material_requirements=[
            {
                "material_group_code": reference_rows["material_group"],
                "material_id": material_id,
                "requirement_strength": "MANDATORY",
            },
            {
                "material_group_code": reference_rows["other_material_group"],
                "material_id": None,
                "requirement_strength": "PREFERRED",
            },
        ],
        technology_requirements=[
            {
                "technology_code": reference_rows["technology_type"],
                "requirement_strength": "MANDATORY",
            }
        ],
        equipment_requirements=[
            {
                "equipment_type_code": reference_rows["equipment_type"],
                "requirement_strength": "MANDATORY",
            }
        ],
        required_certificates=[
            {
                "certificate_type_code": reference_rows["certificate_type"],
                "requirement_strength": "MANDATORY",
            }
        ],
    )
    opportunity = await repository.create_from_canonical(record)
    await db_session.commit()
    opportunity_id = opportunity.id

    restricted = (
        (Region, reference_rows["region"]),
        (ProductType, reference_rows["product_type"]),
        (MaterialGroup, reference_rows["material_group"]),
        (TechnologyType, reference_rows["technology_type"]),
        (EquipmentType, reference_rows["equipment_type"]),
        (CertificateType, reference_rows["certificate_type"]),
    )
    for model, code in restricted:
        with pytest.raises(IntegrityError):
            await db_session.execute(delete(model).where(model.code == code))
        await db_session.rollback()

    with pytest.raises(IntegrityError):
        await db_session.execute(delete(Material).where(Material.id == material_id))
    await db_session.rollback()

    await db_session.execute(
        delete(ProcurementOpportunity).where(
            ProcurementOpportunity.id == opportunity_id
        )
    )
    await db_session.commit()
    for child_model in (
        ProcurementOpportunityProductType,
        ProcurementMaterialRequirement,
        ProcurementTechnologyRequirement,
        ProcurementEquipmentRequirement,
        ProcurementCertificateRequirement,
    ):
        children = await db_session.execute(select(child_model))
        assert children.scalars().all() == []
