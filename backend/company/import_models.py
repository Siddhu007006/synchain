"""
SQLAlchemy 2.0 model for ImportJob (V2.6).

Audit trail for CSV imports. Every import (preview or execute) is logged
so users and admins can trace what was imported, when, and by whom.

Design: One ImportJob per CSV upload execution (not preview).
Previews are stateless — only confirmed imports create a job record.
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class ImportJob(Base):
    """Audit record for a CSV import operation."""

    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), index=True, nullable=False
    )

    # "products" | "suppliers" | "warehouses"
    entity_type: Mapped[str] = mapped_column(index=True)

    file_name: Mapped[str] = mapped_column(default="")
    rows_processed: Mapped[int] = mapped_column(default=0)
    rows_success: Mapped[int] = mapped_column(default=0)
    rows_failed: Mapped[int] = mapped_column(default=0)

    # JSON-serialized list of { row, field, message } error details
    errors_json: Mapped[str] = mapped_column(Text, default="[]")

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
