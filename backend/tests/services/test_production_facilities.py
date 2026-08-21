from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    ProductionFacilityNotFoundError,
)
from app.schemas import ProductionFacilityCreate, ProductionFacilityUpdate
from app.services.production_facilities import ProductionFacilityService


async def test_create_facility_requires_existing_enterprise() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = ProductionFacilityService(repository, enterprises)

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.create(
            999,
            ProductionFacilityCreate(
                facility_name="Test facility",
                total_area=200.0,
                available_area=80.0,
            ),
        )

    repository.create.assert_not_awaited()


async def test_update_facility_raises_domain_not_found() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        update=AsyncMock(),
    )
    service = ProductionFacilityService(repository, SimpleNamespace())

    with pytest.raises(ProductionFacilityNotFoundError):
        await service.update(
            999,
            ProductionFacilityUpdate(available_area=70.0),
        )

    repository.update.assert_not_awaited()
