import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnterpriseProfile, ProductionFacility, Warehouse
from app.repositories.lifting_equipments import LiftingEquipmentRepository
from app.schemas import LiftingEquipmentCreate, LiftingEquipmentUpdate


@pytest.mark.parametrize(
    "location_kind",
    ["facility", "warehouse", "both", "neither"],
)
async def test_repository_persists_all_location_combinations(
    location_kind: str,
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    facility_row: ProductionFacility,
    warehouse_row: Warehouse,
    reference_rows: dict[str, str],
) -> None:
    facility_id = facility_row.id if location_kind in {"facility", "both"} else None
    warehouse_id = warehouse_row.id if location_kind in {"warehouse", "both"} else None
    repository = LiftingEquipmentRepository(db_session)
    created = await repository.create(
        enterprise_row.id,
        LiftingEquipmentCreate(
            crane_type_code=reference_rows["crane_type"],
            facility_id=facility_id,
            warehouse_id=warehouse_id,
            load_capacity_tons=5.0,
            quantity=2,
        ),
    )

    fetched = await repository.get_by_id(created.id)
    listed = await repository.list_by_profile(enterprise_row.id)

    assert fetched is not None
    assert fetched.facility_id == facility_id
    assert fetched.warehouse_id == warehouse_id
    assert [item.id for item in listed] == [created.id]

    deleted = await repository.delete(created.id)

    assert deleted is not None
    assert await repository.get_by_id(created.id) is None


async def test_repository_update_sets_clears_and_preserves_omitted_fields(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    facility_row: ProductionFacility,
    warehouse_row: Warehouse,
    reference_rows: dict[str, str],
) -> None:
    replacement_facility = ProductionFacility(
        profile_id=enterprise_row.id,
        facility_name="Replacement facility",
        total_area=220.0,
        available_area=70.0,
        power_capacity=130.0,
        gas_supply=False,
        compressed_air=True,
        water_supply=True,
        steam_supply=False,
    )
    replacement_warehouse = Warehouse(
        profile_id=enterprise_row.id,
        warehouse_type_code=reference_rows["other_warehouse_type"],
        total_capacity_cube=140.0,
        max_load_sqm=18.0,
        temperature_control=False,
    )
    db_session.add_all([replacement_facility, replacement_warehouse])
    await db_session.commit()
    await db_session.refresh(replacement_facility)
    await db_session.refresh(replacement_warehouse)

    repository = LiftingEquipmentRepository(db_session)
    created = await repository.create(
        enterprise_row.id,
        LiftingEquipmentCreate(
            crane_type_code=reference_rows["crane_type"],
            load_capacity_tons=5.0,
            max_lift_height=6.0,
            quantity=2,
        ),
    )

    with_locations = await repository.update(
        created.id,
        LiftingEquipmentUpdate(
            facility_id=facility_row.id,
            warehouse_id=warehouse_row.id,
        ),
    )
    assert with_locations is not None
    assert with_locations.facility_id == facility_row.id
    assert with_locations.warehouse_id == warehouse_row.id
    assert with_locations.load_capacity_tons == 5.0
    assert with_locations.quantity == 2

    replaced = await repository.update(
        created.id,
        LiftingEquipmentUpdate(
            facility_id=replacement_facility.id,
            warehouse_id=replacement_warehouse.id,
        ),
    )
    assert replaced is not None
    assert replaced.facility_id == replacement_facility.id
    assert replaced.warehouse_id == replacement_warehouse.id

    persisted = await repository.get_by_id(created.id)
    assert persisted is not None
    assert persisted.facility_id == replacement_facility.id
    assert persisted.warehouse_id == replacement_warehouse.id

    unchanged = await repository.update(created.id, LiftingEquipmentUpdate())
    assert unchanged is not None
    assert unchanged.facility_id == replacement_facility.id
    assert unchanged.warehouse_id == replacement_warehouse.id
    assert unchanged.max_lift_height == 6.0

    cleared = await repository.update(
        created.id,
        LiftingEquipmentUpdate(
            facility_id=None,
            warehouse_id=None,
            max_lift_height=None,
        ),
    )
    assert cleared is not None
    assert cleared.facility_id is None
    assert cleared.warehouse_id is None
    assert cleared.max_lift_height is None
    assert cleared.crane_type_code == reference_rows["crane_type"]
    assert cleared.load_capacity_tons == 5.0
    assert cleared.quantity == 2


async def test_repository_list_by_profile_excludes_other_profiles(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> None:
    other_profile = EnterpriseProfile(company_name="Other repository profile")
    db_session.add(other_profile)
    await db_session.commit()
    await db_session.refresh(other_profile)

    repository = LiftingEquipmentRepository(db_session)
    own_item = await repository.create(
        enterprise_row.id,
        LiftingEquipmentCreate(
            crane_type_code=reference_rows["crane_type"],
            load_capacity_tons=5.0,
        ),
    )
    other_item = await repository.create(
        other_profile.id,
        LiftingEquipmentCreate(
            crane_type_code=reference_rows["crane_type"],
            load_capacity_tons=7.0,
        ),
    )

    own_list = await repository.list_by_profile(enterprise_row.id)
    other_list = await repository.list_by_profile(other_profile.id)

    assert [item.id for item in own_list] == [own_item.id]
    assert [item.id for item in other_list] == [other_item.id]
