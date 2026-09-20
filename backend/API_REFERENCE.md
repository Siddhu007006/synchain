# SynChain API Reference (v1)

> Base URL: `http://localhost:8000/api/v1`

---

## Health Check

### `GET /`

Returns API status. Not versioned.

**Response:**
```json
{
  "status": "ok",
  "message": "SynChain Decision API is running",
  "version": "3.1.0"
}
```

### `GET /health`

Lightweight health probe for monitoring.

**Response:**
```json
{
  "status": "ok",
  "version": "3.1.0"
}
```

---

## Simulation

### `POST /api/v1/simulate`

Run a supply chain simulation through the multi-agent pipeline.

**Request Body:**
```json
{
  "product": "Electronics",
  "stock": 5000,
  "warehouse": "W1",
  "demand": 8000,
  "supplier_delay": 4,
  "market_trend": "Positive",
  "supply_status": "Medium",
  "season": "Festival",
  "twin_id": 1
}
```

**Field Constraints:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `product` | string | ✅ | 1–100 characters |
| `stock` | float | ✅ | ≥ 0 |
| `warehouse` | string | ✅ | `"W1"` \| `"W2"` \| `"W3"` |
| `demand` | float | ✅ | ≥ 0 |
| `supplier_delay` | float | ✅ | ≥ 0 |
| `market_trend` | string | ❌ | `"Positive"` \| `"Neutral"` \| `"Negative"` (default: `"Neutral"`) |
| `supply_status` | string | ❌ | `"High"` \| `"Medium"` \| `"Low"` (default: `"Medium"`) |
| `season` | string | ❌ | `"Festival"` \| `"Normal"` \| `"Off-season"` (default: `"Normal"`) |
| `twin_id` | integer | ❌ | Digital Twin ID. If provided, twin state is updated after simulation (EWMA). If omitted, runs in L2 mode. |

**Success Response (200):**
```json
{
  "simulation_id": 1,
  "status": "completed"
}
```

**Error Response (422) — invalid enum value:**
```json
{
  "detail": [
    {
      "type": "literal_error",
      "loc": ["body", "warehouse"],
      "msg": "Input should be 'W1', 'W2' or 'W3'",
      "input": "W4"
    }
  ]
}
```

---

### `GET /api/v1/simulate/{simulation_id}`

Retrieve a completed simulation with full results and agent breakdown.

**Parameters:**

| Parameter | Type | Location |
|-----------|------|----------|
| `simulation_id` | integer | path |

**Success Response (200):**
```json
{
  "simulation_id": 1,
  "input": { "product": "Electronics", "stock": 5000, ... },
  "result": {
    "demand_forecast": 13728.0,
    "recommended_inventory": 15100.8,
    "selected_warehouse": "W2",
    "route": "R4",
    "risk": "Medium",
    "strategy": "Monitor supplier performance...",
    "overall_confidence": 0.80,
    "explanation": "Based on analysis by 4 specialist agents...",
    "agent_breakdown": [
      {
        "agent_name": "DemandAgent",
        "input_summary": { "demand": 8000, "market_trend": "Positive", "season": "Festival" },
        "output_data": { "predicted_demand": 13728.0 },
        "confidence": 1.0,
        "explanation": "Base demand 8,000 × trend factor 1.2 + positive market...",
        "execution_ms": 0.01,
        "status": "success"
      }
    ]
  }
}
```

**Error Response (404):**
```json
{
  "detail": "Simulation 999 not found",
  "error_type": "NOT_FOUND"
}
```

---

### `GET /api/v1/simulate/{simulation_id}/scenarios`

Run 4 what-if disruption scenarios against a stored simulation.

**Scenarios:**

| # | Name | Mutation |
|---|------|----------|
| 1 | Demand Surge | `demand × 1.20` |
| 2 | Supplier Shutdown | `supplier_delay → 10` |
| 3 | Inventory Shortage | `stock × 0.70` |
| 4 | Transport Delay | `supplier_delay × 1.50` |

**Success Response (200):**
```json
{
  "simulation_id": 1,
  "base_result": {
    "demand_forecast": 13728.0,
    "recommended_inventory": 15100.8,
    "selected_warehouse": "W2",
    "route": "R4",
    "risk": "Medium",
    "overall_confidence": 0.80,
    "strategy": "..."
  },
  "scenarios": [
    {
      "scenario_name": "Demand Surge",
      "scenario_description": "Demand increases by 20%...",
      "modified_input": { ... },
      "result": { ... },
      "impact": {
        "demand_change": 2745.6,
        "inventory_change": 3020.16,
        "confidence_change": 0.0,
        "risk_change": "No change (Medium)",
        "recommendation_changed": false,
        "warehouse_changed": false,
        "route_changed": false
      }
    }
  ]
}
```

---

### `GET /api/v1/simulations`

List past simulation summaries (most recent first).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max results to return |

**Success Response (200):**
```json
[
  {
    "simulation_id": 3,
    "product": "Electronics",
    "warehouse": "W1",
    "demand": 8000,
    "risk": "Medium",
    "overall_confidence": 0.80,
    "created_at": "2026-06-04T14:00:00"
  }
]
```

---

## Digital Twin (Phase E)

> **Concept:** A Digital Twin is a persistent, evolving state model of a supply chain.
> It tracks demand trends (EWMA), warehouse utilization, supplier reliability, and market conditions across simulations.
> Every state mutation is logged to `twin_state_history` for audit and analytics.

### `POST /api/v1/twins`

Create a new Digital Twin with pre-initialized state domains (3 warehouses, supplier, market).

**Request Body:**
```json
{
  "name": "My Supply Chain"
}
```

**Success Response (200):**
```json
{
  "id": 1,
  "name": "My Supply Chain",
  "simulation_count": 0,
  "created_at": "2026-06-04T14:00:00",
  "updated_at": "2026-06-04T14:00:00"
}
```

---

### `GET /api/v1/twins`

List all Digital Twins.

**Success Response (200):**
```json
[
  { "id": 1, "name": "My Supply Chain", "simulation_count": 5, ... }
]
```

---

### `GET /api/v1/twins/{twin_id}`

Get full state snapshot for a twin (all 4 state domains).

**Success Response (200):**
```json
{
  "id": 1,
  "name": "My Supply Chain",
  "simulation_count": 5,
  "product_states": [
    {
      "product_name": "Widget-A",
      "latest_stock": 5000,
      "latest_demand": 8000,
      "avg_demand": 7840.0,
      "demand_trend": "Stable",
      "simulation_count": 3
    }
  ],
  "warehouse_states": [
    {
      "warehouse_id": "W1",
      "times_selected": 3,
      "utilization_pct": 0.8,
      "selection_rate": 0.6,
      "avg_delivery_score": 0.0,
      "avg_risk_score": 0.42
    }
  ],
  "supplier_state": {
    "avg_delay": 3.5,
    "max_delay_seen": 7.0,
    "reliability_score": 50.0,
    "supply_status_mode": "Medium"
  },
  "market_state": {
    "trend_mode": "Positive",
    "season_mode": "Festival",
    "avg_confidence": 0.78,
    "avg_risk_score": 0.45
  }
}
```

---

### `GET /api/v1/twins/{twin_id}/history`

Get state change audit log for a twin.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Max entries to return |
| `offset` | integer | 0 | Pagination offset |

**Success Response (200):**
```json
{
  "twin_id": 1,
  "total_entries": 42,
  "entries": [
    {
      "id": 42,
      "entity_type": "product",
      "entity_id": "Widget-A",
      "field_name": "avg_demand",
      "old_value": "7600.0",
      "new_value": "7840.0",
      "changed_at": "2026-06-04T15:00:00"
    }
  ]
}
```

---

### `DELETE /api/v1/twins/{twin_id}`

Delete a twin and all related state (cascade).

**Success Response (200):**
```json
{
  "status": "deleted",
  "twin_id": 1
}
```

---

### EWMA State Updates

When a simulation is run with `twin_id`, the twin state is automatically updated:

| Domain | Fields Updated | Method |
|--------|---------------|--------|
| Product | `avg_demand`, `demand_trend`, `latest_stock`, `latest_demand` | EWMA (α=0.3) + ±10% trend thresholds |
| Warehouse | `times_selected`, `utilization_pct`, `selection_rate`, `avg_risk_score` | Count + EWMA |
| Supplier | `avg_delay`, `max_delay_seen`, `reliability_score` | EWMA + max tracking |
| Market | `trend_mode`, `season_mode`, `avg_confidence`, `avg_risk_score` | Mode tracking + EWMA |

> **Design Note:** SupplierState is a V1 aggregate model tracking global supplier metrics. In future phases, this will evolve into per-supplier state models.
> The Digital Twin evolves from simulation outcomes and user-generated simulations, not from real-world operational telemetry.

---

## Error Codes

| HTTP Code | Error Type | Description |
|-----------|-----------|-------------|
| 404 | `NOT_FOUND` | Simulation or result not found |
| 422 | `VALIDATION_ERROR` | Invalid input (Pydantic validation) |
| 500 | `SIMULATION_ERROR` | Agent pipeline internal failure |

## Warehouse Network

> **W1, W2, and W3 are hardcoded simulation warehouses.** They are static configuration inside `logistics_agent.py`, not database entries or API-configurable resources. They exist to give the LogisticsAgent a non-trivial optimization problem with three distinct fulfillment strategies.

| ID | Route | Capacity | Cost Factor | Strategy | When Selected |
|----|-------|----------|-------------|----------|---------------|
| W1 | R1 | 10,000 | 1.0× | Standard (balanced) | Balanced demand, cost-sensitive |
| W2 | R4 | 15,000 | 1.2× | Premium (high capacity) | High demand exceeding W1/W3 capacity |
| W3 | R7 | 8,000 | 0.9× | Budget (lowest cost) | Low demand where cost optimization wins |

**Selection algorithm:** `score = capacity_fit × 0.6 + cost_score × 0.4 + home_bonus(0.15)`

**Routes** (R1, R4, R7) are static labels paired 1:1 with warehouses — not independently configurable.

See [ARCHITECTURE.md § Warehouse Network](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/ARCHITECTURE.md) for full design rationale and future evolution path.

## Agent Pipeline

```
SimulationInput
     │
     ▼
┌─────────────────────────────────────────────┐
│               DecisionAgent                  │
│  ┌───────────┐  ┌──────────────┐            │
│  │DemandAgent│→ │InventoryAgent│            │
│  └───────────┘  └──────────────┘            │
│  ┌────────────────┐  ┌──────────┐           │
│  │ LogisticsAgent  │  │RiskAgent │           │
│  └────────────────┘  └──────────┘           │
│         │                                    │
│         ▼                                    │
│  ┌──────────────────┐                       │
│  │ ExplanationAgent  │                       │
│  └──────────────────┘                       │
└─────────────────────────────────────────────┘
     │
     ▼
SimulationResult (with agent_breakdown)
```

## Confidence Weights

| Agent | Weight | Rationale |
|-------|--------|-----------|
| RiskAgent | 0.40 | Highest business impact |
| DemandAgent | 0.25 | Drives inventory decisions |
| InventoryAgent | 0.20 | Follows from demand |
| LogisticsAgent | 0.15 | Binary warehouse selection |

---

## Forecasting (Phase E2)

> Deterministic EWMA-based demand forecasting from Digital Twin state.
> No ML, no external APIs — pure extrapolation.

### `GET /api/v1/twins/{twin_id}/forecast`

Generate demand forecasts for a product using twin state.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `product` | string | *required* | Product name to forecast |
| `horizons` | string | `"1,3,5"` | Comma-separated horizon periods |

**Forecast Formula:**
```
forecast_demand = avg_demand × trend_factor × season_factor
```
- **Demand is pure demand** — no supply contamination.
- **Supply risk** is a separate field (`Low`/`Medium`/`High`).
- **Confidence** absorbs uncertainty from sim count, horizon, trend, and supply.

**Response (200):**
```json
{
  "twin_id": 1,
  "product": "Widget-A",
  "generated_at": "2026-06-04T15:00:00+00:00",
  "source_state": {
    "avg_demand": 8600.0,
    "demand_trend": "Rising",
    "simulation_count": 7,
    "season": "Festival",
    "supplier_reliability": 75.0
  },
  "forecasts": [
    {
      "horizon": 1,
      "forecast_demand": 10389.0,
      "trend_factor": 1.05,
      "season_factor": 1.15,
      "supply_risk": "Medium",
      "confidence": 0.55,
      "explanation": "Forecast for Widget-A at horizon 1: base demand 8,600.0 (EWMA α=0.3) × trend 1.05 (Rising +5%/horizon) × season 1.15 (Festival) = 10,389.0. Supply risk: Medium (reliability 75.0%). Confidence: 0.55 (7 simulations, Rising trend)."
    }
  ]
}
```

**Error Responses:**
- `404` — Twin not found or product has no simulation history.
- `422` — Invalid horizons format.

---

### `GET /api/v1/twins/{twin_id}/forecasts`

List previously generated forecast records (audit trail).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `product` | string | optional | Filter by product name |
| `limit` | integer | 20 | Max records to return |

**Response (200):**
```json
{
  "twin_id": 1,
  "total_records": 3,
  "records": [
    {
      "id": 1,
      "product_name": "Widget-A",
      "horizon": 1,
      "forecast_demand": 10389.0,
      "trend_factor": 1.05,
      "season_factor": 1.15,
      "supply_risk": "Medium",
      "confidence": 0.55,
      "explanation": "...",
      "source_avg_demand": 8600.0,
      "source_trend": "Rising",
      "source_season": "Festival",
      "source_reliability": 75.0,
      "created_at": "2026-06-04T15:00:00"
    }
  ]
}
```

---

### `GET /api/v1/twins/{twin_id}/forecast/summary`

Get latest horizon-1 forecast summary for all products.
**Read-only** — does NOT generate new forecasts.

**Response (200):**
```json
{
  "twin_id": 1,
  "products": [
    {
      "product": "Widget-A",
      "avg_demand": 8600.0,
      "demand_trend": "Rising",
      "latest_forecast": {
        "forecast_demand": 10389.0,
        "confidence": 0.55,
        "supply_risk": "Medium",
        "generated_at": "2026-06-04T15:00:00"
      }
    }
  ]
}
```

> `latest_forecast` is `null` if no forecasts have been generated yet.

---

### Forecast Confidence Formula

#### Base Confidence (E2)

```
base       = min(sim_count / 10, 1.0)
horizon    = -0.10 x h
trend      = +0.05 if Stable, -0.05 otherwise
supplier   = +0.05 if reliability >= 80, 0.0 if >= 50, -0.10 if < 50
base_confidence = clamp(base + horizon + trend + supplier, 0.1, 1.0)
```

#### Signal Penalty (E4)

When active signals exist, confidence is further reduced:

```
signal_penalty  = sum(weight[source] x severity)  for each active signal
final_confidence = clamp(base_confidence - signal_penalty, 0.1, 1.0)
```

| Signal Source | Weight | Max Penalty | Rationale |
|---------------|--------|-------------|-----------|
| `DemandSpike` | 0.10 | -0.10 | Demand volatility |
| `SupplierDegradation` | 0.15 | -0.15 | Supply disruption (highest impact) |
| `WarehouseOverload` | 0.08 | -0.08 | Operational constraint |
| `TrendShift` | 0.00 | 0.00 | Already in trend_factor |

**Examples:**

| Scenario | Base Conf | Signal Penalty | Final Conf |
|----------|:---------:|:--------------:|:----------:|
| No signals | 0.80 | 0.00 | 0.80 |
| DemandSpike (sev 0.5) | 0.80 | -0.05 | 0.75 |
| SupplierDeg (sev 0.67) | 0.70 | -0.10 | 0.60 |
| Both | 0.70 | -0.15 | 0.55 |

> **Backward Compatibility:** When no signals are active, final_confidence = base_confidence (identical to E2).

### Risk Elevation (E4)

Supply risk may be elevated by one tier when critical signals exist:

| Condition | Effect |
|-----------|--------|
| SupplierDegradation severity > 0.5 | Risk elevated one tier |
| WarehouseOverload severity > 0.5 | Risk elevated one tier |
| Severity <= 0.5 | No elevation |
| DemandSpike / TrendShift | Cannot elevate risk |
| Already "High" | Stays "High" |

### Explanation Audit Trail (E4)

When signals affect the forecast, the explanation includes a full audit trail:

```
[standard E2 explanation]
Signal adjustments: Base confidence 0.80, signal penalties 
[DemandSpike penalty: -0.05 (severity 0.50)], final confidence 0.75.
Risk elevated from Low to Medium due to SupplierDegradation, severity 0.67.
```

This allows users to reconstruct the full confidence calculation:
1. Base confidence (from E2 formula)
2. Each signal penalty (source, amount, severity)
3. Final confidence (after all penalties)
4. Risk elevation (if any)

### Factor Reference

| Factor | Rising | Stable | Falling |
|--------|--------|---------|---------|
| Trend (per horizon) | +5% | 0% | -3% |

| Factor | Festival | Normal | Off-season |
|--------|----------|--------|------------|
| Season | x1.15 | x1.0 | x0.85 |

| Reliability | >=80 | 50-80 | <50 |
|-------------|------|-------|-----|
| Supply Risk | Low | Medium | High |

---

## Signal Intelligence (Phase E3)

> **Concept:** Signal Intelligence is an automated pattern-recognition layer that continuously evaluates Digital Twin state after each simulation. It detects anomalies, risks, and trend shifts, persisting them as `SignalEvent` records for analysis and forecasting augmentation.
>
> **Key Design Decisions:**
> - **No deduplication:** Each simulation occurrence emits its own signals (preserves full event timeline).
> - **Retention:** All-time (no cleanup or archival in current phase — see TD4).
> - **Health score:** Recency-weighted average of last 10 signals (newest weight = 10, oldest = 1).

### `GET /api/v1/twins/{twin_id}/signals`

List all signal events for a Digital Twin.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `signal_type` | string | optional | Filter by type: `"demand"` \| `"supply"` \| `"risk"` \| `"market"` |
| `min_severity` | float | optional | Minimum severity threshold (0.0–1.0) |
| `limit` | integer | 50 | Max results to return |

**Response (200):**
```json
{
  "twin_id": 1,
  "total_signals": 5,
  "signals": [
    {
      "id": 1,
      "source": "DemandSpike",
      "signal_type": "demand",
      "severity": 0.5,
      "severity_label": "warning",
      "payload": {
        "product": "Widget-A",
        "latest_demand": 12000,
        "avg_demand": 8000,
        "spike_ratio": 1.5
      },
      "detected_at": "2026-06-05T10:30:00"
    }
  ]
}
```

**Error Response (404):** Twin not found.

---

### `GET /api/v1/twins/{twin_id}/signals/summary`

Get aggregated signal health summary for a twin.

**Response (200):**
```json
{
  "twin_id": 1,
  "total_signals": 8,
  "health_score": 0.72,
  "health_label": "warning",
  "by_type": {
    "demand": 3,
    "supply": 2,
    "risk": 2,
    "market": 1
  },
  "by_severity": {
    "info": 2,
    "warning": 4,
    "critical": 2
  }
}
```

**Error Response (404):** Twin not found.

---

### Signal Detectors

| Detector | Source | Type | Condition | Severity Formula |
|----------|--------|------|-----------|------------------|
| `DemandSpikeDetector` | `DemandSpike` | `demand` | `latest_demand > avg_demand × 1.25` | `min(1.0, spike_ratio - 1.0)` |
| `SupplierDegradationDetector` | `SupplierDegradation` | `supply` | `reliability_score < 60.0` | `min(1.0, (60 - score) / 60)` |
| `WarehouseOverloadDetector` | `WarehouseOverload` | `risk` | `utilization_pct > 0.85` | `min(1.0, (util - 0.85) / 0.15)` |
| `TrendShiftDetector` | `TrendShift` | `market` | `demand_trend` changed in latest simulation | Lookup table (see below) |

### Trend Shift Severity Map

| Shift | Severity | Type |
|-------|----------|------|
| Stable → Rising | 0.3 | acceleration |
| Stable → Falling | 0.3 | deceleration |
| Rising → Stable | 0.2 | deceleration |
| Falling → Stable | 0.2 | acceleration |
| Rising ↔ Falling | 0.8 | reversal |

### Severity Labels

| Range | Label |
|-------|-------|
| 0.0 – 0.29 | `info` |
| 0.30 – 0.69 | `warning` |
| 0.70 – 1.00 | `critical` |

### Health Score Formula

```
health_score = 1.0 - weighted_average(last 10 signals by severity)

Weights: newest signal = 10, oldest = 1 (recency-weighted)
If no signals: health_score = 1.0
If all signals severity=1.0: health_score = 0.0
```

---

### Forecast + Signals Integration

The `GET /api/v1/twins/{twin_id}/forecast` response now includes an `active_signals` field:

```json
{
  "twin_id": 1,
  "product": "Widget-A",
  "forecasts": [ ... ],
  "active_signals": [
    {
      "source": "DemandSpike",
      "signal_type": "demand",
      "severity": 0.5,
      "payload": { "product": "Widget-A", ... }
    },
    {
      "source": "SupplierDegradation",
      "signal_type": "supply",
      "severity": 0.33,
      "payload": { "reliability_score": 40.0, ... }
    }
  ]
}
```

> **Selection Logic:** Active signals include:
> 1. Product-specific signals (e.g., DemandSpike for the requested product)
> 2. Twin-wide signals (e.g., SupplierDegradation, WarehouseOverload)
>
> Signal filtering uses the last 10 signals (recency window).

---

## External Intelligence (Phase E5)

> **Concept:** External Intelligence extends the Signal Engine with data from the outside world — news, weather, commodity prices, and economic indicators. External data is fetched by configurable providers (synthetic by default), cached in the database, and evaluated by detectors that follow the same `SignalDetector` ABC as E3 internal detectors.
>
> **Key Design Decisions:**
> - **Provider abstraction:** `DataProvider` ABC with synthetic defaults. Real APIs swappable via config.
> - **Cache-based evaluation:** Detectors read from `ExternalDataCache`, never call APIs directly during evaluation.
> - **Graceful degradation:** Missing/expired cache → detector returns empty list → forecast unaffected.
> - **Global scope:** News, Commodity, Economic signals are global. Weather prepared for future twin-scoping.
> - **Schema versioning:** `schema_version` field on cache entries for future payload evolution.

### External Signal Sources

| Source | Detector | Trigger Condition | Severity Formula |
|--------|----------|-------------------|------------------|
| `NewsDisruption` | `NewsDisruptionDetector` | Relevance score > 40 | `min(1.0, relevance / 100)` |
| `WeatherAlert` | `WeatherAlertDetector` | Severity level >= moderate | minor=0.2, moderate=0.4, severe=0.7, extreme=1.0 |
| `CommodityShock` | `CommodityShockDetector` | Price change > ±10% | `min(1.0, abs(change_pct) / 30)` |
| `EconomicShift` | `EconomicShiftDetector` | PMI < 45 or Inflation > 5% | PMI: `(50-pmi)/20`, Inflation: `(inflation-3)/5` |

### External Signal Confidence Weights

| Signal Source | Weight | Can Elevate Risk |
|---------------|:------:|:----------------:|
| `NewsDisruption` | 0.06 | No |
| `WeatherAlert` | 0.10 | Yes (severity > 0.5) |
| `CommodityShock` | 0.08 | No |
| `EconomicShift` | 0.05 | No |

### `GET /api/v1/external/status`

Returns cache status for all external data providers.

E7 enhancement: includes active provider mode, category, and API key configuration
status for each cached provider. API keys are never exposed.

**Response:**

```json
{
  "provider_mode": "auto",
  "providers": {
    "news_synthetic": {
      "category": "news",
      "mode": "synthetic",
      "api_key_configured": false,
      "last_refresh": "2026-06-07T12:00:00",
      "cached": true,
      "schema_version": 1,
      "expires_in_minutes": 340.5,
      "is_valid": true
    },
    "weather_real": {
      "category": "weather",
      "mode": "real",
      "api_key_configured": true,
      "last_refresh": "2026-06-07T12:00:00",
      "cached": true,
      "schema_version": 2,
      "expires_in_minutes": 540.2,
      "is_valid": true
    }
  },
  "refresh_interval_hours": 6,
  "cache_ttl_hours": 12
}
```

### `GET /api/v1/external/config`

**New in E7.** Inspect provider configuration without exposing secrets.
Shows which providers are active for each category, whether API keys
are configured, and the current provider mode.

**Response:**

```json
{
  "mode": "auto",
  "refresh_interval_hours": 6,
  "cache_ttl_hours": 12,
  "providers": {
    "news": {
      "configured": false,
      "active_provider": "news_synthetic"
    },
    "weather": {
      "configured": true,
      "active_provider": "weather_real"
    },
    "commodity": {
      "configured": true,
      "active_provider": "commodity_real"
    },
    "economic": {
      "configured": false,
      "active_provider": "economic_synthetic"
    }
  }
}
```

### `POST /api/v1/external/refresh`

Manually trigger a refresh of all external data providers.
Uses the configured provider mode (auto/synthetic/real).

**Response:**

```json
{
  "refreshed": true,
  "mode_used": "auto",
  "results": {
    "news": true,
    "weather": true,
    "commodity": true,
    "economic": true
  }
}
```

### Provider Architecture

```
DataProvider (ABC)
├── SyntheticNewsProvider       → news_synthetic  (schema_v=1)
├── SyntheticWeatherProvider    → weather_synthetic (schema_v=1)
├── SyntheticCommodityProvider  → commodity_synthetic (schema_v=1)
├── SyntheticEconomicProvider   → economic_synthetic (schema_v=1)
├── NewsAPIProvider             → news_real (schema_v=2, newsapi.org)
├── OpenWeatherMapProvider      → weather_real (schema_v=2, openweathermap.org)
├── AlphaVantageProvider        → commodity_real (schema_v=2, alphavantage.co)
└── FREDProvider                → economic_real (schema_v=2, api.stlouisfed.org)
```

Providers are selected via `get_provider(category, mode)`. Default mode: `"auto"`.

**Provider Selection Modes:**

| Mode | Behavior |
|------|----------|
| `auto` (default) | Use real provider if API key configured, otherwise synthetic |
| `synthetic` | Always use synthetic providers |
| `real` | Always use real providers (requires API keys) |

### Synthetic Data Behavior

| Provider | Determinism | Data Pattern |
|----------|-------------|-------------|
| News | `hash(data_key + time_bucket)` | 0-3 events with varying relevance scores |
| Weather | `hash(data_key + time_bucket)` | One condition from severity spectrum |
| Commodity | `hash(data_key + time_bucket)` | 5 commodities with sine-wave + noise prices |
| Economic | `hash(data_key + time_bucket)` | PMI (30-65), Inflation (0.5-8%), Consumer Confidence (60-140) |

Time bucket = 6 hours. Same bucket = same output (reproducible within cache cycle).

### Real Provider Configuration (E7)

| Provider | API | Free Tier | Rate Limit | Env Variable |
|----------|-----|-----------|------------|--------------|
| NewsAPI | newsapi.org | 100 req/day | 5/min | `NEWSAPI_KEY` |
| OpenWeatherMap | openweathermap.org | 1000 req/day | 60/min | `OPENWEATHERMAP_KEY` |
| Alpha Vantage | alphavantage.co | 25 req/day | 5/min | `ALPHAVANTAGE_KEY` |
| FRED | api.stlouisfed.org | Unlimited | 120/min | `FRED_KEY` |

**Fail-Soft Behavior:**
- Invalid/missing API keys log warnings and fall back to synthetic providers
- Provider failures return empty data, preserving the last valid cache entry
- Short API keys (< 8 chars) trigger warnings but are still used

### Cache Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Refresh interval | 6 hours | Background scheduler frequency |
| Cache TTL | 12 hours | Entry expiration time |
| Provider mode | `auto` | Provider selection strategy |

### Database: `external_data_cache`

| Column | Type | Description |
|--------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `provider` | str (indexed) | Provider name |
| `data_key` | str (indexed) | Scope key (e.g., "global") |
| `data_json` | Text | Cached JSON payload |
| `schema_version` | int | Provider payload version |
| `fetched_at` | datetime | Last fetch timestamp |
| `expires_at` | datetime (indexed) | Cache expiry time |

---

## Compound Signals (Phase E6)

### `GET /api/v1/compound-rules`

List all registered compound signal rules. Read-only introspection endpoint.

**Response:**
```json
{
  "total_rules": 5,
  "rules": [
    {
      "name": "SupplyShock",
      "triggers": ["DemandSpike", "SupplierDegradation"],
      "severity_fn": "max",
      "severity_boost": 1.0,
      "min_trigger_severity": 0.3,
      "confidence_weight": 0.12,
      "can_elevate_risk": true,
      "description": "Simultaneous demand surge and supplier degradation..."
    }
  ]
}
```

### Compound Signal Rules

| Compound Signal | Triggers | Severity Fn | Boost | Confidence Weight | Risk Elevation |
|-----------------|----------|-------------|-------|-------------------|----------------|
| `SupplyShock` | DemandSpike + SupplierDegradation | max | 1.0 | 0.12 | Yes |
| `FulfillmentCrisis` | WarehouseOverload + DemandSpike | max_boosted | 1.2 | 0.10 | Yes |
| `MarketDisruption` | TrendShift + SupplierDegradation | max | 1.0 | 0.08 | No |
| `PerfectStorm` | WeatherAlert + SupplierDeg + DemandSpike | max_boosted | 1.3 | 0.15 | Yes |
| `CostSqueeze` | CommodityShock + EconomicShift | avg | 1.0 | 0.06 | No |

### Design Decisions

- **Additive Penalty Stacking**: Compound penalties stack additively with their atomic trigger penalties. This is intentional to reflect compounded risk. Calibration will be reviewed in Post-E6 Business Logic Audit.
- **Phase 2 Evaluation**: Compounds are evaluated after all atomic signals (Phase 1), reading from the same evaluation batch. No database round-trip required.
- **signal_type="compound"**: All compound signals use this type, distinct from atomic types (demand, supply, risk, market, external).
- **No Cascading**: Compound signals cannot trigger other compound signals.

### SignalCountByType Schema (Updated)

```json
{
  "demand": 3,
  "supply": 1,
  "risk": 0,
  "market": 1,
  "external": 2,
  "compound": 1
}
```

> `external` field added to fix E5 schema gap. `compound` field added for E6.

