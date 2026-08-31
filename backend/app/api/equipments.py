from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_equipment_service
from app.api.error_responses import error_responses
from app.schemas import (
    EquipmentCreate,
    EquipmentRead,
    EquipmentUpdate,
)
from app.services.equipments import EquipmentService

router = APIRouter(
    tags=["Equipment"],
)

EquipmentDep = Annotated[
    EquipmentService,
    Depends(get_equipment_service),
]

@router.get(
    "/enterprises/{profile_id}/facilities/{facility_id}/equipment",
    response_model=list[EquipmentRead],
    responses=error_responses(404),
)
async def list_equipments(
    profile_id: int,
    facility_id: int,
    service: EquipmentDep,
):
    return await service.list_by_facility(
        profile_id,
        facility_id,
    )

@router.post(
    "/enterprises/{profile_id}/facilities/{facility_id}/equipment",
    response_model=EquipmentRead,
    responses=error_responses(404),
)
async def create_equipment(
    profile_id: int,
    facility_id: int,
    equipment: EquipmentCreate,
    service: EquipmentDep,
):
    return await service.create(
        profile_id,
        facility_id,
        equipment,
    )

@router.get(
    "/equipment/{equipment_id}",
    response_model=EquipmentRead,
    responses=error_responses(404),
)
async def get_equipment(
    equipment_id: int,
    service: EquipmentDep,
):
    return await service.get_by_id(
        equipment_id
    )

@router.patch(
    "/equipment/{equipment_id}",
    response_model=EquipmentRead,
    responses=error_responses(404),
)
async def patch_equipment(
    equipment_id: int,
    equipment: EquipmentUpdate,
    service: EquipmentDep,
):
    return await service.update(
        equipment_id,
        equipment,
    )

@router.delete(
    "/equipment/{equipment_id}",
    response_model=EquipmentRead,
    responses=error_responses(404),
)
async def delete_equipment( 
    equipment_id: int,
    service: EquipmentDep,
):
    return await service.delete(
        equipment_id
    )
