from datetime import date

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CapabilitySectionIntegrityError
from app.models import (
    CapabilityState,
    EnterpriseCertificate,
    EnterpriseProfile,
    Equipment,
    ProductionFacility,
    ProfileSectionCode,
    ProfileSectionCompleteness,
    ProfileTechnologyCapability,
    QualityCapability,
)
from app.repositories import (
    EnterpriseProfileRepository,
    ProcurementOpportunityRepository,
    ProfileMatchingProjectionRepository,
)
from app.schemas import EnterpriseProfileCreate
from app.schemas.procurement_opportunities import PreparedOpportunityInput
from app.services.procurement_opportunities import (
    canonical_opportunity_from_aggregate,
)


async def create_profile(
    db_session: AsyncSession,
    suffix: str,
):
    return await EnterpriseProfileRepository(db_session).create(
        EnterpriseProfileCreate(
            company_name=f"Matching profile {suffix}",
            inn=f"6672000{int(suffix):03d}",
        )
    )


def make_opportunity() -> PreparedOpportunityInput:
    return PreparedOpportunityInput.model_validate(
        {
            "source": "fixture",
            "external_id": "projection-1",
            "title": "Projection opportunity",
            "status": "OPEN",
            "okpd2_codes": ["25.62.10.000"],
            "product_type_codes": [],
            "material_requirements": None,
            "technology_requirements": [
                {
                    "technology_code": "TURNING",
                    "requirement_strength": "MANDATORY",
                }
            ],
            "equipment_requirements": None,
            "dimensional_mass_requirements": None,
            "quality_requirements": None,
            "required_certificates": None,
        }
    )


async def test_profile_projection_is_complete_ordered_and_profile_scoped(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    profile = await create_profile(db_session, "001")
    other = await create_profile(db_session, "002")
    facility = ProductionFacility(
        profile_id=profile.id,
        facility_name="Matching facility",
        total_area=100,
        available_area=50,
    )
    db_session.add(facility)
    await db_session.flush()
    db_session.add_all(
        [
            ProfileTechnologyCapability(
                profile_id=profile.id,
                technology_code=reference_rows["other_technology_type"],
                state=CapabilityState.UNKNOWN,
            ),
            ProfileTechnologyCapability(
                profile_id=profile.id,
                technology_code=reference_rows["technology_type"],
                state=CapabilityState.SUPPORTED,
            ),
            ProfileTechnologyCapability(
                profile_id=other.id,
                technology_code=reference_rows["technology_type"],
                state=CapabilityState.UNSUPPORTED,
            ),
            Equipment(
                profile_id=profile.id,
                facility_id=facility.id,
                equipment_type_code=reference_rows["equipment_type"],
                cnc=True,
                axes=5,
                quantity=2,
                working_zone_x=500.25,
            ),
            QualityCapability(
                profile_id=profile.id,
                min_it_grade=7,
                min_ra=0.8,
                measuring_tools=True,
                cim_machine=False,
            ),
            EnterpriseCertificate(
                profile_id=profile.id,
                certificate_type_code=reference_rows["certificate_type"],
                issue_date=date(2026, 1, 1),
                expiry_date=date(2026, 12, 31),
            ),
        ]
    )
    await db_session.commit()

    snapshot = await ProfileMatchingProjectionRepository(db_session).get_by_id(
        profile.id
    )

    assert snapshot is not None
    assert [row.technology_code for row in snapshot.technology_capabilities] == [
        reference_rows["other_technology_type"],
        reference_rows["technology_type"],
    ]
    assert [row.state for row in snapshot.technology_capabilities] == [
        CapabilityState.UNKNOWN,
        CapabilityState.SUPPORTED,
    ]
    assert len(snapshot.equipments) == 1
    assert str(snapshot.equipments[0].working_zone_x) == "500.25"
    assert snapshot.quality_capability is not None
    assert str(snapshot.quality_capability.min_ra) == "0.8"
    assert len(snapshot.certificates) == 1


async def test_profile_projection_requires_both_completeness_rows(
    db_session: AsyncSession,
) -> None:
    profile = await create_profile(db_session, "003")
    await db_session.execute(
        delete(ProfileSectionCompleteness).where(
            ProfileSectionCompleteness.profile_id == profile.id,
            ProfileSectionCompleteness.section_code == ProfileSectionCode.MATERIALS,
        )
    )
    await db_session.commit()

    with pytest.raises(CapabilitySectionIntegrityError, match="missing"):
        await ProfileMatchingProjectionRepository(db_session).get_by_id(profile.id)


async def test_projection_repository_does_not_commit(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = await create_profile(db_session, "004")
    calls = 0

    async def commit_spy() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(db_session, "commit", commit_spy)
    pending = EnterpriseProfile(company_name="Must not autoflush", inn="6672999999")
    db_session.add(pending)
    snapshot = await ProfileMatchingProjectionRepository(db_session).get_by_id(
        profile.id
    )

    assert snapshot is not None
    assert calls == 0
    assert pending.id is None


def test_projection_rejects_non_finite_float_facts() -> None:
    with pytest.raises(ValueError, match="finite"):
        ProfileMatchingProjectionRepository._finite_decimal(float("nan"), "field")


def test_projection_rejects_negative_float_facts() -> None:
    with pytest.raises(ValueError, match="finite"):
        ProfileMatchingProjectionRepository._finite_decimal(float("inf"), "field")


async def test_opportunity_get_by_id_and_shared_projector_preserve_tri_state(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> None:
    assert reference_rows["technology_type"] == "TURNING"
    repository = ProcurementOpportunityRepository(db_session)
    created = await repository.create_from_canonical(make_opportunity())
    await db_session.commit()

    loaded = await repository.get_by_id(created.id)
    assert loaded is not None
    projected = canonical_opportunity_from_aggregate(loaded)

    assert projected.product_type_codes == []
    assert projected.material_requirements is None
    assert projected.technology_requirements is not None
    assert projected.technology_requirements[0].technology_code == "TURNING"
