import asyncio
import contextlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import socket
import platform

from src.config.settings import settings
from src.db.azure_tables import init_tables
from src.db.redis_cache import init_redis
from src.tasks.gc_stars import delete_old_stars

# Import API routers
from src.api.stars import router as stars_router
from src.api.health import router as health_router
from src.api.sse import router as sse_stars_router
from src.api.admin import router as admin_router
from src.api.debug import router as debug_router

# Setup logger
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend service for Star Map application",
    version=settings.VERSION,
    debug=settings.DEBUG
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.API.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(stars_router, prefix="/stars", tags=["stars"])
# Register users here! If you want :3
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(sse_stars_router, prefix="/events/stars", tags=["events"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

# Only include debug router in non-production environments
if settings.ENVIRONMENT != "production":
    app.include_router(debug_router, prefix="/debug", tags=["debug"])
    logger.info("Debug endpoints enabled in non-production environment")

# Modern lifespan approach instead of on_event
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    try:
        logger.info(f"Starting up {settings.PROJECT_NAME} v{settings.VERSION}")
        
        # Initialize database and services
        init_tables()
        await init_redis()

        # Verify required settings
        settings.verify_required_settings()
        
        # Start background garbage collection task
        asyncio.create_task(delete_old_stars())

        logger.info("Initialization complete")

    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

    yield

    # Shutdown actions
    logger.info("Shutting down application...")


# Apply the lifespan handler
app.router.lifespan_context = lifespan

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with version info"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "message": "Welcome to the Star Map API"
    }

if __name__ == "__main__":
    import uvicorn
    host = "0.0.0.0" if settings.ENVIRONMENT != "development" else "127.0.0.1"
    uvicorn.run(
        "src.main:app",
        host=host,
        port=settings.PORT,
        reload=settings.DEBUG
    )
