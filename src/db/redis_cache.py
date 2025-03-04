import logging
import asyncio
from redis import asyncio as aioredis
from redis.exceptions import RedisError, ConnectionError, TimeoutError
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_limiter import FastAPILimiter

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Cache status
redis_initialized = False

async def init_redis():
    """Initialize Redis connection and setup caching/rate limiting"""
    global redis_initialized
    
    redis_host = settings.REDIS.HOST
    
    # If Redis host is not configured, skip initialization
    if not redis_host:
        logger.info("Redis host not configured, skipping cache initialization")
        redis_initialized = False
        return None

    redis_password = settings.REDIS.PASSWORD
    redis_ssl = settings.REDIS.SSL
    redis_port = settings.REDIS.PORT
    
    # Construct Redis URL with proper SSL handling
    redis_scheme = "rediss" if redis_ssl else "redis"
    redis_url = f"{redis_scheme}://{redis_host}:{redis_port}"
    
    logger.info(f"Initializing Redis cache connection to {redis_host}:{redis_port} (SSL: {redis_ssl})")
    
    # Configure connection pool
    try:
        # Set shorter timeouts in production to prevent hanging
        connect_timeout = 5.0 if settings.ENVIRONMENT == "production" else 10.0
        
        redis = aioredis.from_url(
            redis_url,
            password=redis_password,
            encoding="utf8",
            decode_responses=True,
            max_connections=10,  # Configure pool size based on container resources
            retry_on_timeout=True,
            socket_connect_timeout=connect_timeout,
            socket_keepalive=True,  # Keep connection alive
            health_check_interval=30  # Check connection every 30 seconds
        )
        
        # Test connection with timeout (important for Azure Container Apps)
        try:
            # Use asyncio.wait_for to add a timeout to the ping operation
            await asyncio.wait_for(redis.ping(), timeout=connect_timeout)
            logger.info("Successfully connected to Redis cache")
        except asyncio.TimeoutError:
            logger.warning(f"Redis ping timed out after {connect_timeout} seconds")
            if settings.ENVIRONMENT == "production":
                # In production, this is important enough to throw an error
                raise TimeoutError(f"Redis connection test timed out after {connect_timeout}s")
            return None
        
        # Initialize FastAPI Cache
        FastAPICache.init(
            backend=RedisBackend(redis),
            prefix="starmap-cache"
        )
        logger.info("FastAPI Cache initialized")
        
        # Initialize rate limiter if not in test environment
        if settings.ENVIRONMENT != "test":
            try:
                await FastAPILimiter.init(redis)
                logger.info("Rate limiter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize rate limiter: {str(e)}")
                # Continue without rate limiting
        
        redis_initialized = True
        return redis
    except (RedisError, ConnectionError, TimeoutError) as e:
        logger.warning(f"Failed to connect to Redis: {str(e)}")
        logger.warning("Application will function without caching and rate limiting")
        redis_initialized = False
        return None
    except Exception as e:
        logger.warning(f"Unexpected error initializing Redis: {str(e)}")
        redis_initialized = False
        return None

def is_cache_initialized():
    """Check if the cache is properly initialized"""
    try:
        return FastAPICache._backend is not None
    except Exception:
        return False

async def get_redis_info():
    """Get Redis server info for diagnostics"""
    if not is_cache_initialized():
        return {"status": "not_initialized"}
    
    try:
        # Get the Redis client from FastAPICache
        redis = FastAPICache._backend.redis
        
        # Add timeout to prevent hanging on slow Redis
        info = await asyncio.wait_for(redis.info(), timeout=5.0)
        clients = await asyncio.wait_for(redis.client_list(), timeout=5.0)
        
        return {
            "status": "connected",
            "version": info.get("redis_version"),
            "memory": {
                "used_memory_human": info.get("used_memory_human"),
                "maxmemory_human": info.get("maxmemory_human"),
            },
            "clients": len(clients),
            "uptime_days": info.get("uptime_in_days")
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
