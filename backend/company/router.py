"""
Company CRUD API router (V2 Phase 1).

Endpoints:
  POST   /api/v1/companies              — Create company
  GET    /api/v1/companies              — List companies for current org
  GET    /api/v1/companies/{id}         — Get company by ID
  PATCH  /api/v1/companies/{id}         — Update company fields
  DELETE /api/v1/companies/{id}         — Delete company

V2.2 — Company ↔ Twin:
  GET    /api/v1/companies/{id}/twins   — List twins owned by company
  POST   /api/v1/companies/{id}/twins   — Create twin owned by company

V2.3 — Products:
  POST   /api/v1/companies/{id}/products  — Create product
  GET    /api/v1/companies/{id}/products  — List products (V2.4 prefill ready)
  GET    /api/v1/products/{id}            — Get product by ID
  PATCH  /api/v1/products/{id}            — Update product
  DELETE /api/v1/products/{id}            — Delete product
"""

import logging

from auth.dependencies import AuthContext, get_current_user, require_role
from auth.models import ROLE_ADMIN, ROLE_MEMBER
from company.models import Company
from company.product_models import Product
from company.product_schemas import (
    ProductCreateRequest,
    ProductListResponse,
    ProductResponse,
    ProductUpdateRequest,
)
from company.schemas import (
    CompanyArchiveResponse,
    CompanyCreateRequest,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdateRequest,
    CreateTwinForCompanyRequest,
)
from company.supplier_warehouse_models import Supplier, Warehouse
from company.supplier_warehouse_schemas import (
    SupplierCreateRequest,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdateRequest,
    WarehouseCreateRequest,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseUpdateRequest,
)
from database import get_db
from exceptions import NotFoundError
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.company")

router = APIRouter(prefix="/companies", tags=["Companies"])


def _company_to_response(c: Company) -> CompanyResponse:
    """Convert ORM model to response schema."""
    return CompanyResponse(
        id=c.id,
        name=c.name,
        industry=c.industry,
        country=c.country,
        is_archived=c.is_archived,
        created_at=c.created_at.isoformat() if c.created_at else None,
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
    )


# ---------------------------------------------------------------------------
# POST /companies
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
)
def create_company(
    payload: CompanyCreateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new company within the current organisation."""
    company = Company(
        name=payload.name,
        industry=payload.industry,
        country=payload.country,
        org_id=auth.org.id,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    logger.info(
        "Company created: id=%d name=%s (org=%d)", company.id, company.name, auth.org.id
    )
    return _company_to_response(company)


# ---------------------------------------------------------------------------
# GET /companies
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=CompanyListResponse,
)
def list_companies(
    limit: int = 50,
    offset: int = 0,
    include_archived: bool = False,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all companies belonging to the current organisation.

    By default excludes archived companies.
    Pass ?include_archived=true to include them.
    """
    base_filter = [Company.org_id == auth.org.id]
    if not include_archived:
        base_filter.append(Company.is_archived == False)  # noqa: E712

    total = (
        db.scalar(select(func.count()).select_from(Company).where(*base_filter)) or 0
    )
    companies = db.scalars(
        select(Company)
        .where(*base_filter)
        .order_by(Company.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return CompanyListResponse(
        total=total,
        companies=[_company_to_response(c) for c in companies],
    )


# ---------------------------------------------------------------------------
# GET /companies/{company_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
)
def get_company(
    company_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a single company by ID."""
    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.org_id == auth.org.id)
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")
    return _company_to_response(company)


# ---------------------------------------------------------------------------
# PATCH /companies/{company_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/{company_id}",
    response_model=CompanyResponse,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
)
def update_company(
    company_id: int,
    payload: CompanyUpdateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partially update a company — only provided fields are changed."""
    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.org_id == auth.org.id)
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")

    if payload.name is not None:
        company.name = payload.name
    if payload.industry is not None:
        company.industry = payload.industry
    if payload.country is not None:
        company.country = payload.country

    db.commit()
    db.refresh(company)
    logger.info("Company updated: id=%d (org=%d)", company_id, auth.org.id)
    return _company_to_response(company)


# ---------------------------------------------------------------------------
# DELETE /companies/{company_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{company_id}",
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
def delete_or_archive_company(
    company_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Safe company removal — Block Delete + Archive workflow.

    Behaviour:
      - If the company has ANY dependent records (products, suppliers, warehouses,
        twins, or simulations), return HTTP 409 CONFLICT with dependency counts.
        The client should offer "Archive instead" as the recommended action.

      - If the company has zero dependent records, archive it (is_archived=True)
        rather than hard-deleting, so the record can be recovered if needed.

    Why not hard-delete?
      Hard-deleting a company with twins/simulations would either:
        a) Raise ForeignKeyViolation (500 Internal Server Error visible to user), or
        b) Cascade-destroy months of intelligence data in one click.
      Neither is acceptable for a production SaaS product.
    """
    from company.product_models import Product
    from company.supplier_warehouse_models import Supplier, Warehouse
    from digital_twin.models import DigitalTwin
    from fastapi import HTTPException

    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.org_id == auth.org.id)
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")

    # ── Count all dependent records ────────────────────────────────────────
    product_count = (
        db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.company_id == company_id)
        )
        or 0
    )
    supplier_count = (
        db.scalar(
            select(func.count())
            .select_from(Supplier)
            .where(Supplier.company_id == company_id)
        )
        or 0
    )
    warehouse_count = (
        db.scalar(
            select(func.count())
            .select_from(Warehouse)
            .where(Warehouse.company_id == company_id)
        )
        or 0
    )
    twin_count = (
        db.scalar(
            select(func.count())
            .select_from(DigitalTwin)
            .where(DigitalTwin.company_id == company_id)
        )
        or 0
    )

    # Count simulations linked to this company
    import models as sim_models

    simulation_count = (
        db.scalar(
            select(func.count())
            .select_from(sim_models.Simulation)
            .where(sim_models.Simulation.company_id == company_id)
        )
        or 0
    )

    total_dependent = (
        product_count + supplier_count + warehouse_count + twin_count + simulation_count
    )

    # ── BLOCK: company has data → 409 with counts ──────────────────────────
    if total_dependent > 0:
        parts = []
        if twin_count:
            parts.append(f"{twin_count} twin{'s' if twin_count != 1 else ''}")
        if simulation_count:
            parts.append(
                f"{simulation_count} simulation{'s' if simulation_count != 1 else ''}"
            )
        if product_count:
            parts.append(f"{product_count} product{'s' if product_count != 1 else ''}")
        if supplier_count:
            parts.append(
                f"{supplier_count} supplier{'s' if supplier_count != 1 else ''}"
            )
        if warehouse_count:
            parts.append(
                f"{warehouse_count} warehouse{'s' if warehouse_count != 1 else ''}"
            )

        summary = ", ".join(parts)
        logger.warning(
            "Company delete blocked: id=%d has %s (org=%d)",
            company_id,
            summary,
            auth.org.id,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error": "company_has_data",
                "message": (
                    f"'{company.name}' contains {summary}. "
                    f"Archive it instead to preserve all data."
                ),
                "counts": {
                    "products": product_count,
                    "suppliers": supplier_count,
                    "warehouses": warehouse_count,
                    "twins": twin_count,
                    "simulations": simulation_count,
                },
                "recommended_action": "archive",
            },
        )

    # ── ARCHIVE: no dependent records → safe to archive ───────────────────
    company.is_archived = True
    db.commit()
    logger.info(
        "Company archived: id=%d name=%s (org=%d)",
        company_id,
        company.name,
        auth.org.id,
    )
    return CompanyArchiveResponse(
        id=company.id,
        name=company.name,
        is_archived=True,
        message=f"'{company.name}' has been archived. No data was deleted.",
    )


@router.patch(
    "/{company_id}/archive",
    response_model=CompanyArchiveResponse,
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
def archive_company(
    company_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Archive a company regardless of whether it has data.

    Use this when the user explicitly chooses to archive instead of delete.
    All data (twins, simulations, signals, forecasts, products, suppliers,
    warehouses) is preserved. The company is hidden from active listings
    but remains accessible with ?include_archived=true.
    """
    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.org_id == auth.org.id)
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")

    company.is_archived = True
    db.commit()
    logger.info(
        "Company explicitly archived: id=%d name=%s (org=%d)",
        company_id,
        company.name,
        auth.org.id,
    )
    return CompanyArchiveResponse(
        id=company.id,
        name=company.name,
        is_archived=True,
        message=f"'{company.name}' has been archived. All data is preserved.",
    )


@router.patch(
    "/{company_id}/unarchive",
    response_model=CompanyArchiveResponse,
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
def unarchive_company(
    company_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restore an archived company to active status."""
    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.org_id == auth.org.id)
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")

    company.is_archived = False
    db.commit()
    logger.info(
        "Company unarchived: id=%d name=%s (org=%d)",
        company_id,
        company.name,
        auth.org.id,
    )
    return CompanyArchiveResponse(
        id=company.id,
        name=company.name,
        is_archived=False,
        message=f"'{company.name}' has been restored to active status.",
    )


# ---------------------------------------------------------------------------
# V2.2 — GET /companies/{company_id}/twins
# ---------------------------------------------------------------------------


@router.get(
    "/{company_id}/twins",
    tags=["Companies"],
)
def list_company_twins(
    company_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all Digital Twins owned by a specific company.

    Returns enriched twin summaries including simulation_count,
    signal counts from signal_events, and health score from
    the latest signals summary — so the company page shows real
    intelligence data per twin, not just names.
    """
    # Verify company belongs to this org
    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.org_id == auth.org.id)
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")

    from digital_twin.models import DigitalTwin, SignalEvent
    from sqlalchemy import func as sqlfunc

    twins = db.scalars(
        select(DigitalTwin)
        .where(
            DigitalTwin.company_id == company_id,
            DigitalTwin.org_id == auth.org.id,
        )
        .order_by(DigitalTwin.updated_at.desc())
    ).all()

    result = []
    for twin in twins:
        # Count total signals for this twin
        signal_count = (
            db.scalar(
                select(sqlfunc.count())
                .select_from(SignalEvent)
                .where(SignalEvent.twin_id == twin.id)
            )
            or 0
        )

        # Compute simple health score from last 10 signals
        recent_signals = db.scalars(
            select(SignalEvent)
            .where(SignalEvent.twin_id == twin.id)
            .order_by(SignalEvent.created_at.desc())
            .limit(10)
        ).all()

        health_score = 1.0
        if recent_signals:
            n = len(recent_signals)
            total_weight = 0.0
            weighted_sev = 0.0
            for i, sig in enumerate(recent_signals):
                w = n - i
                weighted_sev += sig.severity * w
                total_weight += w
            if total_weight > 0:
                health_score = round(
                    max(0.0, min(1.0, 1.0 - weighted_sev / total_weight)), 4
                )

        result.append(
            {
                "id": twin.id,
                "name": twin.name,
                "company_id": twin.company_id,
                "simulation_count": twin.simulation_count,
                "signal_count": signal_count,
                "health_score": health_score,
                "created_at": twin.created_at.isoformat() if twin.created_at else None,
                "updated_at": twin.updated_at.isoformat() if twin.updated_at else None,
            }
        )

    return result


# ---------------------------------------------------------------------------
# V2.2 — POST /companies/{company_id}/twins
# ---------------------------------------------------------------------------


@router.post(
    "/{company_id}/twins",
    status_code=status.HTTP_201_CREATED,
    tags=["Companies"],
    dependencies=[Depends(require_role(ROLE_MEMBER))],
)
def create_company_twin(
    company_id: int,
    payload: CreateTwinForCompanyRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Digital Twin owned by a specific company.

    Accepts: { "name": "Electronics Twin" }
    The twin is automatically scoped to this company and org.
    """
    # Verify company belongs to this org
    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.org_id == auth.org.id)
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")

    from digital_twin.manager import TwinManager

    mgr = TwinManager(db)
    twin = mgr.create_twin(name=payload.name)
    twin.org_id = auth.org.id
    twin.company_id = company_id
    db.commit()
    db.refresh(twin)

    logger.info(
        "Twin created under company: twin_id=%d company_id=%d org_id=%d",
        twin.id,
        company_id,
        auth.org.id,
    )

    return {
        "id": twin.id,
        "name": twin.name,
        "company_id": twin.company_id,
        "simulation_count": twin.simulation_count,
        "signal_count": 0,
        "health_score": 1.0,
        "created_at": twin.created_at.isoformat() if twin.created_at else None,
        "updated_at": twin.updated_at.isoformat() if twin.updated_at else None,
    }


# ---------------------------------------------------------------------------
# V2.3 — POST /companies/{company_id}/products
# ---------------------------------------------------------------------------


def _product_to_response(p: Product) -> ProductResponse:
    return ProductResponse(
        id=p.id,
        company_id=p.company_id,
        name=p.name,
        category=p.category,
        current_stock=p.current_stock,
        avg_monthly_demand=p.avg_monthly_demand,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


def _verify_company(company_id: int, org_id: int, db: Session) -> Company:
    """Raise NotFoundError if company doesn't belong to this org."""
    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.org_id == org_id)
    )
    if not company:
        raise NotFoundError(f"Company {company_id} not found")
    return company


@router.post(
    "/{company_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Products"],
)
def create_product(
    company_id: int,
    payload: ProductCreateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a product owned by a company.

    The current_stock and avg_monthly_demand fields are the V2.4
    prefill contract — they will auto-populate the simulation form
    when a product is selected.
    """
    _verify_company(company_id, auth.org.id, db)

    product = Product(
        company_id=company_id,
        name=payload.name,
        category=payload.category,
        current_stock=payload.current_stock,
        avg_monthly_demand=payload.avg_monthly_demand,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    logger.info(
        "Product created: id=%d name=%s company_id=%d",
        product.id,
        product.name,
        company_id,
    )
    return _product_to_response(product)


# ---------------------------------------------------------------------------
# V2.3 — GET /companies/{company_id}/products
# Designed for V2.4: returns current_stock + avg_monthly_demand for prefill
# ---------------------------------------------------------------------------


@router.get(
    "/{company_id}/products",
    response_model=ProductListResponse,
    tags=["Products"],
)
def list_company_products(
    company_id: int,
    limit: int = 100,
    offset: int = 0,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all products owned by a company.

    V2.4 note: each product in this response carries current_stock and
    avg_monthly_demand. The simulation form will call this endpoint,
    let the user select a product, then prefill stock and demand without
    any additional API calls or schema changes.
    """
    _verify_company(company_id, auth.org.id, db)

    total = (
        db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.company_id == company_id)
        )
        or 0
    )
    products = db.scalars(
        select(Product)
        .where(Product.company_id == company_id)
        .order_by(Product.name)
        .limit(limit)
        .offset(offset)
    ).all()
    return ProductListResponse(
        total=total,
        products=[_product_to_response(p) for p in products],
    )


# ---------------------------------------------------------------------------
# V2.3 — GET /products/{product_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{company_id}/products/{product_id}",
    response_model=ProductResponse,
    tags=["Products"],
)
def get_product(
    company_id: int,
    product_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single product by ID, verifying it belongs to the company."""
    _verify_company(company_id, auth.org.id, db)
    product = db.scalar(
        select(Product).where(
            Product.id == product_id, Product.company_id == company_id
        )
    )
    if not product:
        raise NotFoundError(f"Product {product_id} not found")
    return _product_to_response(product)


# ---------------------------------------------------------------------------
# V2.3 — PATCH /products/{product_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/{company_id}/products/{product_id}",
    response_model=ProductResponse,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Products"],
)
def update_product(
    company_id: int,
    product_id: int,
    payload: ProductUpdateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partially update a product."""
    _verify_company(company_id, auth.org.id, db)
    product = db.scalar(
        select(Product).where(
            Product.id == product_id, Product.company_id == company_id
        )
    )
    if not product:
        raise NotFoundError(f"Product {product_id} not found")

    if payload.name is not None:
        product.name = payload.name
    if payload.category is not None:
        product.category = payload.category
    if payload.current_stock is not None:
        product.current_stock = payload.current_stock
    if payload.avg_monthly_demand is not None:
        product.avg_monthly_demand = payload.avg_monthly_demand

    db.commit()
    db.refresh(product)
    logger.info("Product updated: id=%d company_id=%d", product_id, company_id)
    return _product_to_response(product)


# ---------------------------------------------------------------------------
# V2.3 — DELETE /products/{product_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{company_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Products"],
)
def delete_product(
    company_id: int,
    product_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a product."""
    _verify_company(company_id, auth.org.id, db)
    product = db.scalar(
        select(Product).where(
            Product.id == product_id, Product.company_id == company_id
        )
    )
    if not product:
        raise NotFoundError(f"Product {product_id} not found")
    db.delete(product)
    db.commit()
    logger.info("Product deleted: id=%d company_id=%d", product_id, company_id)


# ===========================================================================
# V2.5 — Suppliers
# ===========================================================================


def _supplier_to_resp(s: Supplier) -> SupplierResponse:
    return SupplierResponse(
        id=s.id,
        company_id=s.company_id,
        name=s.name,
        lead_time_days=s.lead_time_days,
        supply_status=s.supply_status,
        reliability_pct=s.reliability_pct,
        created_at=s.created_at.isoformat() if s.created_at else None,
        updated_at=s.updated_at.isoformat() if s.updated_at else None,
    )


def _warehouse_to_resp(w: Warehouse) -> WarehouseResponse:
    return WarehouseResponse(
        id=w.id,
        company_id=w.company_id,
        name=w.name,
        warehouse_id=w.warehouse_id,
        location=w.location,
        capacity=w.capacity,
        created_at=w.created_at.isoformat() if w.created_at else None,
        updated_at=w.updated_at.isoformat() if w.updated_at else None,
    )


@router.post(
    "/{company_id}/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Suppliers"],
)
def create_supplier(
    company_id: int,
    payload: SupplierCreateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a supplier.  lead_time_days → supplier_delay,  supply_status → supply_status."""
    _verify_company(company_id, auth.org.id, db)
    s = Supplier(
        company_id=company_id,
        name=payload.name,
        lead_time_days=payload.lead_time_days,
        supply_status=payload.supply_status,
        reliability_pct=payload.reliability_pct,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    logger.info("Supplier created: id=%d company_id=%d", s.id, company_id)
    return _supplier_to_resp(s)


@router.get(
    "/{company_id}/suppliers", response_model=SupplierListResponse, tags=["Suppliers"]
)
def list_company_suppliers(
    company_id: int,
    limit: int = 100,
    offset: int = 0,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all suppliers for a company (V2.5 prefill ready)."""
    _verify_company(company_id, auth.org.id, db)
    total = (
        db.scalar(
            select(func.count())
            .select_from(Supplier)
            .where(Supplier.company_id == company_id)
        )
        or 0
    )
    rows = db.scalars(
        select(Supplier)
        .where(Supplier.company_id == company_id)
        .order_by(Supplier.name)
        .limit(limit)
        .offset(offset)
    ).all()
    return SupplierListResponse(
        total=total, suppliers=[_supplier_to_resp(s) for s in rows]
    )


@router.get(
    "/{company_id}/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    tags=["Suppliers"],
)
def get_supplier(
    company_id: int,
    supplier_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_company(company_id, auth.org.id, db)
    s = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id, Supplier.company_id == company_id
        )
    )
    if not s:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    return _supplier_to_resp(s)


@router.patch(
    "/{company_id}/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Suppliers"],
)
def update_supplier(
    company_id: int,
    supplier_id: int,
    payload: SupplierUpdateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_company(company_id, auth.org.id, db)
    s = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id, Supplier.company_id == company_id
        )
    )
    if not s:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    if payload.name is not None:
        s.name = payload.name
    if payload.lead_time_days is not None:
        s.lead_time_days = payload.lead_time_days
    if payload.supply_status is not None:
        s.supply_status = payload.supply_status
    if payload.reliability_pct is not None:
        s.reliability_pct = payload.reliability_pct
    db.commit()
    db.refresh(s)
    return _supplier_to_resp(s)


@router.delete(
    "/{company_id}/suppliers/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Suppliers"],
)
def delete_supplier(
    company_id: int,
    supplier_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_company(company_id, auth.org.id, db)
    s = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id, Supplier.company_id == company_id
        )
    )
    if not s:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    db.delete(s)
    db.commit()


# ===========================================================================
# V2.5 — Warehouses
# ===========================================================================


@router.post(
    "/{company_id}/warehouses",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Warehouses"],
)
def create_warehouse(
    company_id: int,
    payload: WarehouseCreateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a warehouse.  warehouse_id (W1/W2/W3) → SimulationInput.warehouse."""
    _verify_company(company_id, auth.org.id, db)
    w = Warehouse(
        company_id=company_id,
        name=payload.name,
        warehouse_id=payload.warehouse_id,
        location=payload.location,
        capacity=payload.capacity,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    logger.info(
        "Warehouse created: id=%d company_id=%d wh=%s", w.id, company_id, w.warehouse_id
    )
    return _warehouse_to_resp(w)


@router.get(
    "/{company_id}/warehouses",
    response_model=WarehouseListResponse,
    tags=["Warehouses"],
)
def list_company_warehouses(
    company_id: int,
    limit: int = 100,
    offset: int = 0,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all warehouses for a company (V2.5 prefill ready)."""
    _verify_company(company_id, auth.org.id, db)
    total = (
        db.scalar(
            select(func.count())
            .select_from(Warehouse)
            .where(Warehouse.company_id == company_id)
        )
        or 0
    )
    rows = db.scalars(
        select(Warehouse)
        .where(Warehouse.company_id == company_id)
        .order_by(Warehouse.name)
        .limit(limit)
        .offset(offset)
    ).all()
    return WarehouseListResponse(
        total=total, warehouses=[_warehouse_to_resp(w) for w in rows]
    )


@router.get(
    "/{company_id}/warehouses/{warehouse_db_id}",
    response_model=WarehouseResponse,
    tags=["Warehouses"],
)
def get_warehouse(
    company_id: int,
    warehouse_db_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_company(company_id, auth.org.id, db)
    w = db.scalar(
        select(Warehouse).where(
            Warehouse.id == warehouse_db_id, Warehouse.company_id == company_id
        )
    )
    if not w:
        raise NotFoundError(f"Warehouse {warehouse_db_id} not found")
    return _warehouse_to_resp(w)


@router.patch(
    "/{company_id}/warehouses/{warehouse_db_id}",
    response_model=WarehouseResponse,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Warehouses"],
)
def update_warehouse(
    company_id: int,
    warehouse_db_id: int,
    payload: WarehouseUpdateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_company(company_id, auth.org.id, db)
    w = db.scalar(
        select(Warehouse).where(
            Warehouse.id == warehouse_db_id, Warehouse.company_id == company_id
        )
    )
    if not w:
        raise NotFoundError(f"Warehouse {warehouse_db_id} not found")
    if payload.name is not None:
        w.name = payload.name
    if payload.warehouse_id is not None:
        w.warehouse_id = payload.warehouse_id
    if payload.location is not None:
        w.location = payload.location
    if payload.capacity is not None:
        w.capacity = payload.capacity
    db.commit()
    db.refresh(w)
    return _warehouse_to_resp(w)


@router.delete(
    "/{company_id}/warehouses/{warehouse_db_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(ROLE_MEMBER))],
    tags=["Warehouses"],
)
def delete_warehouse(
    company_id: int,
    warehouse_db_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_company(company_id, auth.org.id, db)
    w = db.scalar(
        select(Warehouse).where(
            Warehouse.id == warehouse_db_id, Warehouse.company_id == company_id
        )
    )
    if not w:
        raise NotFoundError(f"Warehouse {warehouse_db_id} not found")
    db.delete(w)
    db.commit()
