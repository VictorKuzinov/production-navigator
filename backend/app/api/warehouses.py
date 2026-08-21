from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_warehouse_service
from app.schemas import WarehouseCreate, WarehouseRead, WarehouseUpdate
from app.services.warehouses import WarehouseService

router = APIRouter(
    tags=["Warehouses"],
)

WarehouseDep = Annotated[
    WarehouseService,
    Depends(get_warehouse_service),
]


@router.get(
    "/enterprises/{profile_id}/warehouses",
    response_model=list[WarehouseRead],
)
async def list_warehouses(
    profile_id: int,
    service: WarehouseDep,
):
    return await service.list_warehouses(profile_id)


@router.post(
    "/enterprises/{profile_id}/warehouses",
    response_model=WarehouseRead,
)
async def create_warehouse(
    profile_id: int,
    warehouse: WarehouseCreate,
    service: WarehouseDep,
):
    return await service.create_warehouse(profile_id, warehouse)


@router.get(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseRead,
)
async def get_warehouse(
    warehouse_id: int,
    service: WarehouseDep,
):
    return await service.get_warehouse(warehouse_id)


@router.patch(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseRead,
)
async def update_warehouse(
    warehouse_id: int,
    warehouse: WarehouseUpdate,
    service: WarehouseDep,
):
    return await service.update_warehouse(warehouse_id, warehouse)


@router.delete(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseRead,
)
async def delete_warehouse(
    warehouse_id: int,
    service: WarehouseDep,
):
    return await service.delete_warehouse(warehouse_id)
