from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.profile_capabilities import CapabilityState, ProfileSectionState
from app.schemas.procurement_matching import (
    EquipmentSnapshot,
    MaterialCapabilitySnapshot,
    ProductExperienceSnapshot,
    ProfileMatchingSnapshot,
    TechnologyCapabilitySnapshot,
)
from app.schemas.procurement_matching_scoring import MatchStatus
from app.schemas.procurement_opportunities import PreparedOpportunityInput
from app.seeds.procurement_opportunities import load_bundled_document
from app.services.procurement_matching import ProcurementMatchingService

EVALUATION_TIME = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def opportunity(external_id: str, **changes: object) -> PreparedOpportunityInput:
    payload: dict[str, object] = {
        "source": "slice-b-test",
        "external_id": external_id,
        "title": external_id,
        "status": "OPEN",
        "okpd2_codes": [],
        "product_type_codes": [],
        "material_requirements": [],
        "technology_requirements": [],
        "equipment_requirements": [],
        "dimensional_mass_requirements": [],
        "quality_requirements": [],
        "required_certificates": [],
        "application_deadline": date(2026, 10, 1),
    }
    payload.update(changes)
    return PreparedOpportunityInput.model_validate(payload)


def profile() -> ProfileMatchingSnapshot:
    return ProfileMatchingSnapshot(
        profile_id=7,
        products=(
            ProductExperienceSnapshot(
                product_id=1,
                product_type_code="ASSEMBLY_UNIT",
            ),
        ),
        material_capabilities=(
            MaterialCapabilitySnapshot(
                capability_id=1,
                material_group_code="STEEL_CARBON",
                state=CapabilityState.SUPPORTED,
            ),
        ),
        technology_capabilities=(
            TechnologyCapabilitySnapshot(
                capability_id=1,
                technology_code="TURNING",
                state=CapabilityState.SUPPORTED,
            ),
            TechnologyCapabilitySnapshot(
                capability_id=2,
                technology_code="MILLING",
                state=CapabilityState.UNSUPPORTED,
            ),
        ),
        equipments=(
            EquipmentSnapshot(
                equipment_id=1,
                equipment_type_code="TURNING_CENTER",
                cnc=True,
                axes=3,
                quantity=2,
            ),
        ),
        technology_section_state=ProfileSectionState.CONFIRMED_COMPLETE,
        material_section_state=ProfileSectionState.CONFIRMED_COMPLETE,
    )


def custom_status_opportunities() -> list[PreparedOpportunityInput]:
    material = {
        "material_group_code": "STEEL_CARBON",
        "requirement_strength": "MANDATORY",
    }
    turning = {
        "technology_code": "TURNING",
        "requirement_strength": "MANDATORY",
    }
    equipment = {
        "equipment_type_code": "TURNING_CENTER",
        "requirement_strength": "MANDATORY",
    }
    match = opportunity(
        "STATUS-MATCH",
        material_requirements=[material],
        technology_requirements=[turning],
        equipment_requirements=[equipment],
    )
    return [
        match,
        opportunity(
            "STATUS-POTENTIAL",
            product_type_codes=["UNSEEN_PRODUCT"],
            material_requirements=[material],
        ),
        opportunity(
            "STATUS-LOW",
            product_type_codes=["ASSEMBLY_UNIT"],
            technology_requirements=[
                {
                    "technology_code": "MILLING",
                    "requirement_strength": "PREFERRED",
                }
            ],
        ),
        opportunity(
            "STATUS-INSUFFICIENT",
            product_type_codes=["ASSEMBLY_UNIT"],
            material_requirements=None,
            technology_requirements=None,
            equipment_requirements=None,
            dimensional_mass_requirements=None,
            quality_requirements=None,
            required_certificates=None,
        ),
        opportunity(
            "STATUS-INCOMPATIBLE",
            technology_requirements=[
                {
                    "technology_code": "MILLING",
                    "requirement_strength": "MANDATORY",
                }
            ],
        ),
        opportunity(
            "STATUS-NOT-ELIGIBLE",
            status="CLOSED",
            material_requirements=[material],
            technology_requirements=[turning],
            equipment_requirements=[equipment],
        ),
    ]


class OpportunityRepositoryStub:
    def __init__(self, aggregates: list[SimpleNamespace]):
        self.aggregates = aggregates
        self.by_id = {item.id: item for item in aggregates}

    async def get_by_id(self, opportunity_id: int):
        return self.by_id.get(opportunity_id)

    async def list_all(self):
        return list(self.aggregates)


@pytest.mark.asyncio
async def test_fixture_set_end_to_end_produces_all_statuses_and_stable_top_ten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared_fixture = load_bundled_document().opportunities
    prepared = [*prepared_fixture, *custom_status_opportunities()]
    aggregates = [
        SimpleNamespace(id=index, prepared=item)
        for index, item in enumerate(prepared, start=1)
    ]
    opportunity_repository = OpportunityRepositoryStub(aggregates)
    profile_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=profile()))
    monkeypatch.setattr(
        "app.services.procurement_matching.canonical_opportunity_from_aggregate",
        lambda aggregate: aggregate.prepared,
    )
    service = ProcurementMatchingService(
        opportunity_repository=opportunity_repository,
        profile_repository=profile_repository,
    )

    custom_aggregates = aggregates[-6:]
    scored = [
        await service.score_match(item.id, 7, EVALUATION_TIME)
        for item in custom_aggregates
    ]
    assert [item.match_status for item in scored] == [
        MatchStatus.MATCH,
        MatchStatus.POTENTIAL,
        MatchStatus.LOW_MATCH,
        MatchStatus.INSUFFICIENT_DATA,
        MatchStatus.INCOMPATIBLE,
        MatchStatus.NOT_ELIGIBLE,
    ]

    first = await service.top_matches(7, EVALUATION_TIME)
    second = await service.top_matches(7, EVALUATION_TIME)

    assert len(prepared_fixture) == 50
    assert len(first) == 10
    assert all(
        item.match_status not in {MatchStatus.NOT_ELIGIBLE, MatchStatus.INCOMPATIBLE}
        for item in first
    )
    assert [item.opportunity_identity for item in first] == [
        item.opportunity_identity for item in second
    ]
    required_fields = {
        "match_status",
        "compatibility_score",
        "coverage",
        "ranking_score",
        "eligibility_reasons",
        "positive_reasons",
        "hard_conflicts",
        "remediable_limitations",
        "missing_data",
        "missing_capabilities",
        "trace",
    }
    assert required_fields <= set(type(first[0]).model_fields)
