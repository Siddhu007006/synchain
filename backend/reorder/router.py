"""
Reorder Recommendation API Router (V3.0 Sprint A).

Endpoints:
  GET /api/v1/companies/{company_id}/recommendations
    → List all product recommendations + inventory health score

  GET /api/v1/companies/{company_id}/inventory-health
    → Inventory health score only (executive KPI)

  GET /api/v1/products/{product_id}/recommendation
    → Single product recommendation

All endpoints:
  - Require authentication
  - Respect org-scoping
  - Return explainable recommendations with reasoning chains
"""

import logging

from auth.dependencies import AuthContext, get_current_user
from company.models import Company
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from reorder.engine import calculate_inventory_health
from reorder.schemas import (
    FinancialImpactResponse,
    InventoryHealthComponent,
    InventoryHealthResponse,
    RecommendationListResponse,
    ReorderRecommendation,
    SingleRecommendationResponse,
)
from reorder.service import get_company_recommendations, get_product_recommendation
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.reorder")

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


def _result_to_schema(r):
    """Convert engine ReorderResult dataclass to Pydantic schema."""
    return ReorderRecommendation(
        product_id=r.product_id,
        product_name=r.product_name,
        company_id=r.company_id,
        severity=r.severity,
        current_stock=r.current_stock,
        forecast_demand=r.forecast_demand,
        daily_demand=r.daily_demand,
        days_until_stockout=r.days_until_stockout,
        stockout_date=r.stockout_date,
        reorder_point=r.reorder_point,
        safety_stock=r.safety_stock,
        lead_time_demand=r.lead_time_demand,
        recommended_quantity=r.recommended_quantity,
        recommended_supplier_id=r.recommended_supplier_id,
        recommended_supplier_name=r.recommended_supplier_name,
        supplier_lead_time_days=r.supplier_lead_time_days,
        recommended_order_date=r.recommended_order_date,
        confidence=r.confidence,
        recommendation_confidence=r.recommendation_confidence,
        financial_impact=FinancialImpactResponse(
            stockout_risk=r.financial_impact.stockout_risk,
            units_at_risk=r.financial_impact.units_at_risk,
            estimated_revenue_impact=r.financial_impact.estimated_revenue_impact,
            currency=r.financial_impact.currency,
            has_price_data=r.financial_impact.has_price_data,
        ),
        reasoning=r.reasoning,
    )


def _build_health_response(company_id: int, company_name: str, health: dict):
    """Convert inventory health dict to Pydantic schema."""
    return InventoryHealthResponse(
        company_id=company_id,
        company_name=company_name,
        score=health["score"],
        grade=health["grade"],
        components=InventoryHealthComponent(**health["components"]),
        total_products=health["total_products"],
        critical_count=health["critical_count"],
        high_count=health["high_count"],
    )


@router.get(
    "/companies/{company_id}/recommendations",
    response_model=RecommendationListResponse,
    summary="List reorder recommendations for all products in a company",
    description=(
        "Generates recommendations using the Reorder Point Model. "
        "Each recommendation includes quantity, supplier, order date, "
        "stockout projection, severity, financial impact, and a reasoning chain. "
        "Also returns company-level Inventory Health Score."
    ),
)
async def list_recommendations(
    company_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate and return reorder recommendations for all company products."""

    # Verify company exists and belongs to user's org
    company = (
        db.query(Company)
        .filter(
            Company.id == company_id,
            Company.org_id == auth.org.id,
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    results = get_company_recommendations(
        company_id=company_id,
        org_id=auth.org.id,
        db=db,
    )

    recommendations = [_result_to_schema(r) for r in results]

    critical_count = sum(1 for r in recommendations if r.severity == "CRITICAL")
    high_count = sum(1 for r in recommendations if r.severity == "HIGH")

    # Inventory Health Score
    health = calculate_inventory_health(results)
    health_response = _build_health_response(company_id, company.name, health)

    logger.info(
        "GET /companies/%d/recommendations → %d items "
        "(critical=%d, high=%d, health=%d/100)",
        company_id,
        len(recommendations),
        critical_count,
        high_count,
        health["score"],
    )

    return RecommendationListResponse(
        company_id=company_id,
        company_name=company.name,
        total=len(recommendations),
        critical_count=critical_count,
        high_count=high_count,
        inventory_health=health_response,
        recommendations=recommendations,
    )


@router.get(
    "/companies/{company_id}/inventory-health",
    response_model=InventoryHealthResponse,
    summary="Get inventory health score for a company (executive KPI)",
    description=(
        "Returns a single 0-100 score derived from: "
        "forecast confidence (30%), stockout risk (25%), "
        "signal health (25%), and supplier reliability (20%)."
    ),
)
async def get_inventory_health(
    company_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Inventory Health Score — the executive KPI."""

    company = (
        db.query(Company)
        .filter(
            Company.id == company_id,
            Company.org_id == auth.org.id,
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    results = get_company_recommendations(
        company_id=company_id,
        org_id=auth.org.id,
        db=db,
    )

    health = calculate_inventory_health(results)
    return _build_health_response(company_id, company.name, health)


@router.get(
    "/products/{product_id}/recommendation",
    response_model=SingleRecommendationResponse,
    summary="Get reorder recommendation for a single product",
)
async def product_recommendation(
    product_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate recommendation for one product."""

    result = get_product_recommendation(
        product_id=product_id,
        org_id=auth.org.id,
        db=db,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or not accessible",
        )

    return SingleRecommendationResponse(recommendation=_result_to_schema(result))
