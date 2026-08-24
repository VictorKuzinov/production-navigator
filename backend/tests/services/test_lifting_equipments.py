from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    CraneTypeNotFoundError,
    EnterpriseProfileNotFoundError,
    LiftingEquipmentNotFoundError,
    ProductionFacilityNotFoundError,
    WarehouseNotFoundError,
)
from app.schemas import LiftingEquipmentCreate, LiftingEquipmentUpdate
from app.services.lifting_equipments import LiftingEquipmentService


def build_service(
    repository,
    enterprises,
    facilities,
    warehouses,
    references,
) -> LiftingEquipmentService:
    return LiftingEquipmentService(
        repository,
        enterprises,
        facilities,
        warehouses,
        references,
    )


@pytest.mark.parametrize(
    ("facility_id", "warehouse_id"),
    [
        (10, None),
        (None, 20),
        (10, 20),
        (None, None),
    ],
)
async def test_create_supports_all_location_combinations(
    facility_id: int | None,
    warehouse_id: int | None,
) -> None:
    created = SimpleNamespace(id=30, profile_id=7)
    repository = SimpleNamespace(create=AsyncMock(return_value=created))
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    facilities = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(profile_id=7))
    )
    warehouses = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(profile_id=7))
    )
    references = SimpleNamespace(
        get_crane_type_by_code=AsyncMock(return_value=object())
    )
    service = build_service(
        repository,
        enterprises,
        facilities,
        warehouses,
        references,
    )
    data = LiftingEquipmentCreate(
        crane_type_code="OVERHEAD_CRANE",
        facility_id=facility_id,
        warehouse_id=warehouse_id,
        load_capacity_tons=5.0,
    )

    result = await service.create(7, data)

    assert result is created
    if facility_id is None:
        facilities.get_by_id.assert_not_awaited()
    else:
        facilities.get_by_id.assert_awaited_once_with(facility_id)
    if warehouse_id is None:
        warehouses.get_by_id.assert_not_awaited()
    else:
        warehouses.get_by_id.assert_awaited_once_with(warehouse_id)
    references.get_crane_type_by_code.assert_awaited_once_with("OVERHEAD_CRANE")
    repository.create.assert_awaited_once_with(7, data)


async def test_create_requires_existing_enterprise() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    facilities = SimpleNamespace(get_by_id=AsyncMock())
    warehouses = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_crane_type_by_code=AsyncMock())
    service = build_service(
        repository,
        enterprises,
        facilities,
        warehouses,
        references,
    )

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.create(
            999,
            LiftingEquipmentCreate(
                crane_type_code="OVERHEAD_CRANE",
                load_capacity_tons=5.0,
            ),
        )

    facilities.get_by_id.assert_not_awaited()
    warehouses.get_by_id.assert_not_awaited()
    references.get_crane_type_by_code.assert_not_awaited()
    repository.create.assert_not_awaited()


@pytest.mark.parametrize(
    ("location_kind", "location_result", "expected_error"),
    [
        ("facility", None, ProductionFacilityNotFoundError),
        (
            "facility",
            SimpleNamespace(profile_id=8),
            ProductionFacilityNotFoundError,
        ),
        ("warehouse", None, WarehouseNotFoundError),
        ("warehouse", SimpleNamespace(profile_id=8), WarehouseNotFoundError),
    ],
)
async def test_create_rejects_unknown_or_cross_profile_locations(
    location_kind: str,
    location_result: object | None,
    expected_error: type[Exception],
) -> None:
    repository = SimpleNamespace(create=AsyncMock())
    enterprises = SimpleNamespace(get_by_id=AsyncMock(return_value=object()))
    facilities = SimpleNamespace(get_by_id=AsyncMock())
    warehouses = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_crane_type_by_code=AsyncMock())
    if location_kind == "facility":
        facilities.get_by_id.return_value = location_result
        facility_id, warehouse_id = 10, None
    else:
        warehouses.get_by_id.return_value = location_result
        facility_id, warehouse_id = None, 20
    service = build_service(
        repository,
        enterprises,
        facilities,
        warehouses,
        references,
    )

    with pytest.raises(expected_error):
        await service.create(
            7,
            LiftingEquipmentCreate(
                crane_type_code="OVERHEAD_CRANE",
                facility_id=facility_id,
                warehouse_id=warehouse_id,
                load_capacity_tons=5.0,
            ),
        )

    references.get_crane_type_by_code.assert_not_awaited()
    repository.create.assert_not_awaited()


async def test_create_rejects_unknown_crane_type() -> None:
    repository = SimpleNamespace(create=AsyncMock())
    references = SimpleNamespace(get_crane_type_by_code=AsyncMock(return_value=None))
    service = build_service(
        repository,
        SimpleNamespace(get_by_id=AsyncMock(return_value=object())),
        SimpleNamespace(get_by_id=AsyncMock()),
        SimpleNamespace(get_by_id=AsyncMock()),
        references,
    )

    with pytest.raises(CraneTypeNotFoundError):
        await service.create(
            7,
            LiftingEquipmentCreate(
                crane_type_code="NO_SUCH_TYPE",
                load_capacity_tons=5.0,
            ),
        )

    repository.create.assert_not_awaited()


async def test_update_sets_locations_and_validates_ownership() -> None:
    lifting_equipment = SimpleNamespace(id=30, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=lifting_equipment),
        update=AsyncMock(return_value=lifting_equipment),
    )
    facilities = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(profile_id=7))
    )
    warehouses = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(profile_id=7))
    )
    references = SimpleNamespace(get_crane_type_by_code=AsyncMock())
    service = build_service(
        repository,
        SimpleNamespace(),
        facilities,
        warehouses,
        references,
    )
    update = LiftingEquipmentUpdate(facility_id=10, warehouse_id=20)

    result = await service.update(30, update)

    assert result is lifting_equipment
    facilities.get_by_id.assert_awaited_once_with(10)
    warehouses.get_by_id.assert_awaited_once_with(20)
    references.get_crane_type_by_code.assert_not_awaited()
    repository.update.assert_awaited_once_with(30, update)


async def test_update_clears_locations_without_lookup() -> None:
    lifting_equipment = SimpleNamespace(id=30, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=lifting_equipment),
        update=AsyncMock(return_value=lifting_equipment),
    )
    facilities = SimpleNamespace(get_by_id=AsyncMock())
    warehouses = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_crane_type_by_code=AsyncMock())
    service = build_service(
        repository,
        SimpleNamespace(),
        facilities,
        warehouses,
        references,
    )
    update = LiftingEquipmentUpdate(facility_id=None, warehouse_id=None)

    result = await service.update(30, update)

    assert result is lifting_equipment
    facilities.get_by_id.assert_not_awaited()
    warehouses.get_by_id.assert_not_awaited()
    references.get_crane_type_by_code.assert_not_awaited()
    repository.update.assert_awaited_once_with(30, update)


async def test_update_omitted_fields_skip_unrelated_validation() -> None:
    lifting_equipment = SimpleNamespace(id=30, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=lifting_equipment),
        update=AsyncMock(return_value=lifting_equipment),
    )
    facilities = SimpleNamespace(get_by_id=AsyncMock())
    warehouses = SimpleNamespace(get_by_id=AsyncMock())
    references = SimpleNamespace(get_crane_type_by_code=AsyncMock())
    service = build_service(
        repository,
        SimpleNamespace(),
        facilities,
        warehouses,
        references,
    )
    update = LiftingEquipmentUpdate(max_lift_height=8.0)

    await service.update(30, update)

    facilities.get_by_id.assert_not_awaited()
    warehouses.get_by_id.assert_not_awaited()
    references.get_crane_type_by_code.assert_not_awaited()
    repository.update.assert_awaited_once_with(30, update)


@pytest.mark.parametrize(
    ("location_kind", "location_result", "expected_error"),
    [
        ("facility", None, ProductionFacilityNotFoundError),
        (
            "facility",
            SimpleNamespace(profile_id=8),
            ProductionFacilityNotFoundError,
        ),
        ("warehouse", None, WarehouseNotFoundError),
        ("warehouse", SimpleNamespace(profile_id=8), WarehouseNotFoundError),
    ],
)
async def test_update_rejects_unknown_or_cross_profile_locations(
    location_kind: str,
    location_result: object | None,
    expected_error: type[Exception],
) -> None:
    lifting_equipment = SimpleNamespace(id=30, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=lifting_equipment),
        update=AsyncMock(),
    )
    facilities = SimpleNamespace(get_by_id=AsyncMock())
    warehouses = SimpleNamespace(get_by_id=AsyncMock())
    if location_kind == "facility":
        facilities.get_by_id.return_value = location_result
        update = LiftingEquipmentUpdate(facility_id=10)
    else:
        warehouses.get_by_id.return_value = location_result
        update = LiftingEquipmentUpdate(warehouse_id=20)
    service = build_service(
        repository,
        SimpleNamespace(),
        facilities,
        warehouses,
        SimpleNamespace(get_crane_type_by_code=AsyncMock()),
    )

    with pytest.raises(expected_error):
        await service.update(30, update)

    repository.update.assert_not_awaited()


async def test_update_rejects_unknown_changed_crane_type() -> None:
    lifting_equipment = SimpleNamespace(id=30, profile_id=7)
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=lifting_equipment),
        update=AsyncMock(),
    )
    references = SimpleNamespace(get_crane_type_by_code=AsyncMock(return_value=None))
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(get_by_id=AsyncMock()),
        SimpleNamespace(get_by_id=AsyncMock()),
        references,
    )

    with pytest.raises(CraneTypeNotFoundError):
        await service.update(
            30,
            LiftingEquipmentUpdate(crane_type_code="NO_SUCH_TYPE"),
        )

    repository.update.assert_not_awaited()


async def test_list_requires_existing_enterprise() -> None:
    repository = SimpleNamespace(list_by_profile=AsyncMock())
    service = build_service(
        repository,
        SimpleNamespace(get_by_id=AsyncMock(return_value=None)),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(EnterpriseProfileNotFoundError):
        await service.list_by_profile(999)

    repository.list_by_profile.assert_not_awaited()


async def test_get_raises_domain_not_found() -> None:
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(LiftingEquipmentNotFoundError):
        await service.get_by_id(999)


async def test_delete_raises_domain_not_found() -> None:
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        delete=AsyncMock(),
    )
    service = build_service(
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(LiftingEquipmentNotFoundError):
        await service.delete(999)

    repository.delete.assert_not_awaited()
