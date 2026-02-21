"""
Redis Caching Layer
Provides caching functionality for frequently accessed data
"""
import json
import logging
from typing import Optional, Any, Callable
from functools import wraps
import asyncio

from app.config import settings

logger = logging.getLogger(__name__)

# Global Redis client
redis_client = None


async def get_redis_client():
    """Get or initialize Redis client"""
    global redis_client

    if not settings.redis_enabled:
        return None

    if redis_client is None:
        try:
            import redis.asyncio as aioredis
            redis_client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Redis client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            return None

    return redis_client


async def close_redis_client():
    """Close Redis connection"""
    global redis_client

    if redis_client:
        try:
            await redis_client.close()
            logger.info("Redis client closed")
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")
        finally:
            redis_client = None


async def get(key: str) -> Optional[Any]:
    """
    Get value from cache

    Args:
        key: Cache key

    Returns:
        Cached value or None
    """
    if not settings.redis_enabled:
        return None

    try:
        client = await get_redis_client()
        if not client:
            return None

        value = await client.get(key)
        if value:
            return json.loads(value)

        return None

    except Exception as e:
        logger.error(f"Error getting from cache: {e}")
        return None


async def set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """
    Set value in cache

    Args:
        key: Cache key
        value: Value to cache (must be JSON serializable)
        ttl: Time to live in seconds (default from settings)

    Returns:
        True if successful, False otherwise
    """
    if not settings.redis_enabled:
        return False

    try:
        client = await get_redis_client()
        if not client:
            return False

        ttl = ttl or settings.cache_ttl_seconds
        await client.setex(key, ttl, json.dumps(value))
        return True

    except Exception as e:
        logger.error(f"Error setting cache: {e}")
        return False


async def delete(key: str) -> bool:
    """
    Delete key from cache

    Args:
        key: Cache key

    Returns:
        True if successful, False otherwise
    """
    if not settings.redis_enabled:
        return False

    try:
        client = await get_redis_client()
        if not client:
            return False

        await client.delete(key)
        return True

    except Exception as e:
        logger.error(f"Error deleting from cache: {e}")
        return False


async def delete_pattern(pattern: str) -> bool:
    """
    Delete all keys matching a pattern

    Args:
        pattern: Key pattern (e.g., "user:*")

    Returns:
        True if successful, False otherwise
    """
    if not settings.redis_enabled:
        return False

    try:
        client = await get_redis_client()
        if not client:
            return False

        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            await client.delete(*keys)

        return True

    except Exception as e:
        logger.error(f"Error deleting pattern from cache: {e}")
        return False


def cached(
    key_prefix: str,
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None
):
    """
    Decorator for caching function results

    Args:
        key_prefix: Prefix for cache keys
        ttl: Time to live in seconds (default from settings)
        key_func: Function to generate cache key from arguments

    Usage:
        @cached("user:", ttl=300)
        async def get_user(user_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.redis_enabled:
                return await func(*args, **kwargs)

            # Generate cache key
            if key_func:
                cache_key = key_prefix + key_func(*args, **kwargs)
            else:
                # Simple default key generation
                cache_key = key_prefix + str(args) + str(sorted(kwargs.items()))

            # Try to get from cache
            cached_value = await get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_value

            # Cache miss, call function
            logger.debug(f"Cache miss for key: {cache_key}")
            result = await func(*args, **kwargs)

            # Cache the result
            if result is not None:
                await set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


class CacheMiddleware:
    """
    Helper class for cache operations on specific endpoints
    """

    @staticmethod
    async def invalidate_user_cache(user_id: str):
        """Invalidate all cache entries for a specific user"""
        patterns = [
            f"user:{user_id}:*",
            f"dashboard:{user_id}:*",
            f"aggregate:{user_id}:*",
        ]

        for pattern in patterns:
            await delete_pattern(pattern)

        logger.info(f"Invalidated cache for user: {user_id}")

    @staticmethod
    async def invalidate_resource_cache(resource_type: str, resource_id: Optional[str] = None):
        """Invalidate cache for a specific resource type"""
        if resource_id:
            pattern = f"{resource_type}:{resource_id}:*"
        else:
            pattern = f"{resource_type}:*"

        await delete_pattern(pattern)
        logger.info(f"Invalidated cache for resource: {pattern}")
