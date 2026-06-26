"""
Pydantic schemas for CSV Import API (V2.6).

Three response types:
  - ImportPreviewResponse: dry_run=true result (no DB writes)
  - ImportResultResponse:  dry_run=false result (rows inserted/upserted)
  - ImportJobResponse:     import history record
"""

from typing import Optional

from pydantic import BaseModel


class ImportRowError(BaseModel):
    """A single validation error for one row."""

    row: int  # 1-indexed row number (excluding header)
    field: str  # Column name that failed
    message: str  # Human-readable error


class ImportPreviewRow(BaseModel):
    """One parsed row with validity status for preview display."""

    row: int
    data: dict  # Parsed column values
    valid: bool
    errors: list[str]


class ImportPreviewResponse(BaseModel):
    """Returned when dry_run=true. No DB writes occurred."""

    entity_type: str
    file_name: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    preview: list[ImportPreviewRow]


class ImportResultResponse(BaseModel):
    """Returned when dry_run=false. Valid rows were upserted."""

    entity_type: str
    file_name: str
    total_rows: int
    success: int
    failed: int
    created: int  # New rows inserted
    updated: int  # Existing rows updated (upsert)
    errors: list[ImportRowError]
    job_id: int  # FK → import_jobs.id for audit trail


class ImportJobResponse(BaseModel):
    """Import history record for GET /companies/{id}/imports."""

    id: int
    entity_type: str
    file_name: str
    rows_processed: int
    rows_success: int
    rows_failed: int
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ImportJobListResponse(BaseModel):
    """Paginated import history."""

    total: int
    imports: list[ImportJobResponse]
