from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Warehouse
from app.schemas import WarehouseCreate, WarehouseUpdate


class WarehouseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        warehouse_id: int,
    ) -> Warehouse | None:
        statement = select(Warehouse).where(Warehouse.id == warehouse_id)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: int,
    ) -> list[Warehouse]:
        statement = (
            select(Warehouse)
            .where(Warehouse.profile_id == profile_id)
            .order_by(Warehouse.id)
        )
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def create(
        self,
        profile_id: int,
        data: WarehouseCreate,
    ) -> Warehouse:
        warehouse = Warehouse(
            profile_id=profile_id,
            **data.model_dump(),
        )
        self.session.add(warehouse)

        await self.session.commit()
        await self.session.refresh(warehouse)

        return warehouse

    async def update(
        self,
        warehouse_id: int,
        data: WarehouseUpdate,
    ) -> Warehouse | None:
        warehouse = await self.get_by_id(warehouse_id)

        if warehouse is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(warehouse, field, value)

        await self.session.commit()
        await self.session.refresh(warehouse)

        return warehouse

    async def delete(
        self,
        warehouse_id: int,
    ) -> Warehouse | None:
        warehouse = await self.get_by_id(warehouse_id)

        if warehouse is None:
            return None

        await self.session.delete(warehouse)
        await self.session.commit()

        return warehouse
