"""
Background refresh scheduler for external data providers.

Runs as an asyncio task within FastAPI's lifespan.
No external dependencies (no Celery, no Redis).

Flow:
  1. On app startup, schedule periodic refresh
  2. Every N hours, fetch from all providers
  3. Store results in ExternalDataCache
  4. On app shutdown, cancel the task
"""

import asyncio
import logging

from signals.external_cache import CacheManager
from signals.providers import DEFAULT_PROVIDERS, get_provider
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.scheduler")

# Default configuration
DEFAULT_REFRESH_HOURS = 6
DEFAULT_CACHE_TTL_HOURS = 12
DEFAULT_PROVIDER_MODE = "auto"  # E7: auto-select real vs synthetic


def refresh_all_providers(
    db: Session,
    mode: str = DEFAULT_PROVIDER_MODE,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
) -> dict[str, bool]:
    """
    Synchronous refresh of all external data providers.

    Fetches from each provider and upserts into cache.
    Returns dict of {category: success_bool}.

    E7 Design Decision Q4: If a provider returns empty data (fetch failure),
    skip the cache write to preserve the last valid cache entry until
    its TTL expires naturally.
    """
    cache = CacheManager(db)
    results: dict[str, bool] = {}

    for category in DEFAULT_PROVIDERS:
        try:
            provider = get_provider(category, mode)
            data = provider.fetch({"data_key": "global"})

            # Q4: Skip cache write on empty response (preserve last valid)
            if not data:
                logger.warning(
                    "Provider %s returned empty data for %s — preserving cache",
                    provider.source_name,
                    category,
                )
                results[category] = False
                continue

            cache.upsert(
                provider=provider.source_name,
                data_key="global",
                data=data,
                schema_version=provider.SCHEMA_VERSION,
                ttl_hours=ttl_hours,
            )
            results[category] = True
            logger.info(
                "Refreshed %s (provider=%s, schema_v=%d)",
                category,
                provider.source_name,
                provider.SCHEMA_VERSION,
            )
        except Exception:
            results[category] = False
            logger.exception("Failed to refresh %s", category)

    db.commit()
    return results


async def run_scheduler(
    db_factory,
    refresh_hours: int = DEFAULT_REFRESH_HOURS,
    mode: str = DEFAULT_PROVIDER_MODE,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
):
    """
    Async background task: periodically refresh all providers.

    Args:
        db_factory: Callable that returns a new DB session
        refresh_hours: Hours between refreshes
        mode: Provider mode ("synthetic" or future API modes)
        ttl_hours: Cache entry time-to-live in hours
    """
    logger.info(
        "External data scheduler started (interval=%dh, mode=%s, ttl=%dh)",
        refresh_hours,
        mode,
        ttl_hours,
    )

    # Initial refresh on startup
    try:
        db = db_factory()
        try:
            results = refresh_all_providers(db, mode, ttl_hours)
            logger.info("Initial refresh complete: %s", results)
        finally:
            db.close()
    except Exception:
        logger.exception("Initial refresh failed")

    # Periodic refresh loop
    while True:
        await asyncio.sleep(refresh_hours * 3600)
        try:
            db = db_factory()
            try:
                results = refresh_all_providers(db, mode, ttl_hours)
                logger.info("Scheduled refresh complete: %s", results)
            finally:
                db.close()
        except Exception:
            logger.exception("Scheduled refresh failed")
