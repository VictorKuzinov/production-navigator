from fastapi import APIRouter

from app.api import production_facilities
from app.api.enterprises import router as enterprises_router
from app.api.production_facilities import router as production_facilities_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(enterprises_router)
api_router.include_router(production_facilities_router)