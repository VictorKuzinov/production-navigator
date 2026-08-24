from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LiftingEquipment
from app.schemas import LiftingEquipmentCreate, LiftingEquipmentUpdate


class LiftingEquipmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        lifting_equipment_id: int,
    ) -> LiftingEquipment | None:
        statement = select(LiftingEquipment).where(
            LiftingEquipment.id == lifting_equipment_id
        )
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: int,
    ) -> list[LiftingEquipment]:
        statement = (
            select(LiftingEquipment)
            .where(LiftingEquipment.profile_id == profile_id)
            .order_by(LiftingEquipment.id)
        )
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def create(
        self,
        profile_id: int,
        data: LiftingEquipmentCreate,
    ) -> LiftingEquipment:
        lifting_equipment = LiftingEquipment(
            profile_id=profile_id,
            **data.model_dump(),
        )
        self.session.add(lifting_equipment)

        await self.session.commit()
        await self.session.refresh(lifting_equipment)

        return lifting_equipment

    async def update(
        self,
        lifting_equipment_id: int,
        data: LiftingEquipmentUpdate,
    ) -> LiftingEquipment | None:
        lifting_equipment = await self.get_by_id(lifting_equipment_id)
        if lifting_equipment is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(lifting_equipment, field, value)

        await self.session.commit()
        await self.session.refresh(lifting_equipment)

        return lifting_equipment

    async def delete(
        self,
        lifting_equipment_id: int,
    ) -> LiftingEquipment | None:
        lifting_equipment = await self.get_by_id(lifting_equipment_id)
        if lifting_equipment is None:
            return None

        await self.session.delete(lifting_equipment)
        await self.session.commit()

        return lifting_equipment
