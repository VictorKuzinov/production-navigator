from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_lifting_equipment_service
from app.schemas import (
    LiftingEquipmentCreate,
    LiftingEquipmentRead,
    LiftingEquipmentUpdate,
)
from app.services.lifting_equipments import LiftingEquipmentService

router = APIRouter(tags=["LiftingEquipment"])

LiftingEquipmentDep = Annotated[
    LiftingEquipmentService,
    Depends(get_lifting_equipment_service),
]


@router.get(
    "/enterprises/{profile_id}/lifting-equipment",
    response_model=list[LiftingEquipmentRead],
)
async def list_lifting_equipment(
    profile_id: int,
    service: LiftingEquipmentDep,
):
    return await service.list_by_profile(profile_id)


@router.post(
    "/enterprises/{profile_id}/lifting-equipment",
    response_model=LiftingEquipmentRead,
)
async def create_lifting_equipment(
    profile_id: int,
    lifting_equipment: LiftingEquipmentCreate,
    service: LiftingEquipmentDep,
):
    return await service.create(profile_id, lifting_equipment)


@router.get(
    "/lifting-equipment/{lifting_equipment_id}",
    response_model=LiftingEquipmentRead,
)
async def get_lifting_equipment(
    lifting_equipment_id: int,
    service: LiftingEquipmentDep,
):
    return await service.get_by_id(lifting_equipment_id)


@router.patch(
    "/lifting-equipment/{lifting_equipment_id}",
    response_model=LiftingEquipmentRead,
)
async def update_lifting_equipment(
    lifting_equipment_id: int,
    lifting_equipment: LiftingEquipmentUpdate,
    service: LiftingEquipmentDep,
):
    return await service.update(lifting_equipment_id, lifting_equipment)


@router.delete(
    "/lifting-equipment/{lifting_equipment_id}",
    response_model=LiftingEquipmentRead,
)
async def delete_lifting_equipment(
    lifting_equipment_id: int,
    service: LiftingEquipmentDep,
):
    return await service.delete(lifting_equipment_id)
