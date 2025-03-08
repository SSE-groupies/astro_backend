from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import datetime as dt
import socket
import os
import platform
import sys

from src.config.settings import settings
from src.db.azure_tables import tables
from src.db.redis_cache import is_cache_initialized, get_redis_info
from fastapi_cache import FastAPICache

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(dt.timezone.utc).timestamp()
    }

@router.get("/readiness")
async def readiness_check():
    """
    Readiness probe for container orchestrators.
    Verifies database connections are operational.
    """
    health_status = {
        "status": "ready", 
        "services": {},
        "environment": settings.ENVIRONMENT,
        "hostname": socket.gethostname(),
        "python_version": sys.version,
        "platform": platform.platform()
    }
    
    # Check Azure Table Storage
    try:
        # If in test mode, tables will be mocks and always ready
        if settings.ENVIRONMENT == "test":
            health_status["services"]["azure_tables"] = "mock mode"
        else:
            # Test Azure Table Storage connection
            # Just requesting an entity is a more reliable test than list_entities
            tables["Users"].get_entity(partition_key="system", row_key="health-check")
            health_status["services"]["azure_tables"] = "healthy"
    except Exception as e:
        error_message = str(e)
        logger.warning(f"Azure Tables check failed: {error_message}")
        
        # Don't fail readiness in development or test environments
        if settings.ENVIRONMENT in ["production", "staging"]:
            health_status["status"] = "not_ready"
        
        health_status["services"]["azure_tables"] = f"unhealthy: {error_message}"
    
    # Check Redis connection - don't fail readiness if Redis is down
    try:
        if is_cache_initialized():
            health_status["services"]["redis"] = "healthy"
        else:
            health_status["services"]["redis"] = "not configured"
    except Exception as e:
        logger.warning(f"Redis check failed: {str(e)}")
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        # Don't fail readiness just because Redis is down - app can function without it
    
    # Include environment variables that might be useful for diagnostics
    # Be careful not to include sensitive information
    diagnostic_vars = ["ENVIRONMENT", "PORT", "AZURE_STORAGE_USE_MANAGED_IDENTITY"]
    health_status["env_vars"] = {key: os.environ.get(key, "not set") for key in diagnostic_vars}
    
    # Include container metadata if available (works in Azure Container Apps)
    container_vars = ["CONTAINER_APP_NAME", "CONTAINER_APP_REVISION"]
    container_info = {key: os.environ.get(key) for key in container_vars if os.environ.get(key)}
    if container_info:
        health_status["container"] = container_info
    
    status_code = 200 if health_status["status"] == "ready" else 503
    return JSONResponse(status_code=status_code, content=health_status)

@router.get("/liveness")
async def liveness_check():
    """
    Liveness probe for container orchestrators.
    Simple check to verify the application is running.
    """
    return {
        "status": "alive", 
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(dt.timezone.utc).timestamp()
    }

@router.get("/diagnostics")
async def diagnostics():
    """Detailed diagnostic information for troubleshooting"""
    if settings.ENVIRONMENT == "production":
        return {"message": "Diagnostics endpoint disabled in production"}
    
    # Gather detailed diagnostic information
    diagnostic_info = {
        "app_info": {
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "debug_mode": settings.DEBUG,
            "host": settings.HOST_NAME
        },
        "system_info": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
            "pid": os.getpid()
        },
        "environment_variables": {
            key: value for key, value in os.environ.items() 
            if not any(secret in key.lower() for secret in ["password", "secret", "key", "token"])
        }
    }
    
    return diagnostic_info

@router.get("/redis")
async def redis_info():
    """Detailed Redis cache information for troubleshooting"""
    if settings.ENVIRONMENT == "production":
        return {"message": "Redis diagnostics endpoint disabled in production"}
    
    info = await get_redis_info()
    return info
