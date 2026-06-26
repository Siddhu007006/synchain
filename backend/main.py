"""
SynChain — Supply Chain Decision API

Architecture:
  - FastAPI app with /api/v1/ versioned router
  - Config from pydantic-settings (backend/.env)
  - Alembic manages database schema (no create_all)
  - Structured error handling via exceptions.py
  - Phase E9: Structured logging, middleware, rate limiting,
    audit logging, metering, and production hardening
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

# Phase E9: Production Readiness
import audit.models  # noqa: F401 — registers audit tables

# Phase E8: Multi-tenant Auth
import auth.models  # noqa: F401 — registers auth tables with Base.metadata
import company.import_models  # noqa: F401 — registers import_jobs table (V2.6)

# V2 Phase 1: Company
import company.models  # noqa: F401 — registers companies table
import company.product_models  # noqa: F401 — registers products table (V2.3)
import company.supplier_warehouse_models  # noqa: F401 — registers suppliers + warehouses (V2.5)

# Phase E1: Digital Twin
import digital_twin.models  # noqa: F401 — registers tables with Base.metadata
import digital_twin.schemas as twin_schemas

# Phase E2: Forecasting
import forecasting.models  # noqa: F401 — registers tables with Base.metadata
import forecasting.schemas as forecast_schemas
import metering.models  # noqa: F401 — registers metering tables
import models
import schemas
import services

# Phase E5: External Intelligence
import signals.external_cache  # noqa: F401 — registers ExternalDataCache table
import signals.schemas as signal_schemas
from agents.scenario_agent import ScenarioAgent
from audit.router import router as audit_router
from audit.service import AuditService
from auth.dependencies import AuthContext, get_current_user, require_role
from auth.models import ROLE_ADMIN, ROLE_MEMBER
from auth.org_router import router as org_router
from auth.router import router as auth_router
from company.import_router import router as import_router
from company.router import router as company_router
from config import settings
from database import SessionLocal, get_db
from digital_twin.manager import TwinManager
from exceptions import NotFoundError, SimulationError, SynChainError, ValidationError
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from forecasting.engine import ForecastEngine
from logging_config import setup_logging
from metering.router import router as metering_router
from metering.service import MeteringService
from middleware import RequestIDMiddleware, SecurityHeadersMiddleware, TimingMiddleware
from rate_limiter import rate_limit

# V3.0 Sprint A: Reorder Recommendations
from reorder.router import router as reorder_router

# Phase E3: Signal Intelligence
from signals.engine import SignalEngine
from signals.external_cache import CacheManager

# Phase E7: Real API Providers
from signals.providers import get_active_provider_info
from signals.scheduler import (
    DEFAULT_CACHE_TTL_HOURS,
    DEFAULT_PROVIDER_MODE,
    DEFAULT_REFRESH_HOURS,
    refresh_all_providers,
    run_scheduler,
)
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Structured Logging Setup (E9)
# ---------------------------------------------------------------------------
setup_logging(log_level=settings.log_level, log_format=settings.log_format)
logger = logging.getLogger("synchain")

# App startup timestamp for uptime calculation
_app_start_time = time.time()

# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app_instance):
    """App lifespan: start/stop background scheduler.

    Schema management is handled exclusively by Alembic migrations.
    Do NOT add create_all() here.
    """
    # Start background scheduler
    scheduler_task = asyncio.create_task(
        run_scheduler(
            db_factory=SessionLocal,
            refresh_hours=DEFAULT_REFRESH_HOURS,
            mode=DEFAULT_PROVIDER_MODE,
            ttl_hours=DEFAULT_CACHE_TTL_HOURS,
        )
    )
    yield
    # Shutdown: cancel scheduler
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SynChain — Supply Chain Decision API",
    description="Multi-agent supply chain simulation with scenario analysis.",
    version=settings.app_version,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware stack (E9) — order: security → request_id → timing → CORS
# Outermost middleware executes first on request, last on response.
# ---------------------------------------------------------------------------
app.add_middleware(SecurityHeadersMiddleware, enable_hsts=not settings.debug)
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Structured error handler
# ---------------------------------------------------------------------------
@app.exception_handler(SynChainError)
async def synchain_error_handler(request: Request, exc: SynChainError):
    """Convert SynChainError subclasses to structured JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error_type": exc.error_type},
    )


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
_scenario_agent = ScenarioAgent()

# ---------------------------------------------------------------------------
# API v1 Router
# ---------------------------------------------------------------------------
v1 = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health (root — no prefix, always available)
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "message": "SynChain Decision API is running",
        "version": settings.app_version,
    }


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    """Enhanced health check with component status (E9)."""
    # Database health
    db_status = "ok"
    db_latency = 0.0
    try:
        start = time.time()
        db.execute(models.Simulation.__table__.select().limit(1))
        db_latency = (time.time() - start) * 1000
    except Exception:
        db_status = "error"

    uptime = time.time() - _app_start_time

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": settings.app_version,
        "components": {
            "database": {"status": db_status, "latency_ms": round(db_latency, 1)},
        },
        "uptime_seconds": round(uptime),
    }


@app.get("/ready", tags=["Health"])
def readiness_probe(db: Session = Depends(get_db)):
    """Readiness probe — returns 200 if DB is connectable (E9)."""
    try:
        db.execute(models.Simulation.__table__.select().limit(1))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.get("/live", tags=["Health"])
def liveness_probe():
    """Liveness probe — returns 200 if process is alive (E9)."""
    return {"status": "alive"}


# ---------------------------------------------------------------------------
# Simulation endpoints
# ---------------------------------------------------------------------------


@v1.post(
    "/simulate",
    response_model=schemas.SimulationCreateResponse,
    tags=["Simulation"],
    dependencies=[Depends(require_role(ROLE_MEMBER)), Depends(rate_limit("write"))],
)
def simulate(
    payload: schemas.SimulationInput,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run a supply chain simulation and persist results.

    If twin_id is provided, the linked Digital Twin's state is updated
    after the simulation completes (EWMA smoothing + history logging).
    Requires member role or higher.
    """
    # Validate twin_id if provided (with org_id isolation)
    if payload.twin_id is not None:
        mgr = TwinManager(db)
        twin = mgr.get_twin(payload.twin_id)
        if not twin or twin.org_id != auth.org.id:
            raise NotFoundError(f"Digital Twin {payload.twin_id} not found")

    sim = models.Simulation(
        product=payload.product,
        stock=payload.stock,
        warehouse=payload.warehouse,
        demand=payload.demand,
        supplier_delay=payload.supplier_delay,
        market_trend=payload.market_trend,
        supply_status=payload.supply_status,
        season=payload.season,
        twin_id=payload.twin_id,
        org_id=auth.org.id,
        # V2.4: traceability links
        product_id=payload.product_id,
        company_id=payload.company_id,
        # V2.5: traceability links
        supplier_id=payload.supplier_id,
        warehouse_record_id=payload.warehouse_record_id,
    )
    db.add(sim)
    db.commit()
    db.refresh(sim)

    try:
        result_data = services.simulate_supply_chain(payload)
    except Exception as exc:
        db.delete(sim)
        db.commit()
        logger.exception("Pipeline failed for simulation %d", sim.id)
        raise SimulationError(f"Agent pipeline failed: {exc}") from exc

    breakdown_json = json.dumps(
        [item.model_dump() for item in result_data.agent_breakdown]
    )

    result = models.Result(
        simulation_id=sim.id,
        demand_forecast=result_data.demand_forecast,
        recommended_inventory=result_data.recommended_inventory,
        selected_warehouse=result_data.selected_warehouse,
        route=result_data.route,
        risk=result_data.risk,
        strategy=result_data.strategy,
        agent_breakdown=breakdown_json,
        overall_confidence=result_data.overall_confidence,
        explanation=result_data.explanation,
    )
    db.add(result)
    db.commit()

    # Phase E: Auto-update twin state after successful simulation
    if payload.twin_id is not None:
        try:
            mgr = TwinManager(db)
            mgr.update_state_from_simulation(
                twin_id=payload.twin_id,
                sim_input=payload.model_dump(),
                sim_result=result_data.model_dump(),
            )
        except Exception:
            logger.exception(
                "Twin state update failed for twin %d (non-blocking)",
                payload.twin_id,
            )
            # Non-blocking: simulation still succeeds even if twin update fails

    # E9: Audit + Metering
    AuditService(db).log(
        action="simulation.create",
        resource_type="Simulation",
        resource_id=sim.id,
        user_id=auth.user.id,
        org_id=auth.org.id,
        details={"product": payload.product, "warehouse": payload.warehouse},
    )
    MeteringService(db).record(
        org_id=auth.org.id,
        event_type="simulation.run",
        metadata={"simulation_id": sim.id, "product": payload.product},
    )

    return schemas.SimulationCreateResponse(
        simulation_id=sim.id,
        status="completed",
    )


# ---------------------------------------------------------------------------
# V2.4 helpers — resolve product/company names for simulation detail response
# ---------------------------------------------------------------------------


def _resolve_product_name(product_id, db):
    if not product_id:
        return None
    from company.product_models import Product
    from sqlalchemy import select as _sel

    p = db.scalar(_sel(Product).where(Product.id == product_id))
    return p.name if p else None


def _resolve_company_name(company_id, db):
    if not company_id:
        return None
    from company.models import Company
    from sqlalchemy import select as _sel

    c = db.scalar(_sel(Company).where(Company.id == company_id))
    return c.name if c else None


@v1.get(
    "/simulate/{simulation_id}",
    response_model=schemas.SimulationDetailResponse,
    tags=["Simulation"],
)
def get_simulation(
    simulation_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a completed simulation by ID."""
    sim = (
        db.query(models.Simulation)
        .filter(
            models.Simulation.id == simulation_id,
            models.Simulation.org_id == auth.org.id,
        )
        .first()
    )

    if not sim:
        raise NotFoundError(f"Simulation {simulation_id} not found")
    if not sim.result:
        raise NotFoundError(f"Result for simulation {simulation_id} not found")

    breakdown_items = []
    if sim.result.agent_breakdown:
        try:
            raw = json.loads(sim.result.agent_breakdown)
            breakdown_items = [schemas.AgentBreakdownItem(**item) for item in raw]
        except (json.JSONDecodeError, TypeError):
            breakdown_items = []

    return schemas.SimulationDetailResponse(
        simulation_id=sim.id,
        input=schemas.SimulationInput(
            product=sim.product,
            stock=sim.stock,
            warehouse=sim.warehouse,
            demand=sim.demand,
            supplier_delay=sim.supplier_delay,
            market_trend=sim.market_trend,
            supply_status=sim.supply_status,
            season=sim.season,
        ),
        result=schemas.SimulationResult(
            demand_forecast=sim.result.demand_forecast,
            recommended_inventory=sim.result.recommended_inventory,
            selected_warehouse=sim.result.selected_warehouse,
            route=sim.result.route,
            risk=sim.result.risk,
            strategy=sim.result.strategy,
            agent_breakdown=breakdown_items,
            overall_confidence=sim.result.overall_confidence or 0.0,
            explanation=sim.result.explanation or "",
        ),
        # V2.4 traceability — resolve names from FKs
        product_id=sim.product_id,
        product_name=_resolve_product_name(sim.product_id, db),
        company_id=sim.company_id,
        company_name=_resolve_company_name(sim.company_id, db),
    )


# ---------------------------------------------------------------------------
# Scenario Comparison
# ---------------------------------------------------------------------------


@v1.get(
    "/simulate/{simulation_id}/scenarios",
    response_model=schemas.ScenarioResponse,
    tags=["Scenarios"],
)
def get_scenarios(
    simulation_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run 4 what-if disruption scenarios against a stored simulation."""
    sim = (
        db.query(models.Simulation)
        .filter(
            models.Simulation.id == simulation_id,
            models.Simulation.org_id == auth.org.id,
        )
        .first()
    )

    if not sim:
        raise NotFoundError(f"Simulation {simulation_id} not found")
    if not sim.result:
        raise NotFoundError(f"Result for simulation {simulation_id} not found")

    base_input = schemas.SimulationInput(
        product=sim.product,
        stock=sim.stock,
        warehouse=sim.warehouse,
        demand=sim.demand,
        supplier_delay=sim.supplier_delay,
        market_trend=sim.market_trend,
        supply_status=sim.supply_status,
        season=sim.season,
    )

    base_result = schemas.SimulationResult(
        demand_forecast=sim.result.demand_forecast,
        recommended_inventory=sim.result.recommended_inventory,
        selected_warehouse=sim.result.selected_warehouse,
        route=sim.result.route,
        risk=sim.result.risk,
        strategy=sim.result.strategy,
        overall_confidence=sim.result.overall_confidence or 0.0,
        explanation=sim.result.explanation or "",
    )

    try:
        raw_comparisons = _scenario_agent.run(
            base_input=base_input,
            base_result=base_result,
            run_pipeline=services.simulate_supply_chain,
        )
    except Exception as exc:
        logger.exception("Scenario analysis failed for simulation %d", simulation_id)
        raise SimulationError(f"Scenario analysis failed: {exc}") from exc

    base_summary = schemas.ScenarioResultSummary(
        demand_forecast=base_result.demand_forecast,
        recommended_inventory=base_result.recommended_inventory,
        selected_warehouse=base_result.selected_warehouse,
        route=base_result.route,
        risk=base_result.risk,
        overall_confidence=base_result.overall_confidence,
        strategy=base_result.strategy,
    )

    scenario_comparisons = [
        schemas.ScenarioComparison(
            scenario_name=comp["scenario_name"],
            scenario_description=comp["scenario_description"],
            modified_input=schemas.SimulationInput(**comp["modified_input"]),
            result=schemas.ScenarioResultSummary(**comp["result"]),
            impact=schemas.ScenarioImpact(**comp["impact"]),
        )
        for comp in raw_comparisons
    ]

    return schemas.ScenarioResponse(
        simulation_id=simulation_id,
        base_result=base_summary,
        scenarios=scenario_comparisons,
    )


# ---------------------------------------------------------------------------
# Simulation History
# ---------------------------------------------------------------------------


@v1.get(
    "/simulations",
    response_model=list[schemas.SimulationSummary],
    tags=["History"],
)
def list_simulations(
    limit: int = 20,
    company_id: int | None = None,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List past simulation summaries (most recent first).

    Optional company_id filter for company-scoped dashboards (V2.7).
    """
    query = db.query(models.Simulation).filter(models.Simulation.org_id == auth.org.id)
    if company_id is not None:
        query = query.filter(models.Simulation.company_id == company_id)

    sims = query.order_by(models.Simulation.created_at.desc()).limit(limit).all()

    return [
        schemas.SimulationSummary(
            simulation_id=sim.id,
            product=sim.product,
            warehouse=sim.warehouse,
            demand=sim.demand,
            risk=sim.result.risk if sim.result else None,
            overall_confidence=sim.result.overall_confidence if sim.result else None,
            demand_forecast=sim.result.demand_forecast if sim.result else None,
            created_at=sim.created_at.isoformat() if sim.created_at else None,
        )
        for sim in sims
    ]


# ---------------------------------------------------------------------------
# Digital Twin endpoints (Phase E)
# ---------------------------------------------------------------------------


@v1.post(
    "/twins",
    response_model=twin_schemas.TwinSummary,
    tags=["Digital Twin"],
    dependencies=[Depends(require_role(ROLE_MEMBER))],
)
def create_twin(
    payload: twin_schemas.TwinCreateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new Digital Twin with pre-initialized state domains."""
    # V2.2: validate company_id belongs to this org
    if payload.company_id is not None:
        from company.models import Company

        company = (
            db.query(Company)
            .filter(
                Company.id == payload.company_id,
                Company.org_id == auth.org.id,
            )
            .first()
        )
        if not company:
            raise NotFoundError(f"Company {payload.company_id} not found")

    mgr = TwinManager(db)
    twin = mgr.create_twin(name=payload.name)
    twin.org_id = auth.org.id
    # V2.2: set company ownership
    if payload.company_id is not None:
        twin.company_id = payload.company_id
    db.commit()
    return twin_schemas.TwinSummary(
        id=twin.id,
        name=twin.name,
        simulation_count=twin.simulation_count,
        company_id=twin.company_id,
        created_at=twin.created_at.isoformat() if twin.created_at else None,
        updated_at=twin.updated_at.isoformat() if twin.updated_at else None,
    )


@v1.get(
    "/twins",
    response_model=list[twin_schemas.TwinSummary],
    tags=["Digital Twin"],
)
def list_twins(
    company_id: int | None = None,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List Digital Twins for the current organization.

    Optionally filter by company_id (V2.2).
    """
    from digital_twin.models import DigitalTwin

    query = db.query(DigitalTwin).filter(DigitalTwin.org_id == auth.org.id)
    if company_id is not None:
        query = query.filter(DigitalTwin.company_id == company_id)
    twins = query.all()
    return [
        twin_schemas.TwinSummary(
            id=t.id,
            name=t.name,
            simulation_count=t.simulation_count,
            company_id=t.company_id,
            created_at=t.created_at.isoformat() if t.created_at else None,
            updated_at=t.updated_at.isoformat() if t.updated_at else None,
        )
        for t in twins
    ]


@v1.get(
    "/twins/{twin_id}",
    response_model=twin_schemas.TwinDetailResponse,
    tags=["Digital Twin"],
)
def get_twin(
    twin_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a Digital Twin with full state snapshot."""
    mgr = TwinManager(db)
    twin = mgr.get_twin(twin_id)
    if not twin or twin.org_id != auth.org.id:
        raise NotFoundError(f"Digital Twin {twin_id} not found")

    return twin_schemas.TwinDetailResponse(
        id=twin.id,
        name=twin.name,
        simulation_count=twin.simulation_count,
        created_at=twin.created_at.isoformat() if twin.created_at else None,
        updated_at=twin.updated_at.isoformat() if twin.updated_at else None,
        product_states=[
            twin_schemas.ProductStateSnapshot(
                product_name=ps.product_name,
                latest_stock=ps.latest_stock,
                latest_demand=ps.latest_demand,
                avg_demand=ps.avg_demand,
                demand_trend=ps.demand_trend,
                simulation_count=ps.simulation_count,
                updated_at=ps.updated_at.isoformat() if ps.updated_at else None,
            )
            for ps in twin.product_states
        ],
        warehouse_states=[
            twin_schemas.WarehouseStateSnapshot(
                warehouse_id=ws.warehouse_id,
                times_selected=ws.times_selected,
                utilization_pct=ws.utilization_pct,
                selection_rate=ws.selection_rate,
                avg_delivery_score=ws.avg_delivery_score,
                avg_risk_score=ws.avg_risk_score,
                updated_at=ws.updated_at.isoformat() if ws.updated_at else None,
            )
            for ws in twin.warehouse_states
        ],
        supplier_state=(
            twin_schemas.SupplierStateSnapshot(
                avg_delay=twin.supplier_state.avg_delay,
                max_delay_seen=twin.supplier_state.max_delay_seen,
                reliability_score=twin.supplier_state.reliability_score,
                supply_status_mode=twin.supplier_state.supply_status_mode,
                updated_at=(
                    twin.supplier_state.updated_at.isoformat()
                    if twin.supplier_state.updated_at
                    else None
                ),
            )
            if twin.supplier_state
            else None
        ),
        market_state=(
            twin_schemas.MarketStateSnapshot(
                trend_mode=twin.market_state.trend_mode,
                season_mode=twin.market_state.season_mode,
                avg_confidence=twin.market_state.avg_confidence,
                avg_risk_score=twin.market_state.avg_risk_score,
                updated_at=(
                    twin.market_state.updated_at.isoformat()
                    if twin.market_state.updated_at
                    else None
                ),
            )
            if twin.market_state
            else None
        ),
    )


@v1.get(
    "/twins/{twin_id}/history",
    response_model=twin_schemas.TwinHistoryResponse,
    tags=["Digital Twin"],
)
def get_twin_history(
    twin_id: int,
    limit: int = 100,
    offset: int = 0,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get state change history for a Digital Twin."""
    mgr = TwinManager(db)
    twin = mgr.get_twin(twin_id)
    if not twin or twin.org_id != auth.org.id:
        raise NotFoundError(f"Digital Twin {twin_id} not found")

    entries = mgr.get_history(twin_id, limit=limit, offset=offset)
    total = mgr.count_history(twin_id)

    return twin_schemas.TwinHistoryResponse(
        twin_id=twin_id,
        total_entries=total,
        entries=[
            twin_schemas.StateHistoryEntry(
                id=e.id,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                field_name=e.field_name,
                old_value=e.old_value,
                new_value=e.new_value,
                changed_at=e.changed_at.isoformat() if e.changed_at else None,
            )
            for e in entries
        ],
    )


@v1.delete(
    "/twins/{twin_id}",
    tags=["Digital Twin"],
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
def delete_twin(
    twin_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a Digital Twin and all related state. Requires admin role."""
    mgr = TwinManager(db)
    twin = mgr.get_twin(twin_id)
    if not twin or twin.org_id != auth.org.id:
        raise NotFoundError(f"Digital Twin {twin_id} not found")
    mgr.delete_twin(twin_id)
    return {"status": "deleted", "twin_id": twin_id}


# ---------------------------------------------------------------------------
# Forecasting endpoints (Phase E2)
# ---------------------------------------------------------------------------


@v1.get(
    "/twins/{twin_id}/forecast",
    response_model=forecast_schemas.ForecastResponse,
    tags=["Forecasting"],
)
def generate_forecast(
    twin_id: int,
    product: str,
    horizons: str = "1,3,5",
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate demand forecasts for a product using Digital Twin state.

    Reads current twin state (EWMA averages, trends, season, supplier
    reliability) and produces deterministic multi-horizon forecasts.
    Each forecast is persisted for audit trail.

    Args:
        twin_id: Digital Twin ID.
        product: Product name to forecast (must have simulation history).
        horizons: Comma-separated horizon periods (default: "1,3,5").
    """
    # Parse horizons
    try:
        horizon_list = [int(h.strip()) for h in horizons.split(",") if h.strip()]
    except ValueError:
        raise ValidationError(
            "horizons must be comma-separated integers (e.g. '1,3,5')"
        )

    if not horizon_list:
        raise ValidationError("At least one horizon is required")

    if any(h < 1 for h in horizon_list):
        raise ValidationError("Horizons must be positive integers")

    engine = ForecastEngine(db)
    result = engine.generate(twin_id=twin_id, product=product, horizons=horizon_list)

    if result is None:
        raise NotFoundError(
            f"Twin {twin_id} not found or product '{product}' has no simulation history"
        )

    import json as _json
    from datetime import datetime, timezone

    # Build active_signals from SignalEvent objects
    active_signal_entries = []
    for sig in result.get("active_signals", []):
        payload = (
            sig.payload
            if isinstance(sig.payload, dict)
            else _json.loads(sig.payload or "{}")
        )
        active_signal_entries.append(
            signal_schemas.ActiveSignalEntry(
                source=sig.source,
                signal_type=sig.signal_type,
                severity=sig.severity,
                payload=payload,
                created_at=sig.created_at.isoformat() if sig.created_at else None,
            )
        )

    return forecast_schemas.ForecastResponse(
        twin_id=result["twin_id"],
        product=result["product"],
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_state=forecast_schemas.ForecastSourceState(**result["source_state"]),
        forecasts=[
            forecast_schemas.ForecastPointResponse(
                horizon=fp.horizon,
                forecast_demand=fp.forecast_demand,
                trend_factor=fp.trend_factor,
                season_factor=fp.season_factor,
                supply_risk=fp.supply_risk,
                confidence=fp.confidence,
                explanation=fp.explanation,
            )
            for fp in result["forecasts"]
        ],
        active_signals=active_signal_entries,
    )


@v1.get(
    "/twins/{twin_id}/forecasts",
    response_model=forecast_schemas.ForecastRecordsResponse,
    tags=["Forecasting"],
)
def list_forecast_records(
    twin_id: int,
    product: str | None = None,
    limit: int = 20,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List persisted forecast records for a twin (audit trail).

    Returns previously generated forecasts. Does NOT generate new ones.
    """
    mgr = TwinManager(db)
    if not mgr.get_twin(twin_id):
        raise NotFoundError(f"Digital Twin {twin_id} not found")

    engine = ForecastEngine(db)
    records = engine.list_records(twin_id=twin_id, product=product, limit=limit)

    return forecast_schemas.ForecastRecordsResponse(
        twin_id=twin_id,
        total_records=len(records),
        records=[
            forecast_schemas.ForecastRecordEntry(
                id=r.id,
                product_name=r.product_name,
                horizon=r.horizon,
                forecast_demand=r.forecast_demand,
                trend_factor=r.trend_factor,
                season_factor=r.season_factor,
                supply_risk=r.supply_risk,
                confidence=r.confidence,
                explanation=r.explanation,
                source_avg_demand=r.source_avg_demand,
                source_trend=r.source_trend,
                source_season=r.source_season,
                source_reliability=r.source_reliability,
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
            for r in records
        ],
    )


@v1.get(
    "/twins/{twin_id}/forecast/summary",
    response_model=forecast_schemas.ForecastSummaryResponse,
    tags=["Forecasting"],
)
def get_forecast_summary(
    twin_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get latest horizon-1 forecast summary for all products in a twin.

    Read-only — does NOT generate new forecasts. Only aggregates
    previously generated forecast records.
    """
    engine = ForecastEngine(db)
    summaries = engine.get_summary(twin_id)

    if summaries is None:
        raise NotFoundError(f"Digital Twin {twin_id} not found")

    return forecast_schemas.ForecastSummaryResponse(
        twin_id=twin_id,
        products=[
            forecast_schemas.ProductForecastSummary(
                product=s["product"],
                avg_demand=s["avg_demand"],
                demand_trend=s["demand_trend"],
                latest_forecast=(
                    forecast_schemas.LatestForecast(**s["latest_forecast"])
                    if s["latest_forecast"]
                    else None
                ),
            )
            for s in summaries
        ],
    )


# ---------------------------------------------------------------------------
# Signal Intelligence endpoints (Phase E3)
# ---------------------------------------------------------------------------


@v1.get(
    "/twins/{twin_id}/signals",
    response_model=signal_schemas.SignalListResponse,
    tags=["Signals"],
)
def list_signals(
    twin_id: int,
    signal_type: str | None = None,
    min_severity: float | None = None,
    limit: int = 50,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List signal events for a twin with optional filtering.

    Signals are emitted automatically after each simulation based on
    twin state analysis. They provide early warnings about demand spikes,
    supplier degradation, warehouse overload, and trend shifts.
    """
    mgr = TwinManager(db)
    if not mgr.get_twin(twin_id):
        raise NotFoundError(f"Digital Twin {twin_id} not found")

    import json as _json

    sig_engine = SignalEngine(db)
    signals = sig_engine.list_signals(
        twin_id=twin_id,
        signal_type=signal_type,
        min_severity=min_severity,
        limit=limit,
    )

    def _severity_label(sev: float) -> str:
        if sev >= 0.7:
            return "critical"
        elif sev >= 0.3:
            return "warning"
        return "info"

    return signal_schemas.SignalListResponse(
        twin_id=twin_id,
        total_signals=len(signals),
        signals=[
            signal_schemas.SignalEventEntry(
                id=s.id,
                source=s.source,
                signal_type=s.signal_type,
                severity=s.severity,
                severity_label=_severity_label(s.severity),
                payload=(
                    _json.loads(s.payload) if isinstance(s.payload, str) else s.payload
                ),
                created_at=s.created_at.isoformat() if s.created_at else None,
            )
            for s in signals
        ],
    )


@v1.get(
    "/twins/{twin_id}/signals/summary",
    response_model=signal_schemas.SignalSummaryResponse,
    tags=["Signals"],
)
def get_signal_summary(
    twin_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get aggregated signal overview with health score.

    Health score = 1.0 - weighted_avg_severity(last 10 signals).
    Newer signals carry more weight. No signals = 1.0 (healthy).
    """
    mgr = TwinManager(db)
    if not mgr.get_twin(twin_id):
        raise NotFoundError(f"Digital Twin {twin_id} not found")

    import json as _json

    sig_engine = SignalEngine(db)
    summary = sig_engine.get_summary(twin_id)

    def _severity_label(sev: float) -> str:
        if sev >= 0.7:
            return "critical"
        elif sev >= 0.3:
            return "warning"
        return "info"

    latest_critical_entry = None
    if summary["latest_critical"]:
        lc = summary["latest_critical"]
        latest_critical_entry = signal_schemas.SignalEventEntry(
            id=lc.id,
            source=lc.source,
            signal_type=lc.signal_type,
            severity=lc.severity,
            severity_label=_severity_label(lc.severity),
            payload=(
                _json.loads(lc.payload) if isinstance(lc.payload, str) else lc.payload
            ),
            created_at=lc.created_at.isoformat() if lc.created_at else None,
        )

    return signal_schemas.SignalSummaryResponse(
        twin_id=twin_id,
        total_signals=summary["total_signals"],
        by_type=signal_schemas.SignalCountByType(**summary["by_type"]),
        by_severity=signal_schemas.SignalCountBySeverity(**summary["by_severity"]),
        latest_critical=latest_critical_entry,
        health_score=summary["health_score"],
    )


# ---------------------------------------------------------------------------
# Mount versioned router
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Phase E5: External Intelligence Endpoints
# ---------------------------------------------------------------------------


@v1.get("/external/status", tags=["External Intelligence"])
def get_external_status(db: Session = Depends(get_db)):
    """
    Get cache status for all external data providers.

    E7 enhancement: includes active provider name, mode, and API key status
    for each category. API keys are never exposed — only their presence is
    reported (configured: true/false).
    """
    cache = CacheManager(db)
    entries = cache.get_all_status()
    provider_info = get_active_provider_info()

    # Build provider-keyed status with E7 mode/health info
    providers = {}
    for e in entries:
        provider_name = e["provider"]
        # Find which category this provider belongs to
        category = None
        for cat, info in provider_info.items():
            if (
                info["active_provider"] == provider_name
                or f"{cat}_synthetic" == provider_name
            ):
                category = cat
                break

        providers[provider_name] = {
            "category": category,
            "mode": "real" if "_real" in provider_name else "synthetic",
            "api_key_configured": (
                provider_info.get(category, {}).get("configured", False)
                if category
                else False
            ),
            "last_refresh": e["last_refresh"],
            "cached": e["cached"],
            "schema_version": e["schema_version"],
            "expires_in_minutes": e["expires_in_minutes"],
            "is_valid": e["is_valid"],
        }

    return {
        "provider_mode": settings.external_provider_mode,
        "providers": providers,
        "refresh_interval_hours": DEFAULT_REFRESH_HOURS,
        "cache_ttl_hours": DEFAULT_CACHE_TTL_HOURS,
    }


@v1.get("/external/config", tags=["External Intelligence"])
def get_external_config():
    """
    Inspect provider configuration without exposing secrets.

    E7 endpoint: Shows which providers are active for each category,
    whether API keys are configured, and the current provider mode.
    API keys are NEVER included in the response.
    """
    provider_info = get_active_provider_info()

    return {
        "mode": settings.external_provider_mode,
        "refresh_interval_hours": DEFAULT_REFRESH_HOURS,
        "cache_ttl_hours": DEFAULT_CACHE_TTL_HOURS,
        "providers": provider_info,
    }


@v1.post(
    "/external/refresh",
    tags=["External Intelligence"],
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
def trigger_external_refresh(
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger a refresh of all external data providers.

    Uses the configured provider mode (auto/synthetic/real).
    In auto mode, each category uses its real provider if an API key
    is configured, otherwise falls back to synthetic.
    """
    mode = settings.external_provider_mode
    results = refresh_all_providers(
        db,
        mode=mode,
        ttl_hours=DEFAULT_CACHE_TTL_HOURS,
    )
    return {
        "refreshed": True,
        "mode_used": mode,
        "results": results,
    }


@v1.get("/compound-rules", tags=["Compound Signals"])
def list_compound_rules():
    """
    List all registered compound signal rules.

    Read-only introspection endpoint — rules are defined in code,
    not user-editable. Shows trigger requirements, severity functions,
    confidence weights, and risk elevation eligibility for each rule.
    """
    from signals.compound import COMPOUND_RULES

    rules = []
    for rule in COMPOUND_RULES:
        rules.append(
            {
                "name": rule.name,
                "triggers": list(rule.triggers),
                "severity_fn": rule.severity_fn,
                "severity_boost": rule.severity_boost,
                "min_trigger_severity": rule.min_trigger_severity,
                "confidence_weight": rule.confidence_weight,
                "can_elevate_risk": rule.can_elevate_risk,
                "description": rule.description,
            }
        )

    return {
        "total_rules": len(rules),
        "rules": rules,
    }


# Phase E8: Register auth and org routers
v1.include_router(auth_router)
v1.include_router(org_router)

# Phase E9: Register audit and metering routers
v1.include_router(audit_router)
v1.include_router(metering_router)

# V2 Phase 1: Company
v1.include_router(company_router)

# V2.6: CSV Import
v1.include_router(import_router)

# V3.0: Reorder Recommendations
app.include_router(reorder_router)

app.include_router(v1)

# ---------------------------------------------------------------------------
# Legacy redirects — E9 Q4: Option C (add auth, keep backward compatibility)
# These proxy to v1 endpoints with full auth enforcement.
# ---------------------------------------------------------------------------
legacy = APIRouter(tags=["Legacy (deprecated)"], deprecated=True)


@legacy.post(
    "/simulate",
    response_model=schemas.SimulationCreateResponse,
    dependencies=[Depends(rate_limit("write"))],
)
def legacy_simulate(
    payload: schemas.SimulationInput,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return simulate(payload, auth=auth, db=db)


@legacy.get(
    "/simulate/{simulation_id}", response_model=schemas.SimulationDetailResponse
)
def legacy_get_simulation(
    simulation_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_simulation(simulation_id, auth=auth, db=db)


@legacy.get(
    "/simulate/{simulation_id}/scenarios", response_model=schemas.ScenarioResponse
)
def legacy_get_scenarios(
    simulation_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_scenarios(simulation_id, auth=auth, db=db)


@legacy.get("/simulations", response_model=list[schemas.SimulationSummary])
def legacy_list_simulations(
    limit: int = 20,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_simulations(limit, auth=auth, db=db)


app.include_router(legacy)
