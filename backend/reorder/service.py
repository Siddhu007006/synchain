"""
Reorder Recommendation Service (V3.0 Sprint A).

Orchestration layer between the database and the pure engine.

Responsibilities:
  1. Load products for a company
  2. Load latest forecast for each product (from forecast_records)
  3. Load suppliers for the company (pick best by reliability)
  4. Load active signals for the twin
  5. Feed all inputs to engine.calculate_recommendation()
  6. Return sorted results (CRITICAL first)

This layer has DB access. The engine does NOT.
"""

import logging
from datetime import date

from company.models import Company
from company.product_models import Product
from company.supplier_warehouse_models import Supplier
from digital_twin.models import DigitalTwin, SignalEvent
from forecasting.models import ForecastRecord
from reorder.engine import (
    ForecastData,
    ProductData,
    ReorderResult,
    SignalContext,
    SupplierData,
    calculate_recommendation,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.reorder")

# Severity sort order for output
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}


def get_company_recommendations(
    company_id: int,
    org_id: int,
    db: Session,
) -> list[ReorderResult]:
    """
    Generate reorder recommendations for ALL products in a company.

    Flow:
      1. Verify company belongs to org
      2. Load all products
      3. For each product → gather forecast, supplier, signals
      4. Run engine
      5. Sort by severity (CRITICAL first)
    """
    # --- Load company ---
    company = db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.org_id == org_id,
        )
    ).scalar_one_or_none()

    if company is None:
        return []

    # --- Load all products ---
    products = (
        db.execute(select(Product).where(Product.company_id == company_id))
        .scalars()
        .all()
    )

    if not products:
        return []

    # --- Load suppliers (sorted by reliability descending) ---
    suppliers = (
        db.execute(
            select(Supplier)
            .where(Supplier.company_id == company_id)
            .order_by(desc(Supplier.reliability_pct))
        )
        .scalars()
        .all()
    )

    best_supplier = _pick_best_supplier(suppliers)

    # --- Load twin for this company (if exists) ---
    twin = db.execute(
        select(DigitalTwin).where(DigitalTwin.company_id == company_id)
    ).scalar_one_or_none()

    # --- Generate recommendations ---
    results: list[ReorderResult] = []
    today = date.today()

    for product in products:
        forecast = _get_latest_forecast(product.name, twin, db)
        signals = _get_signal_context(twin, db) if twin else SignalContext()

        result = calculate_recommendation(
            product=ProductData(
                product_id=product.id,
                product_name=product.name,
                company_id=company_id,
                current_stock=product.current_stock,
                avg_monthly_demand=product.avg_monthly_demand,
                unit_price=product.unit_price,
            ),
            forecast=forecast,
            supplier=best_supplier,
            signals=signals,
            today=today,
        )
        results.append(result)

    # Sort: CRITICAL → HIGH → MEDIUM → LOW → NONE
    results.sort(key=lambda r: _SEVERITY_ORDER.get(r.severity, 99))

    logger.info(
        "Generated %d recommendations for company_id=%d " "(critical=%d, high=%d)",
        len(results),
        company_id,
        sum(1 for r in results if r.severity == "CRITICAL"),
        sum(1 for r in results if r.severity == "HIGH"),
    )

    return results


def get_product_recommendation(
    product_id: int,
    org_id: int,
    db: Session,
) -> ReorderResult | None:
    """Generate recommendation for a single product."""

    product = db.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()

    if product is None:
        return None

    # Verify org ownership through company
    company = db.execute(
        select(Company).where(
            Company.id == product.company_id,
            Company.org_id == org_id,
        )
    ).scalar_one_or_none()

    if company is None:
        return None

    # Supplier
    suppliers = (
        db.execute(
            select(Supplier)
            .where(Supplier.company_id == product.company_id)
            .order_by(desc(Supplier.reliability_pct))
        )
        .scalars()
        .all()
    )

    best_supplier = _pick_best_supplier(suppliers)

    # Twin + forecast + signals
    twin = db.execute(
        select(DigitalTwin).where(DigitalTwin.company_id == product.company_id)
    ).scalar_one_or_none()

    forecast = _get_latest_forecast(product.name, twin, db)
    signals = _get_signal_context(twin, db) if twin else SignalContext()

    return calculate_recommendation(
        product=ProductData(
            product_id=product.id,
            product_name=product.name,
            company_id=product.company_id,
            current_stock=product.current_stock,
            avg_monthly_demand=product.avg_monthly_demand,
            unit_price=product.unit_price,
        ),
        forecast=forecast,
        supplier=best_supplier,
        signals=signals,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pick_best_supplier(suppliers: list[Supplier]) -> SupplierData | None:
    """Pick the highest-reliability supplier. Returns None if no suppliers."""
    if not suppliers:
        return None

    best = suppliers[0]  # already sorted by reliability desc
    return SupplierData(
        supplier_id=best.id,
        supplier_name=best.name,
        lead_time_days=best.lead_time_days,
        reliability_pct=best.reliability_pct,
        supply_status=best.supply_status,
    )


def _get_latest_forecast(
    product_name: str,
    twin: DigitalTwin | None,
    db: Session,
) -> ForecastData | None:
    """Get the most recent forecast for a product from forecast_records."""
    if twin is None:
        return None

    record = db.execute(
        select(ForecastRecord)
        .where(
            ForecastRecord.twin_id == twin.id,
            ForecastRecord.product_name == product_name,
            ForecastRecord.horizon == 1,  # nearest-term forecast
        )
        .order_by(desc(ForecastRecord.created_at))
        .limit(1)
    ).scalar_one_or_none()

    if record is None:
        return None

    return ForecastData(
        forecast_demand=record.forecast_demand,
        confidence=record.confidence,
        supply_risk=record.supply_risk,
        trend_factor=record.trend_factor,
    )


def _get_signal_context(twin: DigitalTwin, db: Session) -> SignalContext:
    """Load recent signals for explainability context."""
    # Get signals from last 7 days
    recent_signals = (
        db.execute(
            select(SignalEvent)
            .where(SignalEvent.twin_id == twin.id)
            .order_by(desc(SignalEvent.created_at))
            .limit(20)
        )
        .scalars()
        .all()
    )

    if not recent_signals:
        return SignalContext()

    critical_count = sum(1 for s in recent_signals if s.severity >= 0.8)
    high_severity = [
        f"{s.signal_type} signal (severity: {s.severity:.2f})"
        for s in recent_signals
        if s.severity >= 0.7
    ]

    return SignalContext(
        active_count=len(recent_signals),
        critical_count=critical_count,
        high_severity_signals=high_severity[:5],  # cap at 5 for readability
    )
