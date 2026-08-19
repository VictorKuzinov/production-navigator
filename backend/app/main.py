from fastapi import FastAPI

from app.api.router import api_router
from app.core import settings
from app.core.exception_handlers import (
    enterprise_profile_not_found_handler,
    production_facility_not_found_handler,
)
from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    ProductionFacilityNotFoundError,
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

app.include_router(api_router)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
