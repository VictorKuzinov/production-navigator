from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_transport_service
from app.schemas import TransportCreate, TransportRead, TransportUpdate
from app.services.transports import TransportService

router = APIRouter(tags=["Transports"])

TransportDep = Annotated[
    TransportService,
    Depends(get_transport_service),
]


@router.get(
    "/enterprises/{profile_id}/transports",
    response_model=list[TransportRead],
)
async def list_transports(
    profile_id: int,
    service: TransportDep,
):
    return await service.list_transports(profile_id)


@router.post(
    "/enterprises/{profile_id}/transports",
    response_model=TransportRead,
)
async def create_transport(
    profile_id: int,
    transport: TransportCreate,
    service: TransportDep,
):
    return await service.create_transport(profile_id, transport)


@router.get(
    "/transports/{transport_id}",
    response_model=TransportRead,
)
async def get_transport(
    transport_id: int,
    service: TransportDep,
):
    return await service.get_transport(transport_id)


@router.patch(
    "/transports/{transport_id}",
    response_model=TransportRead,
)
async def update_transport(
    transport_id: int,
    transport: TransportUpdate,
    service: TransportDep,
):
    return await service.update_transport(transport_id, transport)


@router.delete(
    "/transports/{transport_id}",
    response_model=TransportRead,
)
async def delete_transport(
    transport_id: int,
    service: TransportDep,
):
    return await service.delete_transport(transport_id)
