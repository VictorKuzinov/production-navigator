from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    CompanySizeNotFoundError,
    DuplicateInnError,
    EnterpriseProfileNotFoundError,
    RegionNotFoundError,
)
from app.schemas import EnterpriseProfileCreate, EnterpriseProfileUpdate
from app.services.enterprises import EnterpriseProfileService


async def test_create_enterprise_rejects_unknown_region() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    references = SimpleNamespace(get_region_by_code=AsyncMock(return_value=None))
    service = EnterpriseProfileService(repository, references)

    with pytest.raises(RegionNotFoundError):
        await service.create(
            EnterpriseProfileCreate(
                company_name="Test enterprise",
                region_code="NO_SUCH_REGION",
            )
        )

    repository.create.assert_not_awaited()


async def test_create_enterprise_rejects_unknown_company_size() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    references = SimpleNamespace(
        get_company_size_by_code=AsyncMock(return_value=None)
    )
    service = EnterpriseProfileService(repository, references)

    with pytest.raises(CompanySizeNotFoundError):
        await service.create(
            EnterpriseProfileCreate(
                company_name="Test enterprise",
                company_size_code="NO_SUCH_SIZE",
            )
        )

    repository.create.assert_not_awaited()


async def test_update_enterprise_rejects_duplicate_inn_owned_by_another_profile(
) -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id=7)),
        get_by_inn=AsyncMock(return_value=SimpleNamespace(id=8)),
        update=AsyncMock(),
    )
    service = EnterpriseProfileService(repository, SimpleNamespace())

    with pytest.raises(DuplicateInnError):
        await service.update(
            7,
            EnterpriseProfileUpdate(inn="6671000000"),
        )

    repository.update.assert_not_awaited()


async def test_get_enterprise_raises_domain_not_found() -> None:
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = EnterpriseProfileService(repository, SimpleNamespace())

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.get_by_id(999)
