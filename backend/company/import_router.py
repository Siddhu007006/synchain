"""
CSV Import API router (V2.6).

Endpoints:
  POST /api/v1/companies/{id}/import/{entity_type}?dry_run=true|false
    - dry_run=true  → Parse + validate only, return preview (no DB writes)
    - dry_run=false → Validate + UPSERT valid rows, log ImportJob

  GET  /api/v1/companies/{id}/imports
    - Import history for this company

  GET  /api/v1/companies/templates/{entity_type}.csv
    - Download CSV template
"""

import csv
import json
import logging
from pathlib import Path

from auth.dependencies import AuthContext, get_current_user, require_role
from auth.models import ROLE_MEMBER
from company.csv_import import UPSERTERS, VALIDATORS, check_headers, parse_csv_bytes
from company.import_models import ImportJob
from company.import_schemas import (
    ImportJobListResponse,
    ImportJobResponse,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportResultResponse,
    ImportRowError,
)
from company.models import Company
from database import get_db
from exceptions import NotFoundError, ValidationError
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from rate_limiter import rate_limit
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.import")

router = APIRouter(prefix="/companies", tags=["CSV Import"])

TEMPLATE_DIR = Path(__file__).parent / "templates"
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB
VALID_ENTITY_TYPES = {"products", "suppliers", "warehouses"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_company_or_404(company_id: int, auth: AuthContext, db: Session) -> Company:
    """Load company + verify org ownership. Raises 404 if not found."""
    company = db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.org_id == auth.org.id,
        )
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")
    return company


def _validate_entity_type(entity_type: str) -> None:
    """Raise 422 if entity_type is not valid."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise ValidationError(
            f"entity_type must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}"
        )


# ---------------------------------------------------------------------------
# POST /companies/{company_id}/import/{entity_type}?dry_run=true|false
# ---------------------------------------------------------------------------


@router.post(
    "/{company_id}/import/{entity_type}",
    dependencies=[Depends(require_role(ROLE_MEMBER)), Depends(rate_limit("write"))],
)
async def import_csv(
    company_id: int,
    entity_type: str,
    file: UploadFile = File(...),
    dry_run: bool = Query(
        True, description="true = preview only, false = execute import"
    ),
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV file to import (or preview) entities into a company.

    - **dry_run=true** (default): Parse and validate the CSV. Returns a preview
      with per-row validity status. No database writes occur.

    - **dry_run=false**: Validate and UPSERT valid rows into the database.
      Uses (company_id, name) as the business key:
        - If a matching name exists → UPDATE the record
        - If no match → INSERT a new record
      Returns an import summary with success/failure counts.
    """
    _validate_entity_type(entity_type)
    company = _get_company_or_404(company_id, auth, db)

    # Read file contents
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValidationError(
            f"File too large. Maximum size is {MAX_FILE_SIZE // 1024}KB"
        )

    try:
        # Parse CSV
        rows, parse_error = parse_csv_bytes(contents)
        if parse_error:
            raise ValidationError(parse_error)

        if not rows:
            raise ValidationError("CSV file contains no data rows")

        # Check headers
        first_row_keys = list(rows[0].keys())
        header_error = check_headers(first_row_keys, entity_type)
        if header_error:
            raise ValidationError(header_error)

        # Validate rows
        validator = VALIDATORS[entity_type]
        valid_rows, all_preview_rows = validator(rows)
    except (UnicodeDecodeError, csv.Error) as e:
        # CSV parsing failures — known, expected errors
        raise ValidationError(f"CSV parsing failed: {e}")
    except ValidationError:
        # Validation failures already raised — pass through
        raise
    except KeyError as e:
        # Missing required column or validator
        raise ValidationError(f"Invalid entity_type or missing column: {e}")
    # Do NOT catch generic Exception — let unexpected errors become 500s

    file_name = file.filename or "unknown.csv"

    # --- DRY RUN: preview only ---
    if dry_run:
        return ImportPreviewResponse(
            entity_type=entity_type,
            file_name=file_name,
            total_rows=len(all_preview_rows),
            valid_rows=len(valid_rows),
            invalid_rows=len(all_preview_rows) - len(valid_rows),
            preview=[
                ImportPreviewRow(
                    row=r["row"],
                    data=r["data"],
                    valid=r["valid"],
                    errors=r["errors"],
                )
                for r in all_preview_rows
            ],
        )

    # --- EXECUTE: upsert valid rows ---
    upserter = UPSERTERS[entity_type]
    created, updated = upserter(db, company.id, valid_rows)

    # Build error list for failed rows
    errors = []
    for r in all_preview_rows:
        if not r["valid"]:
            for err_msg in r["errors"]:
                # Determine field from error message (best-effort)
                field = err_msg.split(" ")[0] if err_msg else "unknown"
                errors.append(
                    ImportRowError(row=r["row"], field=field, message=err_msg)
                )

    # Log import job for audit trail
    job = ImportJob(
        company_id=company.id,
        entity_type=entity_type,
        file_name=file_name,
        rows_processed=len(all_preview_rows),
        rows_success=len(valid_rows),
        rows_failed=len(all_preview_rows) - len(valid_rows),
        errors_json=json.dumps([e.model_dump() for e in errors]),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(
        "CSV import: company=%d entity=%s file=%s total=%d success=%d failed=%d created=%d updated=%d",
        company.id,
        entity_type,
        file_name,
        len(all_preview_rows),
        len(valid_rows),
        len(all_preview_rows) - len(valid_rows),
        created,
        updated,
    )

    return ImportResultResponse(
        entity_type=entity_type,
        file_name=file_name,
        total_rows=len(all_preview_rows),
        success=len(valid_rows),
        failed=len(all_preview_rows) - len(valid_rows),
        created=created,
        updated=updated,
        errors=errors,
        job_id=job.id,
    )


# ---------------------------------------------------------------------------
# GET /companies/{company_id}/imports — import history
# ---------------------------------------------------------------------------


@router.get(
    "/{company_id}/imports",
    response_model=ImportJobListResponse,
)
def list_import_jobs(
    company_id: int,
    limit: int = 20,
    offset: int = 0,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List import history for a company (most recent first)."""
    _get_company_or_404(company_id, auth, db)

    total = (
        db.scalar(
            select(func.count())
            .select_from(ImportJob)
            .where(ImportJob.company_id == company_id)
        )
        or 0
    )

    jobs = db.scalars(
        select(ImportJob)
        .where(ImportJob.company_id == company_id)
        .order_by(ImportJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return ImportJobListResponse(
        total=total,
        imports=[
            ImportJobResponse(
                id=j.id,
                entity_type=j.entity_type,
                file_name=j.file_name,
                rows_processed=j.rows_processed,
                rows_success=j.rows_success,
                rows_failed=j.rows_failed,
                created_at=j.created_at.isoformat() if j.created_at else None,
            )
            for j in jobs
        ],
    )


# ---------------------------------------------------------------------------
# GET /companies/templates/{entity_type}.csv — download template
# ---------------------------------------------------------------------------


@router.get(
    "/templates/{entity_type}.csv",
    response_class=FileResponse,
)
def download_template(entity_type: str):
    """Download a CSV template file for the given entity type."""
    _validate_entity_type(entity_type)

    template_path = TEMPLATE_DIR / f"{entity_type}.csv"
    if not template_path.exists():
        raise NotFoundError(f"Template for {entity_type} not found")

    return FileResponse(
        path=str(template_path),
        filename=f"{entity_type}_template.csv",
        media_type="text/csv",
    )
