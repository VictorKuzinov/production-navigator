from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CapabilitySectionIntegrityError,
    EnterpriseProfileNotFoundError,
    MaterialGroupNotFoundError,
    MaterialNotFoundError,
    TechnologyTypeNotFoundError,
)
from app.models import (
    CapabilityState,
    Material,
    ProfileMaterialCapability,
    ProfileSectionCode,
    ProfileSectionCompleteness,
    ProfileSectionState,
    ProfileTechnologyCapability,
)
from app.repositories import (
    EnterpriseProfileRepository,
    MaterialRepository,
    ProfileMaterialCapabilityRepository,
    ProfileSectionCompletenessRepository,
    ProfileTechnologyCapabilityRepository,
    ReferenceRepository,
)

NO_ASSERTION: Final = "NO_ASSERTION"
type CapabilityResolution = CapabilityState | Literal["NO_ASSERTION"]


class ProfileCapabilityService:
    def __init__(
        self,
        session: AsyncSession,
        technology_repository: ProfileTechnologyCapabilityRepository,
        material_capability_repository: ProfileMaterialCapabilityRepository,
        section_repository: ProfileSectionCompletenessRepository,
        enterprise_repository: EnterpriseProfileRepository,
        reference_repository: ReferenceRepository,
        material_repository: MaterialRepository,
    ):
        self.session = session
        self.technology_repository = technology_repository
        self.material_capability_repository = material_capability_repository
        self.section_repository = section_repository
        self.enterprise_repository = enterprise_repository
        self.reference_repository = reference_repository
        self.material_repository = material_repository

    async def _require_profile(self, profile_id: int) -> None:
        if await self.enterprise_repository.get_by_id(profile_id) is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

    async def _require_technology(self, technology_code: str) -> None:
        technology = await self.reference_repository.get_technology_type_by_code(
            technology_code
        )
        if technology is None:
            raise TechnologyTypeNotFoundError(
                f"Technology type {technology_code} not found."
            )

    async def _require_material_group(self, group_code: str) -> None:
        material_group = await self.reference_repository.get_material_group_by_code(
            group_code
        )
        if material_group is None:
            raise MaterialGroupNotFoundError(
                f"Material group {group_code} not found."
            )

    async def _require_material(self, material_id: int) -> Material:
        material = await self.material_repository.get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(f"Material {material_id} not found.")
        return material

    async def _require_section(
        self,
        profile_id: int,
        section_code: ProfileSectionCode,
    ) -> ProfileSectionCompleteness:
        completeness = await self.section_repository.get(profile_id, section_code)
        if completeness is None:
            raise CapabilitySectionIntegrityError(
                f"Required section {section_code} is missing for profile {profile_id}."
            )
        return completeness

    async def _invalidate_and_commit(
        self,
        profile_id: int,
        section_code: ProfileSectionCode,
    ) -> None:
        completeness = await self._require_section(profile_id, section_code)
        await self.section_repository.invalidate(completeness)
        await self.session.commit()

    async def list_technology_capabilities(
        self,
        profile_id: int,
    ) -> list[ProfileTechnologyCapability]:
        await self._require_profile(profile_id)
        return await self.technology_repository.list_for_profile(profile_id)

    async def put_technology_capability(
        self,
        profile_id: int,
        technology_code: str,
        state: CapabilityState,
    ) -> ProfileTechnologyCapability:
        await self._require_profile(profile_id)
        await self._require_technology(technology_code)
        existing = await self.technology_repository.get(profile_id, technology_code)

        if existing is not None and existing.state == state:
            return existing

        try:
            if existing is None:
                capability = await self.technology_repository.create(
                    profile_id,
                    technology_code,
                    state,
                )
            else:
                capability = await self.technology_repository.update_state(
                    existing,
                    state,
                )
            await self._invalidate_and_commit(
                profile_id,
                ProfileSectionCode.TECHNOLOGIES,
            )
        except Exception:
            await self.session.rollback()
            raise

        return capability

    async def delete_technology_capability(
        self,
        profile_id: int,
        technology_code: str,
    ) -> None:
        await self._require_profile(profile_id)
        existing = await self.technology_repository.get(profile_id, technology_code)
        if existing is None:
            return

        try:
            await self.technology_repository.delete(existing)
            await self._invalidate_and_commit(
                profile_id,
                ProfileSectionCode.TECHNOLOGIES,
            )
        except Exception:
            await self.session.rollback()
            raise

    async def resolve_technology_capability(
        self,
        profile_id: int,
        technology_code: str,
    ) -> CapabilityResolution:
        await self._require_profile(profile_id)
        await self._require_technology(technology_code)
        capability = await self.technology_repository.get(
            profile_id,
            technology_code,
        )
        if capability is None:
            return NO_ASSERTION
        return CapabilityState(capability.state)

    async def list_material_capabilities(
        self,
        profile_id: int,
    ) -> list[ProfileMaterialCapability]:
        await self._require_profile(profile_id)
        return await self.material_capability_repository.list_for_profile(profile_id)

    async def put_material_group_capability(
        self,
        profile_id: int,
        group_code: str,
        state: CapabilityState,
    ) -> ProfileMaterialCapability:
        await self._require_profile(profile_id)
        await self._require_material_group(group_code)
        existing = await self.material_capability_repository.get_group(
            profile_id,
            group_code,
        )
        if existing is not None and existing.state == state:
            return existing

        try:
            if existing is None:
                capability = await self.material_capability_repository.create_group(
                    profile_id,
                    group_code,
                    state,
                )
            else:
                capability = await self.material_capability_repository.update_state(
                    existing,
                    state,
                )
            await self._invalidate_and_commit(
                profile_id,
                ProfileSectionCode.MATERIALS,
            )
        except Exception:
            await self.session.rollback()
            raise

        return capability

    async def delete_material_group_capability(
        self,
        profile_id: int,
        group_code: str,
    ) -> None:
        await self._require_profile(profile_id)
        existing = await self.material_capability_repository.get_group(
            profile_id,
            group_code,
        )
        if existing is None:
            return

        try:
            await self.material_capability_repository.delete(existing)
            await self._invalidate_and_commit(
                profile_id,
                ProfileSectionCode.MATERIALS,
            )
        except Exception:
            await self.session.rollback()
            raise

    async def put_material_capability(
        self,
        profile_id: int,
        material_id: int,
        state: CapabilityState,
    ) -> ProfileMaterialCapability:
        await self._require_profile(profile_id)
        await self._require_material(material_id)
        existing = await self.material_capability_repository.get_material(
            profile_id,
            material_id,
        )
        if existing is not None and existing.state == state:
            return existing

        try:
            if existing is None:
                capability = await self.material_capability_repository.create_material(
                    profile_id,
                    material_id,
                    state,
                )
            else:
                capability = await self.material_capability_repository.update_state(
                    existing,
                    state,
                )
            await self._invalidate_and_commit(
                profile_id,
                ProfileSectionCode.MATERIALS,
            )
        except Exception:
            await self.session.rollback()
            raise

        return capability

    async def delete_material_capability(
        self,
        profile_id: int,
        material_id: int,
    ) -> None:
        await self._require_profile(profile_id)
        existing = await self.material_capability_repository.get_material(
            profile_id,
            material_id,
        )
        if existing is None:
            return

        try:
            await self.material_capability_repository.delete(existing)
            await self._invalidate_and_commit(
                profile_id,
                ProfileSectionCode.MATERIALS,
            )
        except Exception:
            await self.session.rollback()
            raise

    async def resolve_material_capability(
        self,
        profile_id: int,
        material_id: int,
    ) -> CapabilityResolution:
        await self._require_profile(profile_id)
        material = await self._require_material(material_id)
        specific = await self.material_capability_repository.get_material(
            profile_id,
            material_id,
        )
        if specific is not None:
            return CapabilityState(specific.state)

        group = await self.material_capability_repository.get_group(
            profile_id,
            material.group_code,
        )
        if group is not None:
            return CapabilityState(group.state)
        return NO_ASSERTION

    async def resolve_material_group_capability(
        self,
        profile_id: int,
        group_code: str,
    ) -> CapabilityResolution:
        await self._require_profile(profile_id)
        await self._require_material_group(group_code)
        group = await self.material_capability_repository.get_group(
            profile_id,
            group_code,
        )
        if group is None:
            return NO_ASSERTION
        return CapabilityState(group.state)

    async def list_sections(
        self,
        profile_id: int,
    ) -> list[ProfileSectionCompleteness]:
        await self._require_profile(profile_id)
        sections = await self.section_repository.list_for_profile(profile_id)
        actual_codes = {
            ProfileSectionCode(section.section_code) for section in sections
        }
        if actual_codes != set(ProfileSectionCode):
            raise CapabilitySectionIntegrityError(
                f"Required capability sections are missing for profile {profile_id}."
            )
        return sections

    async def set_section_state(
        self,
        profile_id: int,
        section_code: ProfileSectionCode,
        state: ProfileSectionState,
    ) -> ProfileSectionCompleteness:
        await self._require_profile(profile_id)
        if state == ProfileSectionState.CONFIRMED_COMPLETE:
            raise ValueError(
                "CONFIRMED_COMPLETE is allowed only through confirmation."
            )
        completeness = await self._require_section(profile_id, section_code)
        if completeness.state == state:
            return completeness

        try:
            completeness = await self.section_repository.set_state(
                completeness,
                state,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return completeness

    async def confirm_section(
        self,
        profile_id: int,
        section_code: ProfileSectionCode,
        confirmed_by: str,
    ) -> ProfileSectionCompleteness:
        await self._require_profile(profile_id)
        completeness = await self._require_section(profile_id, section_code)
        confirmed_by = confirmed_by.strip()
        if not 1 <= len(confirmed_by) <= 128:
            raise ValueError("Confirmer must be between 1 and 128 characters.")
        confirmed_at = datetime.now(UTC)
        if completeness.confirmed_at is not None:
            previous = completeness.confirmed_at
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=UTC)
            if confirmed_at <= previous:
                confirmed_at = previous + timedelta(microseconds=1)

        try:
            completeness = await self.section_repository.confirm(
                completeness,
                confirmed_by,
                confirmed_at,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return completeness
