from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    CraneTypeNotFoundError,
    EnterpriseProfileNotFoundError,
    EquipmentNotFoundError,
    EquipmentTypeNotFoundError,
    LiftingEquipmentNotFoundError,
    ProductionFacilityNotFoundError,
    TransportNotFoundError,
    TransportOwnershipTypeNotFoundError,
    TransportScopeNotFoundError,
    TransportTypeNotFoundError,
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


async def transport_not_found_handler(
    request: Request,
    exc: TransportNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def transport_type_not_found_handler(
    request: Request,
    exc: TransportTypeNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def transport_scope_not_found_handler(
    request: Request,
    exc: TransportScopeNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def transport_ownership_type_not_found_handler(
    request: Request,
    exc: TransportOwnershipTypeNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )
