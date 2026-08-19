from app.core.exceptions import (
    CompanySizeNotFoundError,
    DuplicateInnError,
    DuplicateOgrnError,
    EnterpriseProfileNotFoundError,
    RegionNotFoundError,
)
from app.models import EnterpriseProfile
from app.repositories import EnterpriseProfileRepository, ReferenceRepository
from app.schemas import EnterpriseProfileCreate, EnterpriseProfileUpdate


class EnterpriseProfileService:
    def __init__(
            self,
            repository: EnterpriseProfileRepository,
            reference_repository: ReferenceRepository,
    ):
        self.repository = repository
        self.reference_repository = reference_repository

    async def get_by_id(
            self,
            profile_id: int,
    ) -> EnterpriseProfile:
        profile = await self.repository.get_by_id(profile_id)

        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        return profile

    async def list_profiles(
            self,
            offset: int = 0,
            limit: int = 100,
    ) -> list[EnterpriseProfile]:

        return await self.repository.list_profiles(
            offset=offset,
            limit=limit,
        )

    async def create(
            self,
            data: EnterpriseProfileCreate,
    ) -> EnterpriseProfile:

        if data.inn is not None:
            existing = await self.repository.get_by_inn(data.inn)
            if existing is not None:
                raise DuplicateInnError(
                    f"Duplicate INN {data.inn}."
                )

        if data.ogrn is not None:
            existing = await self.repository.get_by_ogrn(data.ogrn)
            if existing is not None:
                raise DuplicateOgrnError(
                    f"Duplicate OGRN {data.ogrn}."
                )

        if data.region_code is not None:
            region = await (self.reference_repository.
            get_region_by_code(
                data.region_code
            ))
            if region is None:
                raise RegionNotFoundError(
                    f"Region code {data.region_code} not found."
                )

        if data.company_size_code is not None:
            company_size = (
                await self.reference_repository.get_company_size_by_code(
                    data.company_size_code
                )
            )
            if company_size is None:
                raise CompanySizeNotFoundError(
                    f"Company size code {data.company_size_code} not found."
                )

        return await self.repository.create(data)

    async def update(
            self,
            profile_id: int,
            data: EnterpriseProfileUpdate,
    ) -> EnterpriseProfile:

        await self.get_by_id(profile_id)

        if data.inn is not None:
            existing = await self.repository.get_by_inn(data.inn)
            if existing is not None and existing.id != profile_id:
                raise DuplicateInnError(
                    f"Duplicate INN {data.inn}."
                )

        if data.ogrn is not None:
            existing = await self.repository.get_by_ogrn(data.ogrn)
            if existing is not None and existing.id != profile_id:
                raise DuplicateOgrnError(
                    f"Duplicate OGRN {data.ogrn}."
                )

        if data.region_code is not None:
            region = await self.reference_repository.get_region_by_code(
                data.region_code
            )
            if region is None:
                raise RegionNotFoundError(
                    f"Region code {data.region_code} not found."
                )

        if data.company_size_code is not None:
            company_size = (
                await self.reference_repository.get_company_size_by_code(
                    data.company_size_code
                )
            )
            if company_size is None:
                raise CompanySizeNotFoundError(
                    f"Company size code {data.company_size_code} not found."
                )

        return await self.repository.update(
            profile_id,
            data,
        )

    async def delete(
            self,
            profile_id: int,
    ) -> EnterpriseProfile | None:

        await self.get_by_id(profile_id)

        return await self.repository.delete(profile_id)

