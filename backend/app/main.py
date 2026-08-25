from fastapi import FastAPI

from app.api.router import api_router
from app.core import settings
from app.core.exception_handlers import (
    crane_type_not_found_handler,
    enterprise_profile_not_found_handler,
    equipment_not_found_handler,
    equipment_type_not_found_handler,
    lifting_equipment_not_found_handler,
    production_facility_not_found_handler,
    transport_not_found_handler,
    transport_ownership_type_not_found_handler,
    transport_scope_not_found_handler,
    transport_type_not_found_handler,
    warehouse_not_found_handler,
    warehouse_type_not_found_handler,
)
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

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_exception_handler(
    EnterpriseProfileNotFoundError,
    enterprise_profile_not_found_handler,
)

app.add_exception_handler(
    ProductionFacilityNotFoundError,
    production_facility_not_found_handler,
)

app.add_exception_handler(
    EquipmentNotFoundError,
    equipment_not_found_handler,
)

app.add_exception_handler(
    EquipmentTypeNotFoundError,
    equipment_type_not_found_handler,
)

app.add_exception_handler(
    WarehouseNotFoundError,
    warehouse_not_found_handler,
)

app.add_exception_handler(
    WarehouseTypeNotFoundError,
    warehouse_type_not_found_handler,
)

app.add_exception_handler(
    LiftingEquipmentNotFoundError,
    lifting_equipment_not_found_handler,
)

app.add_exception_handler(
    CraneTypeNotFoundError,
    crane_type_not_found_handler,
)

app.add_exception_handler(
    TransportNotFoundError,
    transport_not_found_handler,
)

app.add_exception_handler(
    TransportTypeNotFoundError,
    transport_type_not_found_handler,
)

app.add_exception_handler(
    TransportScopeNotFoundError,
    transport_scope_not_found_handler,
)

app.add_exception_handler(
    TransportOwnershipTypeNotFoundError,
    transport_ownership_type_not_found_handler,
)

app.include_router(api_router)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
