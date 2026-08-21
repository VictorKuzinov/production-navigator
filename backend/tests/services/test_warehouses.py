from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    WarehouseNotFoundError,
    WarehouseTypeNotFoundError,
)
from app.schemas import WarehouseCreate, WarehouseUpdate
from app.services.warehouses import WarehouseService


def build_service(repository, enterprises, references) -> WarehouseService:
    return WarehouseService(repository, enterprises, references)


async def test_create_warehouse_requires_existing_enterprise() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    references = SimpleNamespace(get_warehouse_type_by_code=AsyncMock())
    service = build_service(repository, enterprises, references)

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.create_warehouse(
            999,
            WarehouseCreate(
                warehouse_type_code="UNIVERSAL",
                total_capacity_cube=120.0,
            ),
        )

    references.get_warehouse_type_by_code.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_warehouse_rejects_unknown_warehouse_type() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    references = SimpleNamespace(
        get_warehouse_type_by_code=AsyncMock(return_value=None)
    )
    service = build_service(repository, enterprises, references)

    with pytest.raises(WarehouseTypeNotFoundError):
        await service.create_warehouse(
            7,
            WarehouseCreate(
                warehouse_type_code="NO_SUCH_TYPE",
                total_capacity_cube=120.0,
            ),
        )

    repository.create.assert_not_awaited()


async def test_update_warehouse_validates_changed_warehouse_type() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=object()),
        update=AsyncMock(),
    )
    references = SimpleNamespace(
        get_warehouse_type_by_code=AsyncMock(return_value=None)
    )
    service = build_service(repository, SimpleNamespace(), references)

    with pytest.raises(WarehouseTypeNotFoundError):
        await service.update_warehouse(
            10,
            WarehouseUpdate(warehouse_type_code="NO_SUCH_TYPE"),
        )

    repository.update.assert_not_awaited()


async def test_update_warehouse_skips_reference_lookup_when_type_is_omitted() -> None:
    warehouse = SimpleNamespace(id=10)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=warehouse),
        update=AsyncMock(return_value=warehouse),
    )
    references = SimpleNamespace(get_warehouse_type_by_code=AsyncMock())
    service = build_service(repository, SimpleNamespace(), references)
    update = WarehouseUpdate(total_capacity_cube=200.0)

    result = await service.update_warehouse(10, update)

    assert result is warehouse
    references.get_warehouse_type_by_code.assert_not_awaited()
    repository.update.assert_awaited_once_with(10, update)


async def test_get_warehouse_raises_domain_not_found() -> None:
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = build_service(repository, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(WarehouseNotFoundError):
        await service.get_warehouse(999)
