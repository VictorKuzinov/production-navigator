from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprises import EnterpriseProfile
from app.schemas.enterprises import (
    EnterpriseProfileCreate,
    EnterpriseProfileUpdate,
)


class EnterpriseProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        profile_id: int,
    ) -> EnterpriseProfile | None:
        
        statement = select(EnterpriseProfile).where(EnterpriseProfile.id == profile_id)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_inn(
        self,
        profile_inn: str,
    )-> EnterpriseProfile | None:

        statement = select(EnterpriseProfile).where(EnterpriseProfile.inn == profile_inn)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_ogrn(
        self,
        profile_ogrn: str,
    ) -> EnterpriseProfile | None:

        statement = select(EnterpriseProfile).where(EnterpriseProfile.ogrn == profile_ogrn)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_profiles(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[EnterpriseProfile]:

        statement = (
            select(EnterpriseProfile)
            .order_by(EnterpriseProfile.id)
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(statement)

        return result.scalars().all()

    async def create(
            self,
            data: EnterpriseProfileCreate,
    ) -> EnterpriseProfile:

        profile = EnterpriseProfile(
            **data.model_dump()
        )

        self.session.add(profile)

        await self.session.commit()
        await self.session.refresh(profile)

        return profile

    async def update(
            self,
            profile_id: int,
            data: EnterpriseProfileUpdate,
    ) -> EnterpriseProfile | None:

        profile = await self.get_by_id(profile_id)

        if not profile:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)

        await self.session.commit()
        await self.session.refresh(profile)

        return profile


    async def delete(
        self,
        profile_id: int,
    ) -> EnterpriseProfile | None:

        profile = await self.get_by_id(profile_id)
        if not profile:
            return None
        await self.session.delete(profile)
        await self.session.commit()

        return profile
