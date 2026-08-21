from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    EquipmentNotFoundError,
    EquipmentTypeNotFoundError,
    ProductionFacilityNotFoundError,
)
from app.schemas import EquipmentCreate, EquipmentUpdate
from app.services.equipments import EquipmentService


def build_service(
    repository,
    enterprises,
    facilities,
    references,
) -> EquipmentService:
    return EquipmentService(
        repository,
        enterprises,
        facilities,
        references,
    )


async def test_create_equipment_requires_existing_enterprise() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    facilities = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_equipment_type_by_code=AsyncMock())
    service = build_service(repository, enterprises, facilities, references)

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.create(
            999,
            10,
            EquipmentCreate(equipment_type_code="TURNING"),
        )

    facilities.get_by_id.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_equipment_rejects_facility_owned_by_another_profile() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    facilities = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(profile_id=8))
    )
    references = SimpleNamespace(get_equipment_type_by_code=AsyncMock())
    service = build_service(repository, enterprises, facilities, references)

    with pytest.raises(ProductionFacilityNotFoundError):
        await service.create(
            7,
            10,
            EquipmentCreate(equipment_type_code="TURNING"),
        )

    references.get_equipment_type_by_code.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_equipment_rejects_unknown_equipment_type() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    facilities = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(profile_id=7))
    )
    references = SimpleNamespace(
        get_equipment_type_by_code=AsyncMock(return_value=None)
    )
    service = build_service(repository, enterprises, facilities, references)

    with pytest.raises(EquipmentTypeNotFoundError):
        await service.create(
            7,
            10,
            EquipmentCreate(equipment_type_code="NO_SUCH_TYPE"),
        )

    repository.create.assert_not_awaited()


async def test_update_equipment_validates_changed_equipment_type() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=object()),
        update=AsyncMock(),
    )
    references = SimpleNamespace(
        get_equipment_type_by_code=AsyncMock(return_value=None)
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        references,
    )

    with pytest.raises(EquipmentTypeNotFoundError):
        await service.update(
            10,
            EquipmentUpdate(equipment_type_code="NO_SUCH_TYPE"),
        )

    repository.update.assert_not_awaited()


async def test_get_equipment_raises_domain_not_found() -> None:
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(EquipmentNotFoundError):
        await service.get_by_id(999)
