from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    CraneTypeNotFoundError,
    DuplicateMaterialError,
    DuplicateMaterialItemError,
    DuplicateProductError,
    EnterpriseProfileNotFoundError,
    EquipmentNotFoundError,
    EquipmentTypeNotFoundError,
    InvalidMaterialItemError,
    LiftingEquipmentNotFoundError,
    MaterialFormNotFoundError,
    MaterialGroupNotFoundError,
    MaterialInUseError,
    MaterialItemInUseError,
    MaterialItemNotFoundError,
    MaterialNotFoundError,
    ProductInUseError,
    ProductionFacilityNotFoundError,
    ProductNotFoundError,
    ProductTypeNotFoundError,
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


async def material_not_found_handler(
    request: Request,
    exc: MaterialNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def material_group_not_found_handler(
    request: Request,
    exc: MaterialGroupNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def duplicate_material_handler(
    request: Request,
    exc: DuplicateMaterialError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


async def material_in_use_handler(
    request: Request,
    exc: MaterialInUseError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


async def material_item_not_found_handler(
    request: Request,
    exc: MaterialItemNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def material_form_not_found_handler(
    request: Request,
    exc: MaterialFormNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def duplicate_material_item_handler(
    request: Request,
    exc: DuplicateMaterialItemError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


async def material_item_in_use_handler(
    request: Request,
    exc: MaterialItemInUseError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


async def invalid_material_item_handler(
    request: Request,
    exc: InvalidMaterialItemError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )


async def product_not_found_handler(
    request: Request,
    exc: ProductNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def product_type_not_found_handler(
    request: Request,
    exc: ProductTypeNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def duplicate_product_handler(
    request: Request,
    exc: DuplicateProductError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


async def product_in_use_handler(
    request: Request,
    exc: ProductInUseError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )
