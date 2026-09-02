from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_profile_capability_service
from app.api.error_responses import error_responses
from app.models.profile_capabilities import ProfileSectionCode
from app.schemas.profile_capabilities import (
    CapabilityStateUpdate,
    ProfileMaterialCapabilityRead,
    ProfileSectionCompletenessRead,
    ProfileSectionConfirmation,
    ProfileSectionStateUpdate,
    ProfileTechnologyCapabilityRead,
)
from app.services.profile_capabilities import ProfileCapabilityService

router = APIRouter(
    prefix="/enterprises/{profile_id}",
    tags=["Profile capabilities"],
)

ProfileCapabilityServiceDep = Annotated[
    ProfileCapabilityService,
    Depends(get_profile_capability_service),
]


@router.get(
    "/technology-capabilities",
    response_model=list[ProfileTechnologyCapabilityRead],
    responses=error_responses(404),
)
async def list_technology_capabilities(
    profile_id: int,
    service: ProfileCapabilityServiceDep,
):
    return await service.list_technology_capabilities(profile_id)


@router.put(
    "/technology-capabilities/{technology_code}",
    response_model=ProfileTechnologyCapabilityRead,
    responses=error_responses(404),
)
async def put_technology_capability(
    profile_id: int,
    technology_code: str,
    payload: CapabilityStateUpdate,
    service: ProfileCapabilityServiceDep,
):
    return await service.put_technology_capability(
        profile_id,
        technology_code,
        payload.state,
    )


@router.delete(
    "/technology-capabilities/{technology_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404),
)
async def delete_technology_capability(
    profile_id: int,
    technology_code: str,
    service: ProfileCapabilityServiceDep,
) -> Response:
    await service.delete_technology_capability(profile_id, technology_code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/material-capabilities",
    response_model=list[ProfileMaterialCapabilityRead],
    responses=error_responses(404),
)
async def list_material_capabilities(
    profile_id: int,
    service: ProfileCapabilityServiceDep,
):
    return await service.list_material_capabilities(profile_id)


@router.put(
    "/material-capabilities/groups/{group_code}",
    response_model=ProfileMaterialCapabilityRead,
    responses=error_responses(404),
)
async def put_material_group_capability(
    profile_id: int,
    group_code: str,
    payload: CapabilityStateUpdate,
    service: ProfileCapabilityServiceDep,
):
    return await service.put_material_group_capability(
        profile_id,
        group_code,
        payload.state,
    )


@router.delete(
    "/material-capabilities/groups/{group_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404),
)
async def delete_material_group_capability(
    profile_id: int,
    group_code: str,
    service: ProfileCapabilityServiceDep,
) -> Response:
    await service.delete_material_group_capability(profile_id, group_code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/material-capabilities/materials/{material_id}",
    response_model=ProfileMaterialCapabilityRead,
    responses=error_responses(404),
)
async def put_material_capability(
    profile_id: int,
    material_id: int,
    payload: CapabilityStateUpdate,
    service: ProfileCapabilityServiceDep,
):
    return await service.put_material_capability(
        profile_id,
        material_id,
        payload.state,
    )


@router.delete(
    "/material-capabilities/materials/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404),
)
async def delete_material_capability(
    profile_id: int,
    material_id: int,
    service: ProfileCapabilityServiceDep,
) -> Response:
    await service.delete_material_capability(profile_id, material_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/capability-sections",
    response_model=list[ProfileSectionCompletenessRead],
    responses=error_responses(404),
)
async def list_capability_sections(
    profile_id: int,
    service: ProfileCapabilityServiceDep,
):
    return await service.list_sections(profile_id)


@router.put(
    "/capability-sections/{section_code}/state",
    response_model=ProfileSectionCompletenessRead,
    responses=error_responses(404),
)
async def set_capability_section_state(
    profile_id: int,
    section_code: ProfileSectionCode,
    payload: ProfileSectionStateUpdate,
    service: ProfileCapabilityServiceDep,
):
    return await service.set_section_state(
        profile_id,
        section_code,
        payload.state,
    )


@router.put(
    "/capability-sections/{section_code}/confirmation",
    response_model=ProfileSectionCompletenessRead,
    responses=error_responses(404),
)
async def confirm_capability_section(
    profile_id: int,
    section_code: ProfileSectionCode,
    payload: ProfileSectionConfirmation,
    service: ProfileCapabilityServiceDep,
):
    return await service.confirm_section(
        profile_id,
        section_code,
        payload.confirmed_by,
    )
