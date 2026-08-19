from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProductionFacility
from app.schemas import ProductionFacilityCreate, ProductionFacilityUpdate


class ProductionFacilityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        facility_id: int,
    ) -> ProductionFacility | None:

        statement = (select(
            ProductionFacility).
            where(ProductionFacility.id == facility_id)
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: int,
    ) -> list[ProductionFacility]:
        statement = (
            select(ProductionFacility)
            .where(ProductionFacility.profile_id == profile_id)
            .order_by(ProductionFacility.id)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def create(
        self,
        profile_id: int,
        data: ProductionFacilityCreate,
    ) -> ProductionFacility:

        facility = ProductionFacility(
            profile_id=profile_id,
            **data.model_dump(),
        )

        self.session.add(facility)

        await self.session.commit()
        await self.session.refresh(facility)

        return facility

    async def update(
        self,
        facility_id: int,
        data: ProductionFacilityUpdate,
    ) -> ProductionFacility | None:

        facility = await self.get_by_id(facility_id)

        if not facility:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(facility, field, value)

        await self.session.commit()
        await self.session.refresh(facility)

        return facility

    async def delete(
        self,
        facility_id: int,
    ) -> ProductionFacility | None:

        facility = await self.get_by_id(facility_id)
        if not facility:
            return None
        await self.session.delete(facility)
        await self.session.commit()

        return facility
