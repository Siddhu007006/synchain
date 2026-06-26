# SynChain — Project Guide

> **One document to understand the entire project. Zero prior knowledge required.**

---

## 1. What Are We Building?

**SynChain** is a **supply chain decision intelligence platform**. It simulates supply chain operations, creates digital replicas of real supply chains, forecasts future demand, detects risks through signals, and will eventually integrate real-world external data (news, weather, commodities, economics).

### The Problem It Solves

A supply chain manager asks: *"I have 5000 units of Widget-A in stock, demand is 8000, my supplier is delayed 3 days, and it's festival season — what should I do?"*

SynChain answers with:
- **Demand forecast** (what demand will look like in 1, 3, 5 planning horizons)
- **Risk assessment** (supply risk level, operational risks)
- **Inventory strategy** (how much to order, when)
- **Warehouse selection** (which warehouse to use)
- **Logistics routing** (optimal delivery route)
- **Confidence score** (how trustworthy is this recommendation)
- **Natural language explanation** (why this recommendation was made)

### The Vision (Complete System)

```
Real World Data ──→ Digital Twin ──→ Signals ──→ Forecasts ──→ Decisions
   (news, weather,    (virtual copy     (risk       (demand +     (what to
    commodities,       of your supply    detection)   confidence)   do next)
    economics)         chain state)
```

---

## 2. How Is It Built? (Architecture)

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API** | FastAPI (Python) | REST API, async support |
| **Database** | SQLite + SQLAlchemy 2.0 | Local dev DB, ORM |
| **Migrations** | Alembic | Schema version control |
| **Testing** | pytest | Unit + integration tests |
| **Frontend** | Next.js (React) | Web dashboard (separate) |

### Backend Directory Structure

```
backend/
├── main.py                    # FastAPI app, all API routes
├── database.py                # SQLAlchemy engine + session factory
├── config.py                  # Pydantic settings (reads .env)
├── models.py                  # Core models: Simulation, Result
├── schemas.py                 # Pydantic request/response models
├── services.py                # Business logic helpers
├── exceptions.py              # Structured error types
│
├── agents/                    # Multi-agent decision system
│   ├── base_agent.py          # Agent ABC
│   ├── demand_agent.py        # Demand forecasting agent
│   ├── inventory_agent.py     # Inventory optimization agent
│   ├── logistics_agent.py     # Route/warehouse selection agent
│   ├── risk_agent.py          # Risk assessment agent
│   ├── decision_agent.py      # Aggregator (combines all agents)
│   ├── explanation_agent.py   # Generates human-readable explanations
│   └── scenario_agent.py      # What-if scenario comparison
│
├── digital_twin/              # Phase E1: Virtual supply chain replica
│   ├── models.py              # DigitalTwin, ProductState, SupplierState, etc.
│   ├── manager.py             # TwinManager (CRUD + state updates)
│   ├── math_utils.py          # EWMA and statistical functions
│   └── schemas.py             # Twin API request/response models
│
├── forecasting/               # Phase E2: Demand forecasting engine
│   ├── engine.py              # ForecastEngine + all computation functions
│   ├── models.py              # ForecastRecord (persisted forecasts)
│   └── schemas.py             # Forecast API response models
│
├── signals/                   # Phase E3+E5+E6: Signal intelligence
│   ├── detectors.py           # 4 internal detectors + detector registry
│   ├── external_detectors.py  # 4 external detectors (E5)
│   ├── compound.py            # 5 compound signal rules + CompoundDetector (E6)
│   ├── providers.py           # DataProvider ABC + synthetic providers (E5)
│   ├── external_cache.py      # ExternalDataCache model + CacheManager (E5)
│   ├── scheduler.py           # Background refresh scheduler (E5)
│   ├── engine.py              # SignalEngine (orchestrates all detectors + compounds)
│   └── schemas.py             # Signal API response models (external + compound fields)
│
├── auth/                      # E8: Multi-tenant auth platform
│   ├── models.py              # User, Organization, Membership, APIKey
│   ├── security.py            # Bcrypt, JWT, API key hashing
│   ├── dependencies.py        # AuthContext, get_current_user, require_role
│   ├── router.py              # Auth endpoints (register/login/refresh/me/keys)
│   ├── org_router.py          # Org CRUD + membership management
│   ├── schemas.py             # Auth request/response models
│   └── org_schemas.py         # Org request/response models
│
├── company/                   # V2: Company management layer
│   ├── models.py              # Company entity (V2.1)
│   ├── product_models.py      # Product model (V2.3)
│   ├── supplier_warehouse_models.py  # Supplier + Warehouse models (V2.5)
│   ├── router.py              # All company/product/supplier/warehouse endpoints
│   ├── schemas.py             # Company schemas
│   ├── product_schemas.py     # Product schemas (with V2.4 prefill contract)
│   └── supplier_warehouse_schemas.py  # Supplier + Warehouse schemas
│
├── tests/                     # 400+ passing tests
│   ├── conftest.py            # DB fixtures (in-memory SQLite)
│   ├── test_agents.py         # Agent unit tests
│   ├── test_digital_twin.py   # Twin CRUD + state tests
│   ├── test_forecasting.py    # Forecast computation tests
│   ├── test_signals.py        # Signal detector + engine tests
│   ├── test_signal_forecast.py# E4: Signal-driven forecast tests
│   ├── test_signal_integration.py # Signal pipeline integration
│   ├── test_compound_signals.py   # E6: Compound signal tests (61 tests)
│   ├── test_external_signals.py   # E5: External provider + detector tests
│   ├── test_real_providers.py     # E7: Real API provider tests
│   ├── test_auth.py               # E8: Auth endpoint tests (17 tests)
│   ├── test_orgs.py               # E8: Organization tests (14 tests)
│   ├── test_data_isolation.py     # E8: Cross-org isolation tests (10 tests)
│   ├── test_e9_production.py      # E9: Production hardening tests
│   ├── test_pipeline.py       # End-to-end pipeline tests
│   └── test_schemas.py        # Schema validation tests
│
├── audits/                    # Phase completion verification scripts
│   ├── e3_audit.py            # E3 completion: 61/61 PASS
│   ├── e4_audit.py            # E4 completion: 59/59 PASS
│   ├── e5_audit.py            # E5 completion: 94/94 PASS
│   ├── e6_audit.py            # E6 completion: 94/94 PASS
│   └── e7_audit.py            # E7 completion audit
│
├── alembic/                   # Database migrations
├── API_REFERENCE.md           # Complete API documentation
└── requirements.txt           # Python dependencies
```

### Key Design Principles

1. **Demand ≠ Supply** — Demand forecast is pure (`avg_demand × trend × season`). Supply risk is a separate field. They never contaminate each other.

2. **Signals are observers** — Signal detectors read state but never write to it. They can fail without breaking simulations.

3. **Confidence absorbs all uncertainty** — Simulation count, horizon distance, trend stability, supplier reliability, AND active signals all feed into one confidence score.

4. **Everything is explainable** — Every forecast includes a natural-language explanation showing exactly how the number was computed.

5. **Backward compatibility** — Each phase preserves all previous API behavior. No breaking changes.

---

## 3. What Has Been Built (Phase History)

### Foundation Phases (Pre-E)

| Phase | What | Status |
|-------|------|:------:|
| **Phase A** | Core simulation engine. Input params → multi-agent processing → decision output. | ✅ Done |
| **Phase B** | Agent enhancement. 6 specialized agents (demand, inventory, logistics, risk, decision, explanation). | ✅ Done |
| **Phase C** | Scenario analysis. What-if comparison across parameter variations. | ✅ Done |
| **Phase D** | Frontend. Next.js dashboard with simulation form and results display. | ✅ Done |

### Evolution Phases (E-series)

| Phase | Name | What It Does | Status |
|-------|------|-------------|:------:|
| **E1** | Digital Twin | Virtual replica of a supply chain. Tracks product demand, supplier reliability, warehouse utilization across simulations. State updates via EWMA. | ✅ Done |
| **E2** | Forecasting | Multi-horizon demand forecasting engine. Computes `demand × trend × season`, with confidence scoring. Persists forecast records. | ✅ Done |
| **E3** | Signal Intelligence | 4 internal detectors (DemandSpike, SupplierDegradation, WarehouseOverload, TrendShift). SignalEngine orchestrates detection. Recency-weighted health score. | ✅ Done |
| **E4** | Signal-Driven Forecasting | Signals actively influence forecasts. Severity-proportional confidence penalties. Risk elevation. Explanation audit trail. | ✅ Done |
| **E5** | External Intelligence | 4 external signal sources (News, Weather, Commodity, Economic). Configurable providers (synthetic default). Background refresh + cache. | ✅ Done |
| **E6** | Compound Signals | 5 compound rules detecting multi-signal patterns (SupplyShock, FulfillmentCrisis, MarketDisruption, PerfectStorm, CostSqueeze). Additive penalty stacking. Phase 2 evaluation after atomics. | ✅ Done |
| **E7** | Real API Providers | Swap synthetic providers for real APIs (NewsAPI, OpenWeatherMap, Alpha Vantage, FRED). Auto mode: uses real if API key present, synthetic fallback otherwise. Rate-limited HTTP client. | ✅ Done |
| **E8** | Multi-Tenant Auth | JWT authentication, bcrypt password hashing, API key system, organization CRUD, role-based access (viewer/member/admin/owner), `org_id` data isolation on all business entities. 41 tests passing. | ✅ Done |
| **E9** | Production Hardening | Rate limiting (sliding window per tier), structured logging (JSON/text), database pool config, audit log retention, secure cookie support. | ✅ Done |

### V2 Build Series (Company Management Layer)

| Build | Name | What It Does | Status |
|-------|------|-------------|:------:|
| **V2.1** | Company CRUD | Root business entity. 5 REST endpoints (create, list, get, update, delete). Org-scoped via `org_id`. | ✅ Done |
| **V2.2** | Company ↔ Twin | Added `company_id` to DigitalTwin. List/create twins per company. Twin ownership validation. | ✅ Done |
| **V2.3** | Product Catalog | Product model with `current_stock`, `avg_monthly_demand`. CRUD endpoints per company. | ✅ Done |
| **V2.4** | Simulation Prefill | Form: Company selector → Product selector → auto-fills stock + demand. `product_id` + `company_id` FK on simulations for traceability. Results page shows company/product context banner. | ✅ Done |
| **V2.5** | Supplier & Warehouse | Supplier model (`lead_time_days` → `supplier_delay`, `supply_status`). Warehouse model (`warehouse_id` → `warehouse`). CRUD endpoints. Form: auto-fill delay, supply status, warehouse from selected entities. | ✅ Done |

---

## 4. How Each Phase Connects (Data Flow)

```
User Input (product, stock, demand, warehouse, supplier_delay, season, trend)
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  POST /api/v1/simulate                              │
│                                                     │
│  1. Save Simulation record                          │
│  2. Run 6 agents (demand→inventory→logistics→risk   │
│     →decision→explanation)                          │
│  3. Save Result record                              │
│  4. If twin_id provided:                            │
│     a. TwinManager.update_state() ← EWMA updates   │
│     b. SignalEngine.evaluate() ← detect signals     │
│  5. Return decision + explanation                   │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  GET /api/v1/twins/{id}/forecast?product=X          │
│                                                     │
│  1. Read twin's product state (avg_demand, trend,   │
│     season, supplier_reliability)                   │
│  2. Fetch active signals from SignalEngine          │  ← E3+E4
│  3. For each horizon (1, 3, 5):                     │
│     a. Compute: demand = avg × trend_factor × season│
│     b. Compute: base_confidence (E2 formula)        │
│     c. Apply signal penalties (E4)                  │
│     d. Apply risk elevation (E4)                    │
│     e. Build explanation + audit trail              │
│  4. Persist ForecastRecord                          │
│  5. Return forecasts + active_signals               │
└─────────────────────────────────────────────────────┘
```

---

## 5. Database Tables

| Table | Phase | Purpose |
|-------|:-----:|---------|
| `simulations` | A | Raw simulation inputs |
| `results` | A | Computed simulation outputs (decision, risk, strategy) |
| `digital_twins` | E1 | Twin identity (name, metadata) |
| `product_states` | E1 | Per-product demand tracking (avg, trend, EWMA) |
| `supplier_states` | E1 | Supplier reliability tracking |
| `warehouse_states` | E1 | Warehouse utilization tracking |
| `market_states` | E1 | Market condition tracking (season, trend) |
| `twin_state_history` | E1 | Audit log of all state changes |
| `forecast_records` | E2 | Persisted forecast outputs |
| `signal_event` | E3 | Detected signal records |
| `external_data_cache` | E5 | Cached external provider data (with schema_version) |
| `users` | E8 | User accounts (email, hashed password, role) |
| `organizations` | E8 | Multi-tenant organizations (name, slug) |
| `memberships` | E8 | User ↔ Org relationship with role |
| `api_keys` | E8 | API key hashes with prefix and expiry |
| `companies` | V2.1 | Company entities (name, industry, country, org_id) |
| `products` | V2.3 | Products per company (name, category, stock, demand) |
| `suppliers` | V2.5 | Suppliers per company (lead_time, supply_status, reliability) |
| `warehouses` | V2.5 | Warehouses per company (warehouse_id, location, capacity) |

---

## 6. Key Formulas (The Math Behind Decisions)

### Demand Forecast
```
forecast_demand = avg_demand × trend_factor × season_factor
```
- `trend_factor`: Rising +5%/horizon, Stable 0%, Falling -3%/horizon
- `season_factor`: Festival ×1.15, Normal ×1.0, Off-season ×0.85
- `avg_demand`: EWMA (alpha=0.3) across simulation history

### Confidence Score
```
base       = min(sim_count / 10, 1.0)        # Data volume
horizon    = -0.10 × h                        # Distance penalty
trend      = +0.05 if Stable, -0.05 otherwise # Stability bonus
supplier   = +0.05/0.0/-0.10                  # Supply certainty
base_confidence = clamp(sum, 0.1, 1.0)

signal_penalty = Σ(weight × severity)          # E4: signal impact
final_confidence = clamp(base - penalty, 0.1, 1.0)
```

### Signal Confidence Weights
| Signal | Weight | Phase |
|--------|:------:|:-----:|
| DemandSpike | 0.10 | E3 |
| SupplierDegradation | 0.15 | E3 |
| WarehouseOverload | 0.08 | E3 |
| TrendShift | 0.00 | E3 |
| NewsDisruption | 0.06 | E5 |
| WeatherAlert | 0.10 | E5 |
| CommodityShock | 0.08 | E5 |
| EconomicShift | 0.05 | E5 |
| SupplyShock | 0.12 | E6 |
| FulfillmentCrisis | 0.10 | E6 |
| MarketDisruption | 0.08 | E6 |
| PerfectStorm | 0.15 | E6 |
| CostSqueeze | 0.06 | E6 |

### Health Score (per Twin)
```
health = 1.0 - weighted_avg_severity(last 10 signals)
weight = position-based (newest=10, oldest=1)
```

---

## 7. API Endpoints (Quick Reference)

### Core
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/simulate` | Run a simulation |
| `GET` | `/api/v1/simulations` | List simulation history |
| `GET` | `/api/v1/simulate/{id}` | Get simulation detail |
| `GET` | `/api/v1/simulate/{id}/scenarios` | Get scenario analysis |
| `GET` | `/health` | Health check |

### Digital Twin (E1)
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/twins` | Create a twin |
| `GET` | `/api/v1/twins` | List all twins |
| `GET` | `/api/v1/twins/{id}` | Get twin with full state |
| `DELETE` | `/api/v1/twins/{id}` | Delete a twin |
| `GET` | `/api/v1/twins/{id}/history` | State change history |

### Forecasting (E2)
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/twins/{id}/forecast` | Generate demand forecast |
| `GET` | `/api/v1/twins/{id}/forecasts` | List forecast records |
| `GET` | `/api/v1/twins/{id}/forecast/summary` | Forecast summary per product |

### Signals (E3)
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/twins/{id}/signals` | List detected signals |
| `GET` | `/api/v1/twins/{id}/signals/summary` | Signal summary + health score |

### External Intelligence (E5/E7)
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/external/status` | Cache status for all providers |
| `POST` | `/api/v1/external/refresh` | Manually trigger data refresh |
| `GET` | `/api/v1/external/config` | Active provider info per category |
| `GET` | `/api/v1/compound-rules` | List compound signal rule definitions |

### Auth (E8)
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/auth/register` | Create user + auto-create org |
| `POST` | `/api/v1/auth/login` | Login → access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Get current user info |
| `POST` | `/api/v1/auth/keys` | Create API key |
| `GET` | `/api/v1/auth/keys` | List API keys |
| `DELETE` | `/api/v1/auth/keys/{id}` | Revoke API key |
| `POST` | `/api/v1/orgs` | Create organization |
| `GET` | `/api/v1/orgs` | List user's organizations |
| `POST` | `/api/v1/orgs/{id}/invite` | Invite user to org |
| `PATCH` | `/api/v1/orgs/{id}/members/{uid}` | Update member role |
| `DELETE` | `/api/v1/orgs/{id}/members/{uid}` | Remove member |

---

## 8. How to Run

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set up environment
# .env contains DATABASE_URL=sqlite:///./supply_chain.db

# Run migrations (or let create_all handle it for dev)
alembic upgrade head

# Start the server
uvicorn main:app --reload --port 8000

# Run tests
pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

---

## 9. Current State: E9 Complete + Frontend Intelligence

### Phase Summary

| Phase | Key Deliverables | Tests |
|-------|-----------------|:-----:|
| **E6** | 5 compound rules, CompoundDetector, additive penalty stacking | 61 |
| **E7** | 4 real API providers (NewsAPI, OWM, Alpha Vantage, FRED), auto/synthetic/real modes, rate-limited HTTP client | — |
| **E8** | JWT auth, bcrypt, API keys, org CRUD, RBAC, `org_id` data isolation, debug fallback | 41 |
| **E9** | Rate limiting (4 tiers), structured logging, DB pool config, audit retention, secure cookies | — |
| **F1-F6** | Frontend API integration, agent breakdown, scenario panel, 4 intelligence dashboards, twin form integration | — |

### Key Decisions Made
- **E7 Auto Mode**: Real provider if API key present, synthetic fallback otherwise (no crash on missing key)
- **E8 Debug Fallback**: Auto-creates `dev@synchain.local` when `DEBUG=true` (bypasses auth for local dev)
- **E8 Data Isolation**: `org_id` on simulations, twins, forecasts. Cross-org access returns 404 (prevents enumeration)
- **E9 Rate Limiting**: Sliding window — auth: 10/min, write: 30/min, read: 120/min, admin: 20/min
- **F5 Twin ID**: Form sends `twin_id` only when toggle is enabled. Scenario sandbox intentionally omits `twin_id` to prevent twin state corruption
- **Additive Penalty Stacking**: Compound penalties stack with atomic trigger penalties
- **PerfectStorm = 3-trigger**: Requires WeatherAlert + SupplierDeg + DemandSpike at severity ≥ 0.4

---

## 10. What's Next

### Remaining Work

| Priority | Item | Effort |
|----------|------|--------|
| 🔴 P0 | Replace placeholder API keys with `""` or real keys | 15 min |
| 🔴 P0 | Set `DEBUG=false` for demo | 1 min |
| 🟡 P1 | Demo seed script | 30 min |
| 🟡 P1 | Docker + docker-compose | 2-4 hrs |
| 🟢 P2 | Auto-trigger forecast after twin-linked simulation | 1-2 hrs |
| 🟢 P2 | Signal list pagination | 1 hr |

### Technical Debt Items

| ID | Item | Decision |
|----|------|----------|
| **TD4** | Data Retention & Archival | Deferred. Current data volume is negligible. |
| **TD5** | SignalEvents not org-scoped | By design (system-global). Advisory. |
| **TD6** | API key scope enforcement | Scopes stored but not enforced. Planned for future. |

### Architectural Constraints (Apply to ALL Future Work)

1. **No demand contamination** — Supply signals never inflate the demand number
2. **Signal retention = all time** — No cleanup, no deduplication, no retention limits
3. **Health score = last 10 signals, recency-weighted** — Not all-time averaging
4. **One signal per simulation occurrence** — No deduplication across simulations
5. **Deterministic & explainable** — Every output must be reproducible from its inputs
6. **Non-blocking signals** — Detector failures never crash simulations
7. **Compounds are declarative** — Rules are code-defined, not user-editable (E6)
8. **Org isolation mandatory** — All business entities require `org_id` filter
9. **Scenario sandbox isolation** — What-if runs never send `twin_id` to prevent twin corruption

---

## 11. Test Suite Summary

| Test File | Tests | Phase | What It Covers |
|-----------|:-----:|:-----:|---------------|
| `test_agents.py` | 19 | A-B | Agent computation logic |
| `test_digital_twin.py` | 53 | E1 | Twin CRUD, state updates, EWMA, history |
| `test_forecasting.py` | 47 | E2 | Forecast computation, API, backward compat |
| `test_signals.py` | 38 | E3 | Detectors, engine, health score, signal API |
| `test_signal_forecast.py` | 38 | E4 | Signal penalties, risk elevation, explanations |
| `test_signal_integration.py` | 6 | E4 | Signal pipeline end-to-end |
| `test_external_signals.py` | 52 | E5 | Providers, cache, detectors, scheduler |
| `test_compound_signals.py` | 61 | E6 | Compound rules, severity fns, detector, penalties |
| `test_real_providers.py` | — | E7 | Real API provider logic |
| `test_auth.py` | 17 | E8 | Auth endpoints, JWT, API keys |
| `test_orgs.py` | 14 | E8 | Organization CRUD, membership |
| `test_data_isolation.py` | 10 | E8 | Cross-org access prevention |
| `test_e9_production.py` | — | E9 | Rate limiting, logging, hardening |
| `test_pipeline.py` | 14 | A | Full simulation pipeline |
| `test_schemas.py` | 14 | A | Input validation |
| **Total** | **400+** | **A-E9** | **All phases covered** |

---

## 12. Glossary

| Term | Meaning |
|------|---------|
| **Digital Twin** | Virtual replica of a supply chain that accumulates state across simulations |
| **EWMA** | Exponentially Weighted Moving Average (alpha=0.3) — how avg_demand is computed |
| **Horizon** | Abstract planning period (1=short-term, 5=long-term). Not calendar units. |
| **Signal** | A discrete, typed observation about supply chain conditions (severity 0.0–1.0) |
| **Detector** | A class that reads twin state and emits 0+ signals |
| **Provider** | A class that fetches external data (synthetic or real API) |
| **Confidence** | Score (0.1–1.0) expressing how reliable a forecast is |
| **Supply Risk** | Categorical assessment: Low, Medium, or High |
| **Risk Elevation** | E4 mechanism: active signals can push supply risk up one tier |
| **Signal Penalty** | E4 mechanism: weight × severity reduces confidence score |
| **ExternalDataCache** | DB table caching external provider responses with TTL |
| **schema_version** | Version field on cache entries for future payload evolution |
| **Compound Signal** | E6: Pattern detected when multiple atomic signals co-occur |
| **CompoundRule** | E6: Declarative definition of trigger combination + severity function |
| **Additive Stacking** | E6: Compound penalties add to atomic penalties (intentional design) |
