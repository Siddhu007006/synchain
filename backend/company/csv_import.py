"""
CSV Import utilities for Products, Suppliers, and Warehouses (V2 Phase 7).

This module provides shared parsing, validation, and upsert helpers used
by import_router.py (the canonical import pipeline).

The HTTP route handlers that previously lived here have been removed.
All import HTTP traffic is now handled exclusively by:
  import_router.py → POST /api/v1/companies/{id}/import/{entity_type}

Exported utilities:
  parse_csv_bytes   — parse raw file bytes into normalized row dicts
  check_headers     — validate required columns are present
  VALIDATORS        — dict of entity_type → row-level validation function
  UPSERTERS         — dict of entity_type → DB upsert function
  validate_*        — public aliases for test compatibility
  upsert_*          — public aliases for test compatibility
"""

import csv
import io
import logging
from typing import Any

from company.product_models import Product
from company.supplier_warehouse_models import Supplier, Warehouse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.import")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_csv(file_bytes: bytes) -> tuple[list[dict], str | None]:
    """Parse CSV bytes, return (rows, error_message).

    Handles real-world CSV quirks:
    - UTF-8 BOM (Excel exports)
    - Case-insensitive headers (normalized to lowercase)
    - Whitespace in headers and values (stripped)
    - Empty files
    - Non-UTF-8 encoding
    """
    if not file_bytes or not file_bytes.strip():
        return [], "File is empty"

    try:
        text = file_bytes.decode("utf-8-sig")  # handles BOM
    except UnicodeDecodeError:
        return [], "File is not valid UTF-8"

    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for raw_row in reader:
            # Normalize: lowercase keys, strip whitespace from keys and values
            normalized = {
                k.strip().lower(): v.strip() if isinstance(v, str) else v
                for k, v in raw_row.items()
            }
            rows.append(normalized)
        return rows, None
    except Exception as e:
        return [], f"CSV parse error: {e}"


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return (
            float(str(val).strip()) if val is not None and str(val).strip() else default
        )
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Public API for import_router.py (V2.6 advanced import pipeline)
# ---------------------------------------------------------------------------


def parse_csv_bytes(file_bytes: bytes) -> tuple[list[dict], str | None]:
    """Parse CSV bytes into a list of dicts. Public alias of _parse_csv."""
    return _parse_csv(file_bytes)


# Required headers per entity type
_REQUIRED_HEADERS: dict[str, set[str]] = {
    "products": {"name"},
    "suppliers": {"name"},
    "warehouses": {"name", "warehouse_id"},
}

_OPTIONAL_HEADERS: dict[str, set[str]] = {
    "products": {"category", "current_stock", "avg_monthly_demand"},
    "suppliers": {"lead_time_days", "supply_status", "reliability_pct"},
    "warehouses": {"location", "capacity"},
}


def check_headers(columns: list[str], entity_type: str) -> str | None:
    """Validate that the CSV has required columns. Returns error string or None."""
    required = _REQUIRED_HEADERS.get(entity_type, set())
    cols_lower = {c.strip().lower() for c in columns}
    missing = required - cols_lower
    if missing:
        return f"Missing required columns: {', '.join(sorted(missing))}"
    return None


# ---------------------------------------------------------------------------
# Validators: parse rows and return (valid_rows, all_preview_rows)
# ---------------------------------------------------------------------------


def _validate_products(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    valid_rows, preview = [], []
    for i, row in enumerate(rows, start=2):
        errors = []
        name = str(row.get("name", "")).strip()
        if not name:
            errors.append("name is required")

        # Accept column aliases: stock/current_stock, demand/avg_monthly_demand
        raw_stock = row.get("current_stock") or row.get("stock")
        raw_demand = row.get("avg_monthly_demand") or row.get("demand")

        # Validate stock
        stock_val = 0.0
        if raw_stock is not None and str(raw_stock).strip():
            try:
                stock_val = float(str(raw_stock).strip())
                if stock_val < 0:
                    errors.append("stock cannot be negative")
            except (ValueError, TypeError):
                errors.append("stock must be a number")
                stock_val = 0.0

        # Validate demand
        demand_val = 0.0
        if raw_demand is not None and str(raw_demand).strip():
            try:
                demand_val = float(str(raw_demand).strip())
                if demand_val < 0:
                    errors.append("demand cannot be negative")
            except (ValueError, TypeError):
                errors.append("demand must be a number")
                demand_val = 0.0

        data = {
            "name": name,
            "category": str(row.get("category", "")).strip(),
            "current_stock": stock_val,
            "avg_monthly_demand": demand_val,
        }
        entry = {"row": i, "data": data, "valid": len(errors) == 0, "errors": errors}
        preview.append(entry)
        if not errors:
            valid_rows.append(data)
    return valid_rows, preview


def _validate_suppliers(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    VALID_STATUS = {"High", "Medium", "Low"}
    valid_rows, preview = [], []
    for i, row in enumerate(rows, start=2):
        errors = []
        name = str(row.get("name", "")).strip()
        if not name:
            errors.append("name is required")

        # Accept column aliases
        raw_lt = row.get("lead_time_days") or row.get("lead_time")
        raw_rel = row.get("reliability_pct") or row.get("reliability")
        raw_status = row.get("supply_status") or row.get("status")

        # Validate lead time
        lt_val = 0.0
        if raw_lt is not None and str(raw_lt).strip():
            try:
                lt_val = float(str(raw_lt).strip())
                if lt_val < 0:
                    errors.append("lead_time cannot be negative")
            except (ValueError, TypeError):
                errors.append("lead_time must be a number")
                lt_val = 0.0

        # Validate reliability
        rel_val = 100.0
        if raw_rel is not None and str(raw_rel).strip():
            try:
                rel_val = float(str(raw_rel).strip())
                if rel_val < 0 or rel_val > 100:
                    errors.append("reliability must be between 0 and 100")
            except (ValueError, TypeError):
                errors.append("reliability must be a number")
                rel_val = 100.0

        # Validate supply status
        supply_status = "Medium"
        if raw_status is not None and str(raw_status).strip():
            status_str = str(raw_status).strip()
            # Case-insensitive matching
            matched = None
            for valid in VALID_STATUS:
                if status_str.lower() == valid.lower():
                    matched = valid
                    break
            if matched:
                supply_status = matched
            else:
                errors.append(
                    f"supply_status must be High, Medium, or Low, got '{status_str}'"
                )

        data = {
            "name": name,
            "lead_time_days": lt_val,
            "supply_status": supply_status,
            "reliability_pct": rel_val,
        }
        entry = {"row": i, "data": data, "valid": len(errors) == 0, "errors": errors}
        preview.append(entry)
        if not errors:
            valid_rows.append(data)
    return valid_rows, preview


def _validate_warehouses(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    VALID_WH = {"W1", "W2", "W3"}
    valid_rows, preview = [], []
    for i, row in enumerate(rows, start=2):
        errors = []
        name = str(row.get("name", "")).strip()
        if not name:
            errors.append("name is required")

        raw_wh = str(row.get("warehouse_id", "")).strip().upper()
        if not raw_wh:
            errors.append("warehouse_id is required")
        elif raw_wh not in VALID_WH:
            errors.append(f"warehouse_id must be W1, W2, or W3, got '{raw_wh}'")

        # Validate capacity
        raw_cap = row.get("capacity")
        cap_val = 10000.0
        if raw_cap is not None and str(raw_cap).strip():
            try:
                cap_val = float(str(raw_cap).strip())
                if cap_val <= 0:
                    errors.append("capacity must be greater than 0")
            except (ValueError, TypeError):
                errors.append("capacity must be a number")
                cap_val = 10000.0

        data = {
            "name": name,
            "warehouse_id": raw_wh,
            "location": str(row.get("location", "")).strip(),
            "capacity": cap_val,
        }
        entry = {"row": i, "data": data, "valid": len(errors) == 0, "errors": errors}
        preview.append(entry)
        if not errors:
            valid_rows.append(data)
    return valid_rows, preview


VALIDATORS = {
    "products": _validate_products,
    "suppliers": _validate_suppliers,
    "warehouses": _validate_warehouses,
}


# ---------------------------------------------------------------------------
# Upserters: write valid rows to DB, return (created, updated) counts
# ---------------------------------------------------------------------------


def _upsert_products(
    db: Session, company_id: int, valid_rows: list[dict]
) -> tuple[int, int]:
    created, updated = 0, 0
    for data in valid_rows:
        # Case-insensitive name matching
        existing = db.scalar(
            select(Product).where(
                Product.company_id == company_id,
                func.lower(Product.name) == data["name"].lower(),
            )
        )
        if existing:
            if "category" in data:
                existing.category = data["category"]
            existing.current_stock = data["current_stock"]
            existing.avg_monthly_demand = data["avg_monthly_demand"]
            updated += 1
        else:
            db.add(Product(company_id=company_id, **data))
            created += 1
    db.commit()
    return created, updated


def _upsert_suppliers(
    db: Session, company_id: int, valid_rows: list[dict]
) -> tuple[int, int]:
    created, updated = 0, 0
    for data in valid_rows:
        existing = db.scalar(
            select(Supplier).where(
                Supplier.company_id == company_id, Supplier.name == data["name"]
            )
        )
        if existing:
            existing.lead_time_days = data["lead_time_days"]
            existing.supply_status = data["supply_status"]
            existing.reliability_pct = data["reliability_pct"]
            updated += 1
        else:
            db.add(Supplier(company_id=company_id, **data))
            created += 1
    db.commit()
    return created, updated


def _upsert_warehouses(
    db: Session, company_id: int, valid_rows: list[dict]
) -> tuple[int, int]:
    created, updated = 0, 0
    for data in valid_rows:
        existing = db.scalar(
            select(Warehouse).where(
                Warehouse.company_id == company_id, Warehouse.name == data["name"]
            )
        )
        if existing:
            existing.warehouse_id = data["warehouse_id"]
            existing.location = data["location"]
            existing.capacity = data["capacity"]
            updated += 1
        else:
            db.add(Warehouse(company_id=company_id, **data))
            created += 1
    db.commit()
    return created, updated


UPSERTERS = {
    "products": _upsert_products,
    "suppliers": _upsert_suppliers,
    "warehouses": _upsert_warehouses,
}


# ---------------------------------------------------------------------------
# Public aliases for validators and upserters
# (Tests and external callers use these; internal dicts use the private names)
# ---------------------------------------------------------------------------

validate_products = _validate_products
validate_suppliers = _validate_suppliers
validate_warehouses = _validate_warehouses
upsert_products = _upsert_products
upsert_suppliers = _upsert_suppliers
upsert_warehouses = _upsert_warehouses
