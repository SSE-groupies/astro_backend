from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from src.config.settings import settings
from src.db.azure_tables import init_tables
from src.db.redis_cache import init_redis

# Import API routers
from src.api.stars import router as stars_router
from src.api.users import router as users_router
from src.api.health import router as health_router
from src.api.sse import stars_router as sse_stars_router, users_router as sse_users_router
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
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(sse_stars_router, prefix="/events/stars", tags=["events"])
app.include_router(sse_users_router, prefix="/events/users", tags=["events"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

# Only include debug router in non-production environments
if settings.ENVIRONMENT != "production":
    app.include_router(debug_router, prefix="/debug", tags=["debug"])
    logger.info("Debug endpoints enabled in non-production environment")

@app.on_event("startup")
async def startup_event():
    """Initialize components on application startup"""
    logger.info(f"Starting Star Map API in {settings.ENVIRONMENT} environment")
    
    # Initialize database tables
    try:
        init_tables()
        logger.info("Successfully initialized Azure Table Storage")
    except Exception as e:
        logger.error(f"Failed to initialize Azure Table Storage: {str(e)}")
    
    # Initialize Redis
    try:
        await init_redis()
        logger.info("Successfully initialized Redis")
    except Exception as e:
        logger.warning(f"Redis initialization failed: {str(e)}. Some features may be limited.")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown"""
    logger.info("Shutting down Star Map API")
    # Add any cleanup code here if needed

@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to the Star Map API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG
    )
