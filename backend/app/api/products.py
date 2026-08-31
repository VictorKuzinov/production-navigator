from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_product_service
from app.api.error_responses import error_responses
from app.schemas import ProductCreate, ProductRead, ProductUpdate
from app.services.products import ProductService

router = APIRouter(
    tags=["Products"],
)

ProductDep = Annotated[
    ProductService,
    Depends(get_product_service),
]


@router.get(
    "/enterprises/{profile_id}/products",
    response_model=list[ProductRead],
    responses=error_responses(404),
)
async def list_products(
    profile_id: int,
    service: ProductDep,
):
    return await service.list_products(profile_id)


@router.post(
    "/enterprises/{profile_id}/products",
    response_model=ProductRead,
    responses=error_responses(404, 409),
)
async def create_product(
    profile_id: int,
    product: ProductCreate,
    service: ProductDep,
):
    return await service.create_product(profile_id, product)


@router.get(
    "/products/{product_id}",
    response_model=ProductRead,
    responses=error_responses(404),
)
async def get_product(
    product_id: int,
    service: ProductDep,
):
    return await service.get_product(product_id)


@router.patch(
    "/products/{product_id}",
    response_model=ProductRead,
    responses=error_responses(404, 409),
)
async def update_product(
    product_id: int,
    product: ProductUpdate,
    service: ProductDep,
):
    return await service.update_product(product_id, product)


@router.delete(
    "/products/{product_id}",
    response_model=ProductRead,
    responses=error_responses(404, 409),
)
async def delete_product(
    product_id: int,
    service: ProductDep,
):
    return await service.delete_product(product_id)
