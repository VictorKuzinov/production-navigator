from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_material_item_service
from app.schemas import MaterialItemCreate, MaterialItemRead, MaterialItemUpdate
from app.services.material_items import MaterialItemService

router = APIRouter(
    prefix="/material-items",
    tags=["Material Items"],
)

MaterialItemDep = Annotated[
    MaterialItemService,
    Depends(get_material_item_service),
]


@router.get(
    "",
    response_model=list[MaterialItemRead],
)
async def list_material_items(service: MaterialItemDep):
    return await service.list_material_items()


@router.post(
    "",
    response_model=MaterialItemRead,
)
async def create_material_item(
    material_item: MaterialItemCreate,
    service: MaterialItemDep,
):
    return await service.create_material_item(material_item)


@router.get(
    "/{material_item_id}",
    response_model=MaterialItemRead,
)
async def get_material_item(
    material_item_id: int,
    service: MaterialItemDep,
):
    return await service.get_material_item(material_item_id)


@router.patch(
    "/{material_item_id}",
    response_model=MaterialItemRead,
)
async def update_material_item(
    material_item_id: int,
    material_item: MaterialItemUpdate,
    service: MaterialItemDep,
):
    return await service.update_material_item(material_item_id, material_item)


@router.delete(
    "/{material_item_id}",
    response_model=MaterialItemRead,
)
async def delete_material_item(
    material_item_id: int,
    service: MaterialItemDep,
):
    return await service.delete_material_item(material_item_id)
