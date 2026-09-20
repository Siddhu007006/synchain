# SynChain — Architecture

> Multi-agent supply chain intelligence platform

---

## System Overview

SynChain is a **simulation-first** supply chain decision system. It does **not** connect to live warehouse APIs, ERP systems, or real-time data feeds. Instead, it demonstrates how a multi-agent AI pipeline can evaluate supply chain conditions and produce explainable decisions.

```
┌──────────────┐     POST /api/v1/simulate     ┌──────────────────────┐
│   Frontend   │ ──────────────────────────────→│     FastAPI Server   │
│  (Next.js)   │←──────────────────────────────│                      │
└──────────────┘     SimulationResult + agents  │  ┌────────────────┐ │
                                                 │  │ DecisionAgent  │ │
                                                 │  │  ┌──────────┐ │ │
                                                 │  │  │  Demand   │ │ │
                                                 │  │  │ Inventory │ │ │
                                                 │  │  │ Logistics │ │ │
                                                 │  │  │   Risk    │ │ │
                                                 │  │  │Explanation│ │ │
                                                 │  │  └──────────┘ │ │
                                                 │  └────────────────┘ │
                                                 │  ┌────────────────┐ │
                                                 │  │ ScenarioAgent  │ │
                                                 │  │ (orchestrator) │ │
                                                 │  └────────────────┘ │
                                                 │  ┌────────────────┐ │
                                                 │  │   SQLite DB    │ │
                                                 │  └────────────────┘ │
                                                 └──────────────────────┘
```

---

## Warehouse Network: W1 / W2 / W3

### What they are

W1, W2, and W3 are **hardcoded simulation warehouses**. They exist as static configuration inside [logistics_agent.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/agents/logistics_agent.py#L55-L66) to model a small, representative warehouse network for the LogisticsAgent's cost-based optimization algorithm.

They are **not**:
- Real warehouses connected to an inventory system
- Placeholders for a database-driven warehouse table
- User-configurable at runtime

### Why they exist

The purpose of the warehouse network is to give the LogisticsAgent a **non-trivial optimization problem**. With only one warehouse, the agent would have nothing to decide. With three warehouses that differ in capacity and cost, the agent must balance tradeoffs — which is the core demonstration of the system.

Each warehouse represents a distinct fulfillment strategy:

| ID | Route | Capacity | Cost Factor | Strategy | When Selected |
|----|-------|----------|-------------|----------|---------------|
| **W1** | R1 | 10,000 | 1.0× | Standard | Balanced demand, cost-sensitive |
| **W2** | R4 | 15,000 | 1.2× | Premium | High demand that exceeds W1/W3 capacity |
| **W3** | R7 | 8,000 | 0.9× | Budget | Low demand where cost optimization wins |

### How they work

The LogisticsAgent scores each warehouse using:

```
score = (capacity_fit × 0.6) + (cost_score × 0.4) + home_bonus
```

- **Capacity fit** (60% weight): Can this warehouse hold the predicted demand?
- **Cost score** (40% weight): Lower `cost_factor` → higher score
- **Home bonus** (+0.15): If the user's current warehouse already has sufficient stock, prefer it to avoid unnecessary transfers

The agent selects the warehouse with the highest combined score.

### Routes

Routes (R1, R4, R7) are **static labels** paired 1:1 with warehouses. They represent logistics corridors but are not independently configurable. In a production system, routes would be a separate entity with distance, time, and cost attributes.

### Future evolution path

If the system were to evolve beyond simulation:

1. **Phase 1 (current):** Hardcoded `WAREHOUSES` dict in Python
2. **Phase 2 (database-driven):** Move warehouse data to a `warehouses` table; `LogisticsAgent` reads from DB at runtime
3. **Phase 3 (API-driven):** Warehouse CRUD endpoints; users manage their own warehouse networks
4. **Phase 4 (live integration):** Connect to WMS/ERP APIs for real-time capacity and stock data

The current architecture intentionally stays at Phase 1. The agent logic (scoring algorithm, confidence formula) is designed to work regardless of where the warehouse data comes from — only the data source changes.

---

## Agent Architecture

### Agent types

SynChain has two kinds of agents:

| Type | Base class | Returns | Example |
|------|-----------|---------|---------|
| **Step agent** | `BaseAgent` (ABC) | `AgentStepResult` | DemandAgent, InventoryAgent, LogisticsAgent, RiskAgent |
| **Orchestrator** | None (plain class) | Varies | DecisionAgent (returns `SimulationResult`), ScenarioAgent (returns `list[dict]`), ExplanationAgent (returns `str`) |

Step agents are the specialist decision-makers. They consume specific inputs, produce typed outputs, and report a confidence score with a documented formula. Every step agent follows the contract:

```python
class BaseAgent(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, **kwargs) -> AgentStepResult: ...
```

Orchestrators coordinate step agents. They don't produce `AgentStepResult` because they aren't making a single decision — they're combining multiple decisions.

### Pipeline flow

```
SimulationInput
    │
    ├─→ DemandAgent.run(demand, market_trend, season)
    │       → predicted_demand, confidence
    │
    ├─→ InventoryAgent.run(predicted_demand, stock, supply_status)
    │       → recommended_inventory, confidence
    │
    ├─→ LogisticsAgent.run(warehouse, stock, predicted_demand)
    │       → selected_warehouse, route, scores, confidence
    │
    ├─→ RiskAgent.run(supplier_delay, supply_status, market_trend)
    │       → risk_level, risk_score, confidence
    │
    ├─→ WeightedConfidence(all 4 agent confidences)
    │       → overall_confidence
    │
    ├─→ BuildStrategy(risk, warehouse, inventory, context)
    │       → strategy string
    │
    └─→ ExplanationAgent.run(agent_steps, confidence, strategy)
            → narrative paragraph
```

### Confidence architecture

Each step agent computes confidence independently using a documented formula (see docstrings in each agent file). The DecisionAgent combines them using business-impact weights:

| Agent | Weight | Rationale |
|-------|--------|-----------|
| RiskAgent | 0.40 | Wrong risk assessment → most severe consequences |
| DemandAgent | 0.25 | Demand forecast drives inventory decisions |
| InventoryAgent | 0.20 | Inventory follows from demand |
| LogisticsAgent | 0.15 | Warehouse selection is less nuanced |

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 16 + TypeScript | Form, results dashboard, charts |
| UI components | shadcn/ui + Radix | Accessible component library |
| Charts | Recharts | Bar chart, radar chart |
| Backend | FastAPI + Python 3.14 | API server |
| Database | SQLite + SQLAlchemy 2.0 | Simulation persistence |
| Migrations | Alembic | Schema versioning |
| Config | pydantic-settings | Environment-based config |
| Validation | Pydantic v2 + Literal types | Request/response schemas |

---

## Digital Twin Architecture (Phase E)

### What It Is

The SynChain Digital Twin is a **persistent, structured representation of a supply chain's current state** that evolves through simulations. Unlike one-shot simulations (which are stateless), the twin:

1. **Persists** — state survives across simulations
2. **Evolves** — each simulation updates the twin's state via EWMA smoothing
3. **Informs** — agents read twin state for historical context
4. **Tracks history** — every state change is logged in `twin_state_history`

> [!WARNING]
> **Limitation:** The Digital Twin currently evolves from simulation outcomes and user-generated simulations, not from real-world operational telemetry. It is a simulation-driven state model, not a live operational mirror. This is an intentional design constraint — the system demonstrates the twin pattern without requiring external data feeds.

### State Domains

| Domain | Scope | Key Fields |
|--------|-------|------------|
| **ProductState** | Per-product per-twin | `avg_demand` (EWMA), `demand_trend`, `simulation_count` |
| **WarehouseState** | Per-warehouse per-twin | `utilization_pct`, `selection_rate`, `avg_risk_score` |
| **SupplierState** | Aggregate per-twin | `avg_delay` (EWMA), `reliability_score` |
| **MarketState** | Global per-twin | `trend_mode`, `avg_confidence` (EWMA) |

> [!NOTE]
> **SupplierState** is a V1 aggregate model. It tracks global supplier metrics across all simulations in a twin. In future phases, this will evolve into per-supplier state models with individual supplier IDs, performance histories, and relationship graphs.

### EWMA Smoothing

All moving averages use Exponentially Weighted Moving Average with `α = 0.3`:

```
new_avg = 0.3 × current_value + 0.7 × old_avg
```

This gives ~70% weight to historical data, making the twin resistant to outlier simulations while still adapting to genuine trends.

### Twin State History

Every state mutation is logged to `twin_state_history` with `entity_type`, `entity_id`, `field_name`, `old_value`, and `new_value`. This enables:
- Demand evolution charts
- Risk trend analysis
- Warehouse utilization timelines
- Debugging unexpected state changes

### Signal Intelligence Layer

The Signal Intelligence Layer is a pluggable framework for feeding internal and external context into twin state. Phase E3 introduced internal detectors, E5 added synthetic external providers, E6 added compound signal detection, and E7 introduced real API integrations (NewsAPI, OpenWeatherMap, Alpha Vantage, FRED) with auto-mode fallback. The system uses `EXTERNAL_PROVIDER_MODE=auto` to select real providers when API keys are present, falling back to synthetic otherwise.

Signal events are persisted in the `signal_events` table for historical analysis and explainability.

### Twin ↔ Simulation Relationship

```
SimulationInput.twin_id (optional)
    │
    ▼
┌──────────────┐     ┌─────────────────┐
│ POST /simulate│────→│ Agent Pipeline   │ ← reads twin state (if twin_id provided)
└──────────────┘     └────────┬────────┘
                              │
                              ▼
                     ┌────────────────┐
                     │ SimulationResult│
                     └────────┬───────┘
                              │
                              ▼
                     ┌────────────────┐
                     │ Twin State     │ ← EWMA update
                     │ Update         │ ← History log
                     └────────────────┘
```

If `twin_id` is omitted, the pipeline runs in L2 mode (no twin context) — full backward compatibility.

---

## Directory Structure

```
Synchain/
├── backend/
│   ├── agents/
│   │   ├── base_agent.py          # ABC + AgentStepResult
│   │   ├── demand_agent.py        # Forecasting
│   │   ├── inventory_agent.py     # Safety stock
│   │   ├── logistics_agent.py     # Warehouse optimization (W1/W2/W3)
│   │   ├── risk_agent.py          # Multi-factor risk scoring
│   │   ├── decision_agent.py      # Pipeline orchestrator
│   │   ├── explanation_agent.py   # Narrative synthesis
│   │   └── scenario_agent.py      # What-if disruptions
│   ├── digital_twin/              # Phase E — Digital Twin state layer
│   │   ├── __init__.py
│   │   ├── models.py              # SQLAlchemy models (6 tables)
│   │   ├── schemas.py             # Pydantic API schemas
│   │   ├── manager.py             # TwinManager service (CRUD + EWMA)
│   │   └── math_utils.py          # EWMA, trend detection
│   ├── signals/                   # Phase E3+E5+E6+E7 — Signal Intelligence
│   │   ├── __init__.py
│   │   ├── detectors.py           # Internal detectors + detector registry
│   │   ├── external_detectors.py  # External signal detectors
│   │   ├── compound.py            # 5 compound signal rules + CompoundDetector
│   │   ├── providers.py           # DataProvider ABC + synthetic providers
│   │   ├── real_providers.py      # Real API providers (E7)
│   │   ├── external_cache.py      # ExternalDataCache model + cache manager
│   │   ├── scheduler.py           # Background provider refresh
│   │   ├── schemas.py             # SignalData schema
│   │   └── engine.py              # Signal orchestration and health scoring
│   ├── auth/                      # Phase E8 — Multi-tenant auth
│   │   ├── models.py              # User, Organization, Membership, APIKey
│   │   ├── security.py            # Bcrypt, JWT, API key hashing
│   │   ├── dependencies.py        # AuthContext, get_current_user, require_role
│   │   ├── router.py              # Auth endpoints
│   │   ├── org_router.py          # Org CRUD + membership
│   │   ├── schemas.py             # Auth schemas
│   │   └── org_schemas.py         # Org schemas
│   ├── company/                   # V2: Company management layer
│   │   ├── models.py              # Company entity (V2.1)
│   │   ├── product_models.py      # Product model (V2.3)
│   │   ├── supplier_warehouse_models.py  # Supplier + Warehouse (V2.5)
│   │   ├── router.py              # 23 CRUD endpoints
│   │   ├── schemas.py             # Company schemas
│   │   ├── product_schemas.py     # Product schemas (V2.4 prefill)
│   │   └── supplier_warehouse_schemas.py  # Supplier + Warehouse schemas
│   ├── tests/
│   │   ├── test_agents.py         # Agent unit tests
│   │   ├── test_schemas.py        # Validation tests
│   │   ├── test_pipeline.py       # Integration tests
│   │   ├── test_digital_twin.py   # Twin state tests (E1)
│   │   ├── test_forecasting.py    # Forecast computation tests (E2)
│   │   ├── test_signals.py        # Internal signal tests (E3)
│   │   ├── test_signal_forecast.py# Signal-driven forecast tests (E4)
│   │   ├── test_signal_integration.py # Signal pipeline E2E (E4)
│   │   ├── test_external_signals.py   # External provider tests (E5)
│   │   ├── test_compound_signals.py   # Compound signal tests (E6)
│   │   ├── test_real_providers.py     # Real API tests (E7)
│   │   ├── test_auth.py               # Auth endpoint tests (E8)
│   │   ├── test_orgs.py               # Org CRUD tests (E8)
│   │   ├── test_data_isolation.py     # Cross-org isolation (E8)
│   │   └── test_e9_production.py      # Production hardening (E9)
│   ├── audits/                    # Phase completion audit scripts
│   │   ├── e3_audit.py
│   │   ├── e4_audit.py
│   │   ├── e5_audit.py
│   │   ├── e6_audit.py
│   │   └── e7_audit.py
│   ├── alembic/                   # Database migrations
│   ├── main.py                    # FastAPI app + /api/v1/ routes
│   ├── config.py                  # pydantic-settings
│   ├── database.py                # SQLAlchemy engine
│   ├── models.py                  # ORM models (simulations, results)
│   ├── schemas.py                 # Pydantic request/response
│   ├── services.py                # Pipeline entry point
│   ├── exceptions.py              # Structured error hierarchy
│   └── API_REFERENCE.md           # Endpoint documentation
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Landing page
│   │   ├── form/page.tsx          # Simulation input form
│   │   ├── results/page.tsx       # Results + agent breakdown + scenarios
│   │   └── intelligence/
│   │       ├── twins/page.tsx     # Digital Twin dashboard
│   │       ├── forecasts/page.tsx # Forecasting dashboard
│   │       ├── signals/page.tsx   # Signals dashboard
│   │       └── compound/page.tsx  # Compound signals + external status
│   │   └── companies/
│   │       ├── page.tsx           # Company list
│   │       ├── new/page.tsx       # Create company form
│   │       └── [id]/page.tsx      # Company detail (products, suppliers, warehouses, twins)
│   ├── lib/
│   │   ├── api.ts                 # API client (fetch wrapper)
│   │   ├── types.ts               # TypeScript types matching schemas
│   │   └── validations.ts         # Zod form validation
│   └── components/                # UI components
├── docs/                          # PDF documentation
├── e8_audits.md                   # E8 audit report (4 audits: structural, security, isolation, business logic)
├── synchain_technical_audit.md    # Master technical audit (v3)
├── PROJECT_GUIDE.md               # One-document project guide
└── ARCHITECTURE.md                # ← You are here

---

## Auth Architecture (Phase E8)

### Security Model

SynChain implements a multi-tenant auth platform with JWT tokens, bcrypt password hashing, and API key authentication.

```
Request → HTTPBearer / X-API-Key / Debug Fallback
    │
    ▼
┌──────────────────┐
│ get_current_user │  ← dependencies.py
│                  │
│ 1. Extract token/key
│ 2. Verify JWT or hash-match API key
│ 3. Load User + Membership
│ 4. Build AuthContext (user, org, role)
└──────────────────┘
    │
    ▼
┌──────────────────┐
│ require_role()   │  ← Role guard
│ viewer < member < admin < owner
└──────────────────┘
    │
    ▼
┌──────────────────┐
│ Business endpoint │  ← Receives AuthContext
│ filters by org_id │
└──────────────────┘
```

### Data Isolation

All business entities (`simulations`, `digital_twins`, `forecast_records`) have an `org_id` column with a foreign key to `organizations.id`. Every query filters by the authenticated user's organization. Cross-org access returns 404 (not 403) to prevent organization enumeration.

### Debug Mode

When `DEBUG=true`, the auth pipeline auto-creates a `dev@synchain.local` user with a default organization. This allows local development without requiring registration. **Must be disabled in production.**
```
