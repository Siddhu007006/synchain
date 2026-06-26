"""
Alembic env.py — configured for SynChain.

Reads DATABASE_URL from our config.py (pydantic-settings) and uses
our SQLAlchemy 2.0 DeclarativeBase metadata for autogenerate.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audit.models  # noqa: F401  (Phase E9 Audit)
import auth.models  # noqa: F401  (Phase E8)
import company.import_models  # noqa: F401  (V2.6 Import Jobs)
import company.models  # noqa: F401  (V2 Phase 1)
import company.product_models  # noqa: F401  (V2.3 Products)
import company.supplier_warehouse_models  # noqa: F401  (V2.5 Suppliers + Warehouses)
import digital_twin.models  # noqa: F401  (Phase E1)
import forecasting.models  # noqa: F401  (Phase E2)
import metering.models  # noqa: F401  (Phase E9 Metering)

# Import all models so Base.metadata knows about them
import models  # noqa: F401
from config import settings
from database import Base

# Alembic Config object
config = context.config

# Override sqlalchemy.url from our settings (single source of truth)
config.set_main_option("sqlalchemy.url", settings.database_url)

# Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite ALTER TABLE
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
