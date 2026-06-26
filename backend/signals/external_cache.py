"""
External data cache — persistent storage for provider responses.

The cache sits between providers and detectors:
  Provider.fetch() → cache write → Detector.evaluate() reads cache

Design:
  - Cache entries have TTL (expires_at)
  - Detectors gracefully skip when cache is expired/missing
  - schema_version tracks provider payload evolution for migration safety
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from database import Base
from sqlalchemy import Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

logger = logging.getLogger("synchain.external_cache")


class ExternalDataCache(Base):
    """Cached external data provider response."""

    __tablename__ = "external_data_cache"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(index=True)
    data_key: Mapped[str] = mapped_column(index=True)
    data_json: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(default=1)
    fetched_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(index=True)


class CacheManager:
    """Read/write operations for ExternalDataCache."""

    def __init__(self, db: Session):
        self.db = db

    def upsert(
        self,
        provider: str,
        data_key: str,
        data: dict,
        schema_version: int = 1,
        ttl_hours: int = 12,
    ) -> ExternalDataCache:
        """
        Insert or update a cache entry.

        If a row with (provider, data_key) exists, update it.
        Otherwise, create a new row.
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=ttl_hours)

        stmt = select(ExternalDataCache).where(
            ExternalDataCache.provider == provider,
            ExternalDataCache.data_key == data_key,
        )
        existing = self.db.scalars(stmt).first()

        if existing:
            existing.data_json = json.dumps(data)
            existing.schema_version = schema_version
            existing.fetched_at = now
            existing.expires_at = expires
            entry = existing
        else:
            entry = ExternalDataCache(
                provider=provider,
                data_key=data_key,
                data_json=json.dumps(data),
                schema_version=schema_version,
                fetched_at=now,
                expires_at=expires,
            )
            self.db.add(entry)

        self.db.flush()
        return entry

    def get(
        self,
        provider: str,
        data_key: str = "global",
        require_valid: bool = True,
    ) -> dict | None:
        """
        Retrieve cached data for a provider.

        Args:
            provider: Provider name (e.g., "news_synthetic")
            data_key: Scope key (default "global")
            require_valid: If True, return None for expired entries

        Returns:
            Parsed JSON dict or None if missing/expired.
        """
        stmt = select(ExternalDataCache).where(
            ExternalDataCache.provider == provider,
            ExternalDataCache.data_key == data_key,
        )
        entry = self.db.scalars(stmt).first()

        if not entry:
            return None

        if require_valid:
            now = datetime.now(timezone.utc)
            # Handle naive datetimes (SQLite doesn't store timezone)
            expires = entry.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if now > expires:
                return None

        try:
            return json.loads(entry.data_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupt cache entry for %s/%s", provider, data_key)
            return None

    def get_all_status(self) -> list[dict]:
        """Get status of all cache entries for the status endpoint."""
        stmt = select(ExternalDataCache).order_by(ExternalDataCache.provider)
        entries = list(self.db.scalars(stmt).all())

        now = datetime.now(timezone.utc)
        result = []
        for e in entries:
            expires = e.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            remaining = (expires - now).total_seconds() / 60

            result.append(
                {
                    "provider": e.provider,
                    "data_key": e.data_key,
                    "cached": True,
                    "schema_version": e.schema_version,
                    "last_refresh": e.fetched_at.isoformat(),
                    "expires_in_minutes": round(max(0, remaining), 1),
                    "is_valid": remaining > 0,
                }
            )

        return result
