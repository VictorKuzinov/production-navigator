from datetime import datetime

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile_capabilities import (
    CapabilityState,
    ProfileMaterialCapability,
    ProfileSectionCode,
    ProfileSectionCompleteness,
    ProfileSectionState,
    ProfileTechnologyCapability,
)


class ProfileTechnologyCapabilityRepository:
    """Persistence operations that deliberately do not own commit."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(
        self,
        profile_id: int,
        technology_code: str,
    ) -> ProfileTechnologyCapability | None:
        statement = select(ProfileTechnologyCapability).where(
            ProfileTechnologyCapability.profile_id == profile_id,
            ProfileTechnologyCapability.technology_code == technology_code,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_for_profile(
        self,
        profile_id: int,
    ) -> list[ProfileTechnologyCapability]:
        statement = (
            select(ProfileTechnologyCapability)
            .where(ProfileTechnologyCapability.profile_id == profile_id)
            .order_by(ProfileTechnologyCapability.technology_code)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create(
        self,
        profile_id: int,
        technology_code: str,
        state: CapabilityState,
    ) -> ProfileTechnologyCapability:
        capability = ProfileTechnologyCapability(
            profile_id=profile_id,
            technology_code=technology_code,
            state=state,
        )
        self.session.add(capability)
        await self.session.flush()
        return capability

    async def update_state(
        self,
        capability: ProfileTechnologyCapability,
        state: CapabilityState,
    ) -> ProfileTechnologyCapability:
        capability.state = state
        await self.session.flush()
        return capability

    async def delete(self, capability: ProfileTechnologyCapability) -> None:
        await self.session.delete(capability)
        await self.session.flush()


class ProfileMaterialCapabilityRepository:
    """Material capability persistence without transaction ownership."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_group(
        self,
        profile_id: int,
        group_code: str,
    ) -> ProfileMaterialCapability | None:
        statement = select(ProfileMaterialCapability).where(
            ProfileMaterialCapability.profile_id == profile_id,
            ProfileMaterialCapability.material_group_code == group_code,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_material(
        self,
        profile_id: int,
        material_id: int,
    ) -> ProfileMaterialCapability | None:
        statement = select(ProfileMaterialCapability).where(
            ProfileMaterialCapability.profile_id == profile_id,
            ProfileMaterialCapability.material_id == material_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_for_profile(
        self,
        profile_id: int,
    ) -> list[ProfileMaterialCapability]:
        statement = (
            select(ProfileMaterialCapability)
            .where(ProfileMaterialCapability.profile_id == profile_id)
            .order_by(
                ProfileMaterialCapability.material_group_code.is_(None),
                ProfileMaterialCapability.material_group_code,
                ProfileMaterialCapability.material_id,
            )
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create_group(
        self,
        profile_id: int,
        group_code: str,
        state: CapabilityState,
    ) -> ProfileMaterialCapability:
        capability = ProfileMaterialCapability(
            profile_id=profile_id,
            material_group_code=group_code,
            material_id=None,
            state=state,
        )
        self.session.add(capability)
        await self.session.flush()
        return capability

    async def create_material(
        self,
        profile_id: int,
        material_id: int,
        state: CapabilityState,
    ) -> ProfileMaterialCapability:
        capability = ProfileMaterialCapability(
            profile_id=profile_id,
            material_group_code=None,
            material_id=material_id,
            state=state,
        )
        self.session.add(capability)
        await self.session.flush()
        return capability

    async def update_state(
        self,
        capability: ProfileMaterialCapability,
        state: CapabilityState,
    ) -> ProfileMaterialCapability:
        capability.state = state
        await self.session.flush()
        return capability

    async def delete(self, capability: ProfileMaterialCapability) -> None:
        await self.session.delete(capability)
        await self.session.flush()


class ProfileSectionCompletenessRepository:
    """Completeness persistence composed into service-owned transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(
        self,
        profile_id: int,
        section_code: ProfileSectionCode,
    ) -> ProfileSectionCompleteness | None:
        return await self.session.get(
            ProfileSectionCompleteness,
            (profile_id, section_code),
        )

    async def list_for_profile(
        self,
        profile_id: int,
    ) -> list[ProfileSectionCompleteness]:
        section_order = case(
            (ProfileSectionCompleteness.section_code == "TECHNOLOGIES", 0),
            else_=1,
        )
        statement = (
            select(ProfileSectionCompleteness)
            .where(ProfileSectionCompleteness.profile_id == profile_id)
            .order_by(section_order)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def invalidate(
        self,
        completeness: ProfileSectionCompleteness,
    ) -> ProfileSectionCompleteness:
        if completeness.state == ProfileSectionState.CONFIRMED_COMPLETE:
            completeness.state = ProfileSectionState.PARTIAL
            completeness.confirmed_at = None
            completeness.confirmed_by = None
            await self.session.flush()
        return completeness

    async def set_state(
        self,
        completeness: ProfileSectionCompleteness,
        state: ProfileSectionState,
    ) -> ProfileSectionCompleteness:
        completeness.state = state
        completeness.confirmed_at = None
        completeness.confirmed_by = None
        await self.session.flush()
        return completeness

    async def confirm(
        self,
        completeness: ProfileSectionCompleteness,
        confirmed_by: str,
        confirmed_at: datetime,
    ) -> ProfileSectionCompleteness:
        completeness.state = ProfileSectionState.CONFIRMED_COMPLETE
        completeness.confirmed_by = confirmed_by
        completeness.confirmed_at = confirmed_at
        await self.session.flush()
        return completeness
