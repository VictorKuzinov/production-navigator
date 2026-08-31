from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_enterprise_service
from app.api.error_responses import error_responses
from app.schemas import (
    EnterpriseProfileCreate,
    EnterpriseProfileRead,
    EnterpriseProfileUpdate,
)
from app.services.enterprises import EnterpriseProfileService

router = APIRouter(
    prefix="/enterprises",
    tags=["Enterprises"],
)

EnterpriseServiceDep = Annotated[
    EnterpriseProfileService,
    Depends(get_enterprise_service),
]

@router.get(
    "",
    response_model=list[EnterpriseProfileRead],
)
async def list_profiles(
    service: EnterpriseServiceDep,
):
    return await service.list_profiles()

@router.get(
    "/{profile_id}",
    response_model=EnterpriseProfileRead,
    responses=error_responses(404),
)
async def get_profile(
    profile_id: int,
    service: EnterpriseServiceDep,
):
    return await service.get_by_id(profile_id)

@router.post(
    "",
    response_model=EnterpriseProfileRead,
)
async def create_profile(
        profile: EnterpriseProfileCreate,
        service: EnterpriseServiceDep,
):
    return await service.create(profile)

@router.patch(
    "/{profile_id}",
    response_model=EnterpriseProfileRead,
    responses=error_responses(404),
)
async def update_profile(
        profile_id: int,
        profile: EnterpriseProfileUpdate,
        service: EnterpriseServiceDep,
):
    return await service.update(profile_id, profile)

@router.delete(
    "/{profile_id}",
    response_model=EnterpriseProfileRead,
    responses=error_responses(404),
)
async def delete_profile(
        profile_id: int,
        service: EnterpriseServiceDep,
):
    return await service.delete(profile_id)
