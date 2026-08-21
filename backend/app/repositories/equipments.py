from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Equipment
from app.schemas import EquipmentCreate, EquipmentUpdate


class EquipmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        equipment_id: int,
    ) -> Equipment | None:
        statement = select(Equipment).where(
            Equipment.id == equipment_id
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_facility(
        self,
        profile_id: int,
        facility_id: int,
    ) -> list[Equipment]:
        statement = (
            select(Equipment)
            .where(
                Equipment.profile_id == profile_id,
                Equipment.facility_id == facility_id,
                )
            .order_by(Equipment.id)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def create(
        self,
        profile_id: int,
        facility_id: int,
        data: EquipmentCreate,
    ) -> Equipment:

        equipment = Equipment(
            profile_id=profile_id,
            facility_id=facility_id,
            **data.model_dump(),
        )

        self.session.add(equipment)

        await self.session.commit()
        await self.session.refresh(equipment)

        return equipment

    async def update(
        self,
        equipment_id: int,
        data: EquipmentUpdate,
    ) -> Equipment | None:

        equipment = await self.get_by_id(equipment_id)

        if not equipment:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(equipment, field, value)

        await self.session.commit()
        await self.session.refresh(equipment)

        return equipment

    async def delete(
        self,
        equipment_id: int,
    ) -> Equipment | None:

        equipment = await self.get_by_id(equipment_id)
        if not equipment:
            return None

        await self.session.delete(equipment)
        await self.session.commit()

        return equipment
