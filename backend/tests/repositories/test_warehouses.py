from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnterpriseProfile
from app.repositories.warehouses import WarehouseRepository
from app.schemas import WarehouseCreate, WarehouseUpdate


async def test_warehouse_repository_crud_allows_clearing_nullable_max_load(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> None:
    repository = WarehouseRepository(db_session)
    created = await repository.create(
        enterprise_row.id,
        WarehouseCreate(
            warehouse_type_code=reference_rows["warehouse_type"],
            total_capacity_cube=150.0,
            max_load_sqm=20.0,
            temperature_control=False,
        ),
    )

    fetched = await repository.get_by_id(created.id)
    listed = await repository.list_by_profile(enterprise_row.id)
    updated = await repository.update(
        created.id,
        WarehouseUpdate(max_load_sqm=None),
    )

    assert fetched is not None
    assert [warehouse.id for warehouse in listed] == [created.id]
    assert updated is not None
    assert updated.max_load_sqm is None
    assert updated.total_capacity_cube == 150.0
    assert updated.warehouse_type_code == reference_rows["warehouse_type"]

    deleted = await repository.delete(created.id)

    assert deleted is not None
    assert await repository.get_by_id(created.id) is None
