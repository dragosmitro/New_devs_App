import json
import logging
import redis.asyncio as redis
from typing import Dict, Any
import os

from app.services.reservations import calculate_total_revenue

logger = logging.getLogger(__name__)

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


async def get_revenue_summary(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    Falls through to database if Redis is unavailable.
    """
    cache_key = f"revenue:{tenant_id}:{property_id}"

    # Try cache first, but don't fail if Redis is down
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis read failed, falling through to DB: {e}")

    result = await calculate_total_revenue(property_id, tenant_id)

    # Try to cache the result, but don't fail if Redis is down
    try:
        await redis_client.setex(cache_key, 300, json.dumps(result))
    except Exception as e:
        logger.warning(f"Redis write failed, result not cached: {e}")

    return result
