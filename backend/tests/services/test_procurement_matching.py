from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import EnterpriseProfileNotFoundError
from app.models.profile_capabilities import ProfileSectionState
from app.schemas.procurement_matching import ProfileMatchingSnapshot
from app.schemas.procurement_opportunities import PreparedOpportunityInput
from app.services.procurement_matching import (
    ProcurementMatchingService,
    ProcurementOpportunityNotFoundError,
)


def make_canonical() -> PreparedOpportunityInput:
    return PreparedOpportunityInput.model_validate(
        {
            "source": "fixture",
            "external_id": "service-1",
            "title": "Service opportunity",
            "status": "OPEN",
            "okpd2_codes": ["25.62.10.000"],
            "product_type_codes": None,
            "material_requirements": None,
            "technology_requirements": None,
            "equipment_requirements": None,
            "dimensional_mass_requirements": None,
            "quality_requirements": None,
            "required_certificates": None,
        }
    )


async def test_service_distinguishes_opportunity_not_found() -> None:
    opportunity_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    profile_repository = SimpleNamespace(get_by_id=AsyncMock())
    service = ProcurementMatchingService(
        opportunity_repository=opportunity_repository,
        profile_repository=profile_repository,
    )

    with pytest.raises(ProcurementOpportunityNotFoundError, match="17"):
        await service.match(17, 23, date(2026, 9, 3))
    profile_repository.get_by_id.assert_not_awaited()


async def test_service_distinguishes_profile_not_found() -> None:
    opportunity_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id=17))
    )
    profile_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = ProcurementMatchingService(
        opportunity_repository=opportunity_repository,
        profile_repository=profile_repository,
    )

    with pytest.raises(EnterpriseProfileNotFoundError, match="23"):
        await service.match(17, 23, date(2026, 9, 3))


async def test_service_projects_once_and_delegates_explicit_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aggregate = SimpleNamespace(id=17)
    canonical = make_canonical()
    profile = ProfileMatchingSnapshot(
        profile_id=23,
        technology_section_state=ProfileSectionState.UNKNOWN,
        material_section_state=ProfileSectionState.UNKNOWN,
    )
    opportunity_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=aggregate)
    )
    profile_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=profile))
    projection_calls: list[object] = []

    def projector(value):
        projection_calls.append(value)
        return canonical

    monkeypatch.setattr(
        "app.services.procurement_matching.canonical_opportunity_from_aggregate",
        projector,
    )

    class EngineSpy:
        def __init__(self):
            self.kwargs = None

        def match(self, **kwargs):
            self.kwargs = kwargs
            return "non-persistent-result"

    engine = EngineSpy()
    service = ProcurementMatchingService(
        opportunity_repository=opportunity_repository,
        profile_repository=profile_repository,
        engine=engine,
    )
    result = await service.match(17, 23, date(2026, 9, 3))

    assert result == "non-persistent-result"
    assert projection_calls == [aggregate]
    assert engine.kwargs["opportunity_id"] == 17
    assert engine.kwargs["opportunity"] is canonical
    assert engine.kwargs["profile"] is profile
    assert engine.kwargs["context"].evaluation_date == date(2026, 9, 3)
    assert not hasattr(service, "session")
