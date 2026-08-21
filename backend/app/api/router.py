from fastapi import APIRouter

from app.api.enterprises import router as enterprises_router
from app.api.equipments import router as equipments_router
from app.api.production_facilities import router as production_facilities_router
from app.api.warehouses import router as warehouses_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(enterprises_router)
api_router.include_router(production_facilities_router)
api_router.include_router(equipments_router)
api_router.include_router(warehouses_router)
