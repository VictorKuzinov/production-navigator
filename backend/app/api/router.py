from fastapi import APIRouter

from app.api.enterprises import router as enterprises_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(enterprises_router)