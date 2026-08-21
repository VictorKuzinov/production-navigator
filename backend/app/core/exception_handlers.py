from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    EquipmentNotFoundError,
    EquipmentTypeNotFoundError,
    ProductionFacilityNotFoundError,
)


async def enterprise_profile_not_found_handler(
    request: Request,
    exc: EnterpriseProfileNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def production_facility_not_found_handler(
    request: Request,
    exc: ProductionFacilityNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )

async def equipment_not_found_handler(
    request: Request,
    exc: EquipmentNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )

async def equipment_type_not_found_handler(
    request: Request,
    exc: EquipmentTypeNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )