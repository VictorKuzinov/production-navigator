from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    ProductionFacilityNotFoundError,
)
from app.models import ProductionFacility
from app.repositories import EnterpriseProfileRepository
from app.repositories.production_facilities import ProductionFacilityRepository
from app.schemas import ProductionFacilityCreate, ProductionFacilityUpdate


class ProductionFacilityService:

    def __init__(
        self,
        repository: ProductionFacilityRepository,
        enterprise_repository: EnterpriseProfileRepository,
    ):
        self.repository = repository
        self.enterprise_repository = enterprise_repository

    async def get_by_id(
            self,
            facility_id: int,
    ) -> ProductionFacility:
        facility = await self.repository.get_by_id(facility_id)

        if facility is None:
            raise ProductionFacilityNotFoundError(
                f"Production facility {facility_id} not found."
            )

        return facility

    async def list_by_profile(
        self,
        profile_id: int,
    ) -> list[ProductionFacility]:
        profile = await self.enterprise_repository.get_by_id(profile_id)

        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        return await self.repository.list_by_profile(
            profile_id=profile_id,
        )

    async def create(
        self,
        profile_id: int,
        data: ProductionFacilityCreate,
    ) -> ProductionFacility:
        profile = await self.enterprise_repository.get_by_id(profile_id)

        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        return await self.repository.create(
            profile_id=profile_id,
            data=data,
        )

    async def update(
        self,
        facility_id: int,
        data: ProductionFacilityUpdate,
    ) -> ProductionFacility | None:
        facility = await self.repository.get_by_id(facility_id)

        if facility is None:
            raise ProductionFacilityNotFoundError(
                f"Production facility {facility_id} not found."
            )

        return await self.repository.update(
            facility_id,
            data,
        )

    async def delete(
            self,
            facility_id: int,):

        facility = await self.repository.get_by_id(facility_id)

        if facility is None:
            raise ProductionFacilityNotFoundError(
                f"Production facility {facility_id} not found."
            )

        return await self.repository.delete(
            facility_id,
        )
