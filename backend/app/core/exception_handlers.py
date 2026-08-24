from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    CraneTypeNotFoundError,
    EnterpriseProfileNotFoundError,
    EquipmentNotFoundError,
    EquipmentTypeNotFoundError,
    LiftingEquipmentNotFoundError,
    ProductionFacilityNotFoundError,
    WarehouseNotFoundError,
    WarehouseTypeNotFoundError,
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


async def warehouse_not_found_handler(
    request: Request,
    exc: WarehouseNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def warehouse_type_not_found_handler(
    request: Request,
    exc: WarehouseTypeNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def lifting_equipment_not_found_handler(
    request: Request,
    exc: LiftingEquipmentNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def crane_type_not_found_handler(
    request: Request,
    exc: CraneTypeNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )
