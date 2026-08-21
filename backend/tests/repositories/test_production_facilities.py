from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnterpriseProfile
from app.repositories.production_facilities import ProductionFacilityRepository
from app.schemas import ProductionFacilityCreate, ProductionFacilityUpdate


async def test_facility_repository_crud_persists_patch_semantics(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
) -> None:
    repository = ProductionFacilityRepository(db_session)
    created = await repository.create(
        enterprise_row.id,
        ProductionFacilityCreate(
            facility_name="Repository facility",
            total_area=300.0,
            available_area=100.0,
            power_capacity=200.0,
            compressed_air=True,
        ),
    )

    fetched = await repository.get_by_id(created.id)
    listed = await repository.list_by_profile(enterprise_row.id)
    updated = await repository.update(
        created.id,
        ProductionFacilityUpdate(available_area=75.0),
    )

    assert fetched is not None
    assert [facility.id for facility in listed] == [created.id]
    assert updated is not None
    assert updated.available_area == 75.0
    assert updated.total_area == 300.0
    assert updated.compressed_air is True

    deleted = await repository.delete(created.id)

    assert deleted is not None
    assert await repository.get_by_id(created.id) is None
