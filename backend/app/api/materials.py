from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_material_service
from app.schemas import MaterialCreate, MaterialRead, MaterialUpdate
from app.services.materials import MaterialService

router = APIRouter(
    prefix="/materials",
    tags=["Materials"],
)

MaterialDep = Annotated[
    MaterialService,
    Depends(get_material_service),
]


@router.get(
    "",
    response_model=list[MaterialRead],
)
async def list_materials(service: MaterialDep):
    return await service.list_materials()


@router.post(
    "",
    response_model=MaterialRead,
)
async def create_material(
    material: MaterialCreate,
    service: MaterialDep,
):
    return await service.create_material(material)


@router.get(
    "/{material_id}",
    response_model=MaterialRead,
)
async def get_material(
    material_id: int,
    service: MaterialDep,
):
    return await service.get_material(material_id)


@router.patch(
    "/{material_id}",
    response_model=MaterialRead,
)
async def update_material(
    material_id: int,
    material: MaterialUpdate,
    service: MaterialDep,
):
    return await service.update_material(material_id, material)


@router.delete(
    "/{material_id}",
    response_model=MaterialRead,
)
async def delete_material(
    material_id: int,
    service: MaterialDep,
):
    return await service.delete_material(material_id)
