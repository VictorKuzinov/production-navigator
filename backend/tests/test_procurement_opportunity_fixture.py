from datetime import date, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Region, RequirementStrength
from app.repositories import (
    MaterialRepository,
    ProcurementOpportunityRepository,
    ReferenceRepository,
)
from app.schemas.procurement_opportunities import PreparedOpportunityDocument
from app.seeds.classifications import REFERENCE_SEEDS
from app.seeds.procurement_opportunities import (
    BUNDLED_FIXTURE_PATH,
    load_bundled_document,
)
from app.seeds.references import REGION_DATA
from app.services.procurement_opportunities import (
    ProcurementOpportunityIngestionService,
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


def test_bundled_fixture_is_utf8_valid_and_has_exactly_50_stable_identities() -> None:
    raw = BUNDLED_FIXTURE_PATH.read_bytes()
    decoded = raw.decode("utf-8")
    document = PreparedOpportunityDocument.model_validate_json(decoded)
    identities = {
        (record.source, record.external_id) for record in document.opportunities
    }

    assert len(document.opportunities) == 50
    assert len(identities) == 50
    assert all(record.external_id for record in document.opportunities)
    assert all(
        "PNC-OPP-2026-" in record.external_id for record in document.opportunities
    )


def test_fixture_has_representative_tri_state_strength_status_and_deadlines() -> None:
    document = load_bundled_document()
    for field in SIGNAL_FIELDS:
        values = [getattr(record, field) for record in document.opportunities]
        assert any(value is None for value in values)
        assert any(value == [] for value in values)
        assert any(value for value in values)

    assert {record.status.value for record in document.opportunities} == {
        "OPEN",
        "CLOSED",
        "CANCELLED",
        "AWARDED",
        "UNKNOWN",
    }
    strengths = set()
    for record in document.opportunities:
        for field in (
            "material_requirements",
            "technology_requirements",
            "equipment_requirements",
            "dimensional_mass_requirements",
            "quality_requirements",
            "required_certificates",
        ):
            for item in getattr(record, field) or []:
                strengths.add(item.requirement_strength)
    assert strengths == set(RequirementStrength)

    deadlines = [
        deadline
        for record in document.opportunities
        for deadline in (
            record.application_deadline,
            record.execution_deadline,
        )
        if deadline is not None
    ]
    assert any(type(deadline) is date for deadline in deadlines)
    assert any(isinstance(deadline, datetime) for deadline in deadlines)


def test_all_fixture_reference_codes_exist_in_committed_seed_vocabularies() -> None:
    document = load_bundled_document()
    seed_codes = {
        model.__name__: {row[0] for row in data} for model, data in REFERENCE_SEEDS
    }
    region_codes = {row[0] for row in REGION_DATA}

    for record in document.opportunities:
        if record.region_code is not None:
            assert record.region_code in region_codes
        assert set(record.product_type_codes or []).issubset(seed_codes["ProductType"])
        assert {
            item.material_group_code for item in record.material_requirements or []
        }.issubset(seed_codes["MaterialGroup"])
        assert {
            item.technology_code for item in record.technology_requirements or []
        }.issubset(seed_codes["TechnologyType"])
        assert {
            item.equipment_type_code for item in record.equipment_requirements or []
        }.issubset(seed_codes["EquipmentType"])
        assert {
            item.certificate_type_code for item in record.required_certificates or []
        }.issubset(seed_codes["CertificateType"])


async def seed_fixture_references(db_session: AsyncSession) -> None:
    rows = []
    for model, data in REFERENCE_SEEDS:
        rows.extend(
            model(
                code=code,
                name_ru=name_ru,
                ics_section=ics_section,
                ref_system=ref_system,
                ref_code=ref_code,
                description=description,
            )
            for code, name_ru, ics_section, ref_system, ref_code, description in data
        )
    rows.extend(
        Region(
            code=code,
            name_ru=name_ru,
            ics_section=ics_section,
            ref_system=ref_system,
            ref_code=ref_code,
            description=description,
        )
        for code, name_ru, ics_section, ref_system, ref_code, description in REGION_DATA
    )
    db_session.add_all(rows)
    await db_session.commit()


async def test_fixture_first_import_creates_50_and_second_is_50_noops(
    db_session: AsyncSession,
) -> None:
    await seed_fixture_references(db_session)
    document = load_bundled_document()
    service = ProcurementOpportunityIngestionService(
        session=db_session,
        opportunity_repository=ProcurementOpportunityRepository(db_session),
        reference_repository=ReferenceRepository(db_session),
        material_repository=MaterialRepository(db_session),
    )

    first = await service.ingest_batch(document.opportunities)
    second = await service.ingest_batch(document.opportunities)

    assert first.model_dump() == {
        "received_rows": 50,
        "unique_identities": 50,
        "created": 50,
        "updated": 0,
        "unchanged": 0,
        "duplicate_rows": 0,
    }
    assert second.model_dump() == {
        "received_rows": 50,
        "unique_identities": 50,
        "created": 0,
        "updated": 0,
        "unchanged": 50,
        "duplicate_rows": 0,
    }


def test_loader_resolves_fixture_from_its_module_not_working_directory() -> None:
    assert BUNDLED_FIXTURE_PATH == Path(
        __import__(
            "app.seeds.procurement_opportunities",
            fromlist=["__file__"],
        ).__file__
    ).with_name("procurement_opportunities.json")
    assert BUNDLED_FIXTURE_PATH.is_file()
