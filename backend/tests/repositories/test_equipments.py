from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnterpriseProfile, ProductionFacility
from app.repositories.equipments import EquipmentRepository
from app.schemas import EquipmentCreate, EquipmentUpdate


async def test_equipment_repository_crud_persists_patch_semantics(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    facility_row: ProductionFacility,
    reference_rows: dict[str, str],
) -> None:
    repository = EquipmentRepository(db_session)
    created = await repository.create(
        enterprise_row.id,
        facility_row.id,
        EquipmentCreate(
            equipment_type_code=reference_rows["equipment_type"],
            model_name="Before update",
            cnc=True,
            axes=3,
            quantity=2,
        ),
    )

    fetched = await repository.get_by_id(created.id)
    listed = await repository.list_by_facility(
        enterprise_row.id,
        facility_row.id,
    )
    updated = await repository.update(
        created.id,
        EquipmentUpdate(model_name="After update"),
    )

    assert fetched is not None
    assert [equipment.id for equipment in listed] == [created.id]
    assert updated is not None
    assert updated.model_name == "After update"
    assert updated.equipment_type_code == reference_rows["equipment_type"]
    assert updated.quantity == 2

    deleted = await repository.delete(created.id)

    assert deleted is not None
    assert await repository.get_by_id(created.id) is None
