from app.core.exceptions import (
    CraneTypeNotFoundError,
    EnterpriseProfileNotFoundError,
    LiftingEquipmentNotFoundError,
    ProductionFacilityNotFoundError,
    WarehouseNotFoundError,
)
from app.models import LiftingEquipment
from app.repositories import (
    EnterpriseProfileRepository,
    LiftingEquipmentRepository,
    ProductionFacilityRepository,
    ReferenceRepository,
    WarehouseRepository,
)
from app.schemas import LiftingEquipmentCreate, LiftingEquipmentUpdate


class LiftingEquipmentService:
    def __init__(
        self,
        repository: LiftingEquipmentRepository,
        enterprise_repository: EnterpriseProfileRepository,
        facility_repository: ProductionFacilityRepository,
        warehouse_repository: WarehouseRepository,
        reference_repository: ReferenceRepository,
    ):
        self.repository = repository
        self.enterprise_repository = enterprise_repository
        self.facility_repository = facility_repository
        self.warehouse_repository = warehouse_repository
        self.reference_repository = reference_repository

    async def _validate_facility(
        self,
        profile_id: int,
        facility_id: int,
    ) -> None:
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

    async def _validate_warehouse(
        self,
        profile_id: int,
        warehouse_id: int,
    ) -> None:
        warehouse = await self.warehouse_repository.get_by_id(warehouse_id)
        if warehouse is None:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found.")

        if warehouse.profile_id != profile_id:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found "
                f"for enterprise profile {profile_id}."
            )

    async def _validate_crane_type(self, crane_type_code: str) -> None:
        crane_type = await self.reference_repository.get_crane_type_by_code(
            crane_type_code
        )
        if crane_type is None:
            raise CraneTypeNotFoundError(f"Crane type {crane_type_code} not found.")

    async def get_by_id(
        self,
        lifting_equipment_id: int,
    ) -> LiftingEquipment:
        lifting_equipment = await self.repository.get_by_id(lifting_equipment_id)
        if lifting_equipment is None:
            raise LiftingEquipmentNotFoundError(
                f"Lifting equipment {lifting_equipment_id} not found."
            )

        return lifting_equipment

    async def list_by_profile(
        self,
        profile_id: int,
    ) -> list[LiftingEquipment]:
        profile = await self.enterprise_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        return await self.repository.list_by_profile(profile_id)

    async def create(
        self,
        profile_id: int,
        data: LiftingEquipmentCreate,
    ) -> LiftingEquipment:
        profile = await self.enterprise_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        if data.facility_id is not None:
            await self._validate_facility(profile_id, data.facility_id)
        if data.warehouse_id is not None:
            await self._validate_warehouse(profile_id, data.warehouse_id)
        await self._validate_crane_type(data.crane_type_code)

        return await self.repository.create(profile_id, data)

    async def update(
        self,
        lifting_equipment_id: int,
        data: LiftingEquipmentUpdate,
    ) -> LiftingEquipment:
        lifting_equipment = await self.repository.get_by_id(lifting_equipment_id)
        if lifting_equipment is None:
            raise LiftingEquipmentNotFoundError(
                f"Lifting equipment {lifting_equipment_id} not found."
            )

        if "facility_id" in data.model_fields_set and data.facility_id is not None:
            await self._validate_facility(
                lifting_equipment.profile_id,
                data.facility_id,
            )
        if "warehouse_id" in data.model_fields_set and data.warehouse_id is not None:
            await self._validate_warehouse(
                lifting_equipment.profile_id,
                data.warehouse_id,
            )
        if (
            "crane_type_code" in data.model_fields_set
            and data.crane_type_code is not None
        ):
            await self._validate_crane_type(data.crane_type_code)

        updated = await self.repository.update(lifting_equipment_id, data)
        if updated is None:
            raise LiftingEquipmentNotFoundError(
                f"Lifting equipment {lifting_equipment_id} not found."
            )

        return updated

    async def delete(
        self,
        lifting_equipment_id: int,
    ) -> LiftingEquipment:
        lifting_equipment = await self.repository.get_by_id(lifting_equipment_id)
        if lifting_equipment is None:
            raise LiftingEquipmentNotFoundError(
                f"Lifting equipment {lifting_equipment_id} not found."
            )

        deleted = await self.repository.delete(lifting_equipment_id)
        if deleted is None:
            raise LiftingEquipmentNotFoundError(
                f"Lifting equipment {lifting_equipment_id} not found."
            )

        return deleted
