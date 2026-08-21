from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    EquipmentNotFoundError,
    EquipmentTypeNotFoundError,
    ProductionFacilityNotFoundError,
)
from app.models import Equipment
from app.repositories import (
    EnterpriseProfileRepository,
    EquipmentRepository,
    ProductionFacilityRepository,
    ReferenceRepository,
)
from app.schemas import EquipmentCreate, EquipmentUpdate


class EquipmentService:
    def __init__(
        self,
        repository: EquipmentRepository,
        enterprise_repository: EnterpriseProfileRepository,
        facility_repository: ProductionFacilityRepository,
        reference_repository: ReferenceRepository,
    ):
        self.repository = repository
        self.enterprise_repository = enterprise_repository
        self.facility_repository = facility_repository
        self.reference_repository = reference_repository

    async def get_by_id(
        self,
        equipment_id: int,
    ) -> Equipment:
        equipment = await self.repository.get_by_id(equipment_id)

        if equipment is None:
            raise EquipmentNotFoundError(
                f"Equipment {equipment_id} not found."
            )

        return equipment

    async def list_by_facility(
        self,
        profile_id: int,
        facility_id: int,
    ) -> list[Equipment]:
        profile = await self.enterprise_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        facility = await self.facility_repository.get_by_id(facility_id)
        if facility is None:
            raise ProductionFacilityNotFoundError(
                f"Production facility {facility_id} not found."
            )

        if facility.profile_id != profile_id:
            raise ProductionFacilityNotFoundError(
                f"Production facility {facility_id} not found "
                f"for enterprise profile {profile_id}."
            )

        return await self.repository.list_by_facility(
            profile_id=profile_id,
            facility_id=facility_id,
        )


    async def create(
        self,
        profile_id: int,
        facility_id: int,
        data: EquipmentCreate,
    ) -> Equipment:

        profile = await self.enterprise_repository.get_by_id(profile_id)

        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )
        
        facility = await self.facility_repository.get_by_id(facility_id)
        if facility is None:
            raise ProductionFacilityNotFoundError(
                f"Production facility {facility_id} not found."
            )

        if facility.profile_id != profile_id:
            raise ProductionFacilityNotFoundError(
                f"Production facility {facility_id} not found "
                f"for enterprise profile {profile_id}."
            )

        equipment_type = await self.reference_repository.get_equipment_type_by_code(
            data.equipment_type_code
        )

        if equipment_type is None:
            raise EquipmentTypeNotFoundError(
                f"Equipment type {data.equipment_type_code} not found."
            )

        return await self.repository.create(
            profile_id=profile_id,
            facility_id=facility_id,
            data=data,
        )

    async def update(
        self,
        equipment_id: int,
        data: EquipmentUpdate,
    ) -> Equipment:

        equipment = await self.repository.get_by_id(equipment_id)

        if equipment is None:
            raise EquipmentNotFoundError(
                f"Equipment {equipment_id} not found."
            )

        if data.equipment_type_code is not None:
            equipment_type = await self.reference_repository.get_equipment_type_by_code(
                data.equipment_type_code
            )

            if equipment_type is None:
                raise EquipmentTypeNotFoundError(
                    f"Equipment type {data.equipment_type_code} not found."
                )

        return await self.repository.update(
            equipment_id,
            data,
        )

    async def delete(
            self,
            equipment_id: int,
    ) -> Equipment:

        equipment = await self.repository.get_by_id(equipment_id)

        if equipment is None:
            raise EquipmentNotFoundError(
                f"Equipment {equipment_id} not found."
            )

        return await self.repository.delete(
            equipment_id,
        )