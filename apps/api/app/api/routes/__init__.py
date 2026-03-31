from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.lessons import router as lessons_router
from app.api.routes.live import router as live_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(uploads_router, prefix="/api", tags=["uploads"])
api_router.include_router(lessons_router, prefix="/api", tags=["lessons"])
api_router.include_router(live_router, tags=["live"])
