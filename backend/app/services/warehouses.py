from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    WarehouseNotFoundError,
    WarehouseTypeNotFoundError,
)
from app.models import Warehouse
from app.repositories import (
    EnterpriseProfileRepository,
    ReferenceRepository,
    WarehouseRepository,
)
from app.schemas import WarehouseCreate, WarehouseUpdate


class WarehouseService:
    def __init__(
        self,
        repository: WarehouseRepository,
        enterprise_repository: EnterpriseProfileRepository,
        reference_repository: ReferenceRepository,
    ):
        self.repository = repository
        self.enterprise_repository = enterprise_repository
        self.reference_repository = reference_repository

    async def get_warehouse(
        self,
        warehouse_id: int,
    ) -> Warehouse:
        warehouse = await self.repository.get_by_id(warehouse_id)

        if warehouse is None:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found."
            )

        return warehouse

    async def list_warehouses(
        self,
        profile_id: int,
    ) -> list[Warehouse]:
        profile = await self.enterprise_repository.get_by_id(profile_id)

        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        return await self.repository.list_by_profile(profile_id)

    async def create_warehouse(
        self,
        profile_id: int,
        data: WarehouseCreate,
    ) -> Warehouse:
        profile = await self.enterprise_repository.get_by_id(profile_id)

        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        warehouse_type = (
            await self.reference_repository.get_warehouse_type_by_code(
                data.warehouse_type_code
            )
        )

        if warehouse_type is None:
            raise WarehouseTypeNotFoundError(
                f"Warehouse type {data.warehouse_type_code} not found."
            )

        return await self.repository.create(
            profile_id=profile_id,
            data=data,
        )

    async def update_warehouse(
        self,
        warehouse_id: int,
        data: WarehouseUpdate,
    ) -> Warehouse:
        warehouse = await self.repository.get_by_id(warehouse_id)

        if warehouse is None:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found."
            )

        if (
            "warehouse_type_code" in data.model_fields_set
            and data.warehouse_type_code is not None
        ):
            warehouse_type = (
                await self.reference_repository.get_warehouse_type_by_code(
                    data.warehouse_type_code
                )
            )

            if warehouse_type is None:
                raise WarehouseTypeNotFoundError(
                    f"Warehouse type {data.warehouse_type_code} not found."
                )

        updated_warehouse = await self.repository.update(warehouse_id, data)

        if updated_warehouse is None:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found."
            )

        return updated_warehouse

    async def delete_warehouse(
        self,
        warehouse_id: int,
    ) -> Warehouse:
        warehouse = await self.repository.get_by_id(warehouse_id)

        if warehouse is None:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found."
            )

        deleted_warehouse = await self.repository.delete(warehouse_id)

        if deleted_warehouse is None:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found."
            )

        return deleted_warehouse
