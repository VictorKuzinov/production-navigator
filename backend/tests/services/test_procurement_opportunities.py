from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ProcurementOpportunityBatchConflictError,
    ProcurementOpportunityReferenceError,
)
from app.models import Material
from app.repositories import (
    MaterialRepository,
    ProcurementOpportunityRepository,
    ReferenceRepository,
)
from app.schemas.procurement_opportunities import PreparedOpportunityInput
from app.services.procurement_opportunities import (
    ProcurementOpportunityIngestionService,
)


def payload(external_id: str = "service-1", **changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "source": "fixture",
        "external_id": external_id,
        "procurement_number": None,
        "title": "Service opportunity",
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
    values.update(changes)
    return values


def record(
    external_id: str = "service-1", **changes: object
) -> PreparedOpportunityInput:
    return PreparedOpportunityInput.model_validate(payload(external_id, **changes))


def build_service(
    db_session: AsyncSession,
    repository: ProcurementOpportunityRepository | None = None,
) -> ProcurementOpportunityIngestionService:
    return ProcurementOpportunityIngestionService(
        session=db_session,
        opportunity_repository=repository
        or ProcurementOpportunityRepository(db_session),
        reference_repository=ReferenceRepository(db_session),
        material_repository=MaterialRepository(db_session),
    )


async def test_create_noop_and_update_keep_identity_and_exact_counters(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    service = build_service(db_session, repository)
    original = record(
        source=" EIS ",
        product_type_codes=[
            reference_rows["other_product_type"],
            reference_rows["product_type"],
        ],
        technology_requirements=[
            {
                "technology_code": reference_rows["other_technology_type"],
                "requirement_strength": "PREFERRED",
            },
            {
                "technology_code": reference_rows["technology_type"],
                "requirement_strength": "MANDATORY",
            },
        ],
        application_deadline="2026-09-20T09:00:00+05:00",
    )

    first = await service.ingest_batch([original])
    stored = await repository.get_by_identity("eis", "service-1")
    assert stored is not None
    original_id = stored.id
    assert first.model_dump() == {
        "received_rows": 1,
        "unique_identities": 1,
        "created": 1,
        "updated": 0,
        "unchanged": 0,
        "duplicate_rows": 0,
    }

    reordered = record(
        source="eis",
        product_type_codes=list(reversed(original.product_type_codes or [])),
        technology_requirements=list(reversed(original.technology_requirements or [])),
        application_deadline="2026-09-20T04:00:00Z",
    )
    second = await service.ingest_batch([reordered])
    assert second.created == 0
    assert second.updated == 0
    assert second.unchanged == 1

    changed = record(
        source="eis",
        title="Changed snapshot",
        product_type_codes=[],
        technology_requirements=None,
        quality_requirements=[
            {
                "cmm_required": False,
                "requirement_strength": "UNKNOWN",
            }
        ],
        application_deadline="2026-09-20T04:00:00Z",
    )
    third = await service.ingest_batch([changed])
    refreshed = await repository.get_by_identity("eis", "service-1")
    assert refreshed is not None
    assert third.updated == 1
    assert refreshed.id == original_id
    assert refreshed.title == "Changed snapshot"
    assert refreshed.product_types == []
    assert refreshed.technology_requirements == []


async def test_equal_same_batch_duplicates_collapse_with_reordered_arrays(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    first_payload = payload(
        "duplicate",
        okpd2_codes=["28.41.20.000", "25.62.10.000"],
        product_type_codes=[
            reference_rows["product_type"],
            reference_rows["other_product_type"],
        ],
    )
    second_payload = deepcopy(first_payload)
    second_payload["source"] = " FIXTURE "
    second_payload["okpd2_codes"] = list(reversed(first_payload["okpd2_codes"]))
    second_payload["product_type_codes"] = list(
        reversed(first_payload["product_type_codes"])
    )
    records = [
        PreparedOpportunityInput.model_validate(first_payload),
        PreparedOpportunityInput.model_validate(second_payload),
    ]

    result = await build_service(db_session).ingest_batch(records)

    assert result.received_rows == 2
    assert result.unique_identities == 1
    assert result.created == 1
    assert result.duplicate_rows == 1


async def test_conflicting_batch_fails_before_any_database_operation() -> None:
    session = AsyncMock()
    opportunity_repository = AsyncMock()
    reference_repository = AsyncMock()
    material_repository = AsyncMock()
    service = ProcurementOpportunityIngestionService(
        session=session,
        opportunity_repository=opportunity_repository,
        reference_repository=reference_repository,
        material_repository=material_repository,
    )

    with pytest.raises(ProcurementOpportunityBatchConflictError) as caught:
        await service.ingest_batch(
            [record("conflict"), record("conflict", title="Different")]
        )

    assert caught.value.conflicts == (("fixture", "conflict", (1, 2)),)
    opportunity_repository.get_by_identities.assert_not_awaited()
    reference_repository.get_region_by_code.assert_not_awaited()
    session.rollback.assert_not_awaited()


async def test_external_id_case_is_exact_while_source_case_is_canonicalized(
    db_session: AsyncSession,
) -> None:
    result = await build_service(db_session).ingest_batch(
        [
            record("Lot-A", source=" Fixture "),
            record("lot-a", source="FIXTURE"),
        ]
    )
    rows = await ProcurementOpportunityRepository(db_session).list_all()

    assert result.created == 2
    assert [(row.source, row.external_id) for row in rows] == [
        ("fixture", "Lot-A"),
        ("fixture", "lot-a"),
    ]


async def test_reference_validation_collects_all_categories_before_mutation(
    db_session: AsyncSession,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    invalid = record(
        "bad-refs",
        region_code="PNC_REG_MISSING",
        product_type_codes=["MISSING_PRODUCT"],
        material_requirements=[
            {
                "material_group_code": "MISSING_GROUP",
                "material_id": 999999,
                "requirement_strength": "MANDATORY",
            }
        ],
        technology_requirements=[
            {
                "technology_code": "MISSING_TECHNOLOGY",
                "requirement_strength": "PREFERRED",
            }
        ],
        equipment_requirements=[
            {
                "equipment_type_code": "MISSING_EQUIPMENT",
                "requirement_strength": "UNKNOWN",
            }
        ],
        required_certificates=[
            {
                "certificate_type_code": "PNC_CERT_MISSING",
                "requirement_strength": "MANDATORY",
            }
        ],
    )

    with pytest.raises(ProcurementOpportunityReferenceError) as caught:
        await build_service(db_session, repository).ingest_batch(
            [record("valid-before-bad"), invalid]
        )

    reasons = [issue[2] for issue in caught.value.issues]
    assert len(reasons) == 7
    assert reasons == sorted(reasons)
    assert any("region_code" in reason for reason in reasons)
    assert any("material_id" in reason for reason in reasons)
    assert await repository.list_all() == []


async def test_exact_material_must_belong_to_declared_group(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    material = Material(
        group_code=reference_rows["material_group"],
        grade_name="Service exact grade",
    )
    db_session.add(material)
    await db_session.commit()

    mismatched = record(
        "material-mismatch",
        material_requirements=[
            {
                "material_group_code": reference_rows["other_material_group"],
                "material_id": material.id,
                "requirement_strength": "MANDATORY",
            }
        ],
    )
    with pytest.raises(ProcurementOpportunityReferenceError, match="belongs"):
        await build_service(db_session).ingest_batch([mismatched])


async def test_reference_error_on_later_record_prevents_earlier_create(
    db_session: AsyncSession,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    with pytest.raises(ProcurementOpportunityReferenceError):
        await build_service(db_session, repository).ingest_batch(
            [
                record("would-be-valid"),
                record("invalid-later", product_type_codes=["MISSING_PRODUCT"]),
            ]
        )
    assert await repository.list_all() == []


async def test_commit_failure_rolls_back_replaced_snapshot(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    service = build_service(db_session, repository)
    await service.ingest_batch([record("rollback-update")])
    stored = await repository.get_by_identity("fixture", "rollback-update")
    assert stored is not None
    original_id = stored.id
    real_commit = db_session.commit

    async def fail_commit() -> None:
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="forced commit failure"):
        await service.ingest_batch([record("rollback-update", title="Must roll back")])
    monkeypatch.setattr(db_session, "commit", real_commit)

    reloaded = await repository.get_by_identity("fixture", "rollback-update")
    assert reloaded is not None
    assert reloaded.id == original_id
    assert reloaded.title == "Service opportunity"


async def test_failure_after_first_mutation_rolls_back_whole_batch(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    real_create = repository.create_from_canonical
    calls = 0

    async def fail_second_create(input_record: PreparedOpportunityInput):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("forced second-row failure")
        return await real_create(input_record)

    monkeypatch.setattr(repository, "create_from_canonical", fail_second_create)
    with pytest.raises(RuntimeError, match="forced second-row failure"):
        await build_service(db_session, repository).ingest_batch(
            [record("atomic-1"), record("atomic-2")]
        )

    assert await repository.list_all() == []


async def test_noop_does_not_call_create_or_replace(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProcurementOpportunityRepository(db_session)
    service = build_service(db_session, repository)
    same = record("pure-noop")
    await service.ingest_batch([same])

    create = AsyncMock()
    replace = AsyncMock()
    monkeypatch.setattr(repository, "create_from_canonical", create)
    monkeypatch.setattr(repository, "replace_snapshot", replace)
    result = await service.ingest_batch([same])

    assert result.unchanged == 1
    create.assert_not_awaited()
    replace.assert_not_awaited()
