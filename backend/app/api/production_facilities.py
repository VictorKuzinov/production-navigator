from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_facility_service
from app.api.error_responses import error_responses
from app.schemas import (
    ProductionFacilityCreate,
    ProductionFacilityRead,
    ProductionFacilityUpdate,
)
from app.services.production_facilities import ProductionFacilityService

router = APIRouter(
    tags=["ProductionFacilities"],
)


ProductionFacilityDep = Annotated[
    ProductionFacilityService,
    Depends(get_facility_service),
]


@router.get(
    "/enterprises/{profile_id}/facilities",
    response_model=list[ProductionFacilityRead],
    responses=error_responses(404),
)
async def list_facilities(
    profile_id: int,
    service: ProductionFacilityDep,
):
    return await service.list_by_profile(profile_id)


@router.post(
    "/enterprises/{profile_id}/facilities",
    response_model=ProductionFacilityRead,
    responses=error_responses(404),
)
async def create_facility(
    profile_id: int,
    facility: ProductionFacilityCreate,
    service: ProductionFacilityDep,
):
    return await service.create(profile_id, facility)


@router.get(
    "/facilities/{facility_id}",
    response_model=ProductionFacilityRead,
    responses=error_responses(404),
)
async def get_facility(
    facility_id: int,
    service: ProductionFacilityDep,
):
    return await service.get_by_id(facility_id)


@router.patch(
    "/facilities/{facility_id}",
    response_model=ProductionFacilityRead,
    responses=error_responses(404),
)
async def update_facility(
    facility_id: int,
    facility: ProductionFacilityUpdate,
    service: ProductionFacilityDep,
):
    return await service.update(facility_id, facility)


@router.delete(
    "/facilities/{facility_id}",
    response_model=ProductionFacilityRead,
    responses=error_responses(404),
)
async def delete_facility(
    facility_id: int,
    service: ProductionFacilityDep,
):
    return await service.delete(facility_id)
