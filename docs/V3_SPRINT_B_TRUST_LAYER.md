# V3.0 Sprint B -- Trust Layer

## Problem

The recommendation engine works. Sprint A proved that.

But no customer will trust it yet.

The first question every customer asks:

> "How accurate is this?"

Not: "Can it generate a PO?"

Trust comes from **measurement**. Sprint B builds the measurement layer.

---

## What Sprint B Delivers

```
Historical Demand --> Forecast Accuracy --> Recommendation Outcomes --> Trust Dashboard
```

| Capability | Purpose |
|------------|---------|
| Historical Demand Import | "Here's what actually happened" |
| Forecast Accuracy Engine | MAPE, Bias, Accuracy, Coverage -- per product |
| Recommendation Outcome Tracking | "Did the recommendation help?" |
| Split Dashboard: Health + Trust | Business state vs SynChain quality |

What Sprint B does NOT build:
- Purchase Orders (V4.0)
- ERP integration (V4.0)
- Mobile App (V5.0)
- AI Assistant (V5.0)

---

## CRITICAL: Horizon Definition

### The Problem

The forecast engine generates forecasts at horizons `[1, 3, 5]`.
These were previously described as "abstract planning periods."

For accuracy computation, horizons MUST map to real time.
Without this mapping, `forecast_demand` cannot be compared to `actual_demand`.

### The Definition

**Horizon N = the Nth 30-day period from forecast generation date.**

| Horizon | Meaning | Example (forecast generated June 1) |
|---------|---------|-------------------------------------|
| 1 | Days 1-30 from generation | June 1 - June 30 |
| 3 | Days 61-90 from generation | August 1 - August 30 |
| 5 | Days 121-150 from generation | October 1 - October 30 |

### Matching Rule for Accuracy

```
forecast_record.created_at  = June 1, 2026
forecast_record.horizon     = 1
forecast_record.forecast_demand = 820

--> This predicts demand for: June 1 - June 30

actual_demand.period_start  = 2026-06-01
actual_demand.period_end    = 2026-06-30
actual_demand.actual_units  = 780

--> Error = |820 - 780| / 780 = 5.1%
```

### Why 30 Days

- Manufacturers track monthly
- Monthly demand is the base unit in `avg_monthly_demand`
- The forecast formula `avg_demand * trend_factor * season_factor` produces monthly demand
- Lead times are expressed in days and compared against monthly demand rates

### Computed Period for Any Forecast Record

```python
def forecast_period(created_at: datetime, horizon: int) -> tuple[date, date]:
    """Compute the calendar period a forecast record predicts."""
    period_start = created_at.date() + timedelta(days=(horizon - 1) * 30)
    period_end = period_start + timedelta(days=29)
    return period_start, period_end
```

This function lives in the accuracy engine. It is the SINGLE source of truth
for how forecasts map to calendar periods. No other module interprets horizons.

---

## Data Model

### New Table: `actual_demand` (Historical Demand Records)

This is the **ground truth**. Without it, accuracy is just a number.

```
actual_demand
  id              INT PK
  company_id      INT FK --> companies.id (indexed)
  product_id      INT FK --> products.id (indexed)
  period_start    DATE (first day of period)
  period_end      DATE (last day of period)
  actual_units    FLOAT (actual units sold/consumed)
  source          VARCHAR -- 'csv_import' | 'manual' | 'api'
  created_at      TIMESTAMP
  UNIQUE(product_id, period_start)
```

Design decisions:
- Period-based (not daily) -- manufacturers track monthly/weekly, not daily
- `period_start + period_end` allows flexible period lengths
- `source` tracks where data came from (audit trail)
- Unique constraint prevents duplicate entries for the same period

### New Table: `recommendation_outcomes` (Did It Help?)

Tracks whether a recommendation was acted on and what happened.

```
recommendation_outcomes
  id                  INT PK
  company_id          INT FK --> companies.id (indexed)
  product_id          INT FK --> products.id (indexed)
  recommendation_date DATE (when recommendation was generated)
  severity_at_time    VARCHAR -- CRITICAL|HIGH|MEDIUM|LOW|NONE
  recommended_qty     FLOAT
  action_taken        VARCHAR -- see Action Types below
  actual_qty_ordered  FLOAT (nullable -- what they actually ordered)
  order_date          DATE (nullable -- when they actually ordered)
  stockout_occurred   BOOLEAN (did they actually run out?)
  notes               TEXT (optional human note)
  created_at          TIMESTAMP
  resolved_at         TIMESTAMP (nullable)
  UNIQUE(product_id, recommendation_date)
```

### Action Types

| Value | Meaning | Example |
|-------|---------|---------|
| `ordered` | Full order placed | Recommended 500, ordered 500 |
| `partially_ordered` | Reduced order placed | Recommended 500, ordered 250 |
| `ignored` | No action taken | Recommendation dismissed |
| `alternative_action` | Did something different | Switched supplier, used substitute part |
| `pending` | Not yet decided | Default state |

Design decisions:
- `partially_ordered` distinguishes "ordered 450/500" from "ordered 50/500"
- `alternative_action` captures creative responses the system didn't predict
- `action_taken` is human-entered -- the system doesn't know if they ordered
- `stockout_occurred` is the ground truth for recommendation quality
- This becomes the feedback loop for improving the engine in V4.0

### NO `forecast_accuracy` Table

Accuracy is **derived data**. It comes from:
- `forecast_records` (what we predicted)
- `actual_demand` (what actually happened)

Storing it creates staleness:
```
forecast changes --> actual changes --> accuracy stale
```

Instead: accuracy is computed on-the-fly by the service layer.
The engine functions are pure and fast. No caching needed.

---

## Accuracy Metrics

### Per-Product Metrics

| Metric | Formula | Purpose |
|--------|---------|---------|
| **MAPE** | `mean(\|forecast - actual\| / actual) * 100` | "How far off are we on average?" |
| **Bias** | `mean((forecast - actual) / actual) * 100` | "Do we consistently over/under-predict?" |
| **Accuracy** | `100 - MAPE` | "What % of the time are we right?" |
| **Direction Accuracy** | `% of periods where trend direction was correct` | "Did we get the direction right?" |
| **Data Coverage** | `periods_with_actual / expected_periods * 100` | "How much data is this based on?" |

### Why Data Coverage Matters

```
Product A: Accuracy = 88%, Data Coverage = 80% (8/10 months)
Product B: Accuracy = 88%, Data Coverage = 20% (2/10 months)
```

Product A's accuracy is meaningful. Product B's is noise.

A VP will immediately ask: "How much data is this based on?"

Data Coverage answers that question before they ask.

### Coverage Grading

| Coverage | Grade | Meaning |
|----------|-------|---------|
| >= 80% | HIGH | Statistically meaningful |
| >= 50% | MODERATE | Useful but incomplete |
| >= 25% | LOW | Directional only |
| < 25% | INSUFFICIENT | Do not trust accuracy number |

### Accuracy Grading

| Accuracy | Grade | Meaning |
|----------|-------|---------|
| >= 85% | EXCELLENT | Production-ready forecasts |
| >= 70% | GOOD | Useful, some noise |
| >= 50% | FAIR | Better than guessing |
| < 50% | POOR | Needs more data / investigation |

### Company-Level Metrics

| Metric | Formula | Purpose |
|--------|---------|---------|
| **Company MAPE** | Demand-volume-weighted average of product MAPEs | "Overall forecast quality" |
| **Company Accuracy** | `100 - Company MAPE` | Executive KPI |
| **Company Coverage** | `products_with_data / total_products * 100` | "How much of our catalog is measured?" |
| **Recommendation Hit Rate** | `(ordered + partially_ordered) / total * 100` | "How often do they trust us?" |
| **Stockout Prevention Rate** | `1 - (stockouts / total) * 100` | "Are we preventing problems?" |

---

## Split Dashboard: Health Score + Trust Score

### Why Split

Mixing Model Quality with Business State is wrong.

A company with:
- Terrible inventory (stockouts everywhere)
- Perfect forecasts (88% accuracy)

would score high under a single blended score. That's misleading.

### Inventory Health Score (Business State)

"How healthy is this company's inventory RIGHT NOW?"

| Component | Weight | Source |
|-----------|-------:|--------|
| Stockout Safety | 30% | Days of coverage across products |
| Supplier Reliability | 25% | Weighted avg supplier reliability |
| Signal Health | 25% | Active critical/high signals |
| Inventory Position | 20% | Stock vs demand ratio |

Grading: HEALTHY (>= 80) | MODERATE (>= 60) | AT_RISK (>= 40) | CRITICAL (< 40)

### SynChain Trust Score (Platform Quality)

"How much should you trust SynChain's predictions?"

| Component | Weight | Source |
|-----------|-------:|--------|
| Forecast Accuracy | 35% | Company MAPE (100 - MAPE) |
| Data Coverage | 25% | Products with actuals / total |
| Recommendation Hit Rate | 25% | Orders placed / recommendations |
| Forecast Confidence | 15% | Avg engine confidence |

Grading: TRUSTED (>= 80) | BUILDING (>= 60) | DEVELOPING (>= 40) | INSUFFICIENT (< 40)

### Executive View

```
INVENTORY HEALTH:   72/100  (MODERATE)
SYNCHAIN TRUST:     84/100  (TRUSTED)

  Health: Stockout Safety 65, Supplier 82, Signals 78, Position 60
  Trust:  Accuracy 88%, Coverage 80%, Hit Rate 78%, Confidence 82%
```

Two numbers. Two questions answered:
1. "How's my inventory?" --> Health
2. "Can I trust this system?" --> Trust

---

## Import Format

### Actual Demand CSV

```csv
product_name,period_start,period_end,actual_units
Aluminum Sheet 4x8,2026-01-01,2026-01-31,780
Aluminum Sheet 4x8,2026-02-01,2026-02-28,820
Aluminum Sheet 4x8,2026-03-01,2026-03-31,855
Steel Rod 1/2 inch,2026-01-01,2026-01-31,610
Steel Rod 1/2 inch,2026-02-01,2026-02-28,590
```

Rules:
- `product_name` must match an existing product in the company
- `period_start` must be a valid date (ISO format: YYYY-MM-DD)
- `period_end` must be after `period_start`
- `actual_units` must be >= 0
- Duplicates (same product + period_start) are UPDATED, not rejected
- CSV import follows existing pattern in `company/csv_import.py`

### Recommendation Outcome CSV

```csv
product_name,recommendation_date,action_taken,actual_qty_ordered,order_date,stockout_occurred,notes
Connector USB-C,2026-07-01,ordered,700,2026-07-02,false,Emergency order placed
Heat Sink 40x40mm,2026-07-01,ignored,0,,true,Supplier found alternative
Gear Module 0.5,2026-07-01,partially_ordered,80,2026-07-03,false,Budget constrained
PCB Board Rev3,2026-07-15,alternative_action,0,,false,Switched to alternate component
```

---

## API Endpoints (Sprint B)

### Actual Demand Import
```
POST /api/v1/companies/{id}/import/actual-demand
  Body: multipart/form-data (CSV file)
  Returns: { imported: N, updated: N, skipped: N, errors: [...] }
```

### Forecast Accuracy (computed on-the-fly, not stored)
```
GET /api/v1/companies/{id}/forecast-accuracy
  Query: ?product_id=X (optional filter)
  Returns: {
    company_accuracy: { mape, bias, accuracy, grade, coverage, coverage_grade },
    products: [{
      product_id, product_name,
      mape, bias, accuracy, grade,
      coverage, coverage_grade,
      data_points, expected_periods
    }]
  }
```

### Recommendation Outcomes
```
POST /api/v1/companies/{id}/import/outcomes
  Body: multipart/form-data (CSV file)
  Returns: { imported: N, updated: N, errors: [...] }

GET /api/v1/companies/{id}/recommendation-outcomes
  Returns: {
    total_recommendations: N,
    outcomes: {
      ordered: N,
      partially_ordered: N,
      ignored: N,
      alternative_action: N,
      pending: N
    },
    hit_rate: 0.78,
    stockout_prevention_rate: 0.92
  }
```

### Split Dashboard
```
GET /api/v1/companies/{id}/inventory-health
  Returns: {
    score: 72, grade: "MODERATE",
    components: { stockout_safety, supplier_reliability, signal_health, inventory_position }
  }

GET /api/v1/companies/{id}/trust-score
  Returns: {
    score: 84, grade: "TRUSTED",
    components: { forecast_accuracy, data_coverage, recommendation_hit_rate, forecast_confidence }
  }
```

---

## Success Criteria

Sprint B is done when:

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | Actual demand CSV imports successfully | Import 6 months of data for 5 products |
| 2 | MAPE/Bias/Accuracy computed per product | API returns correct metrics |
| 3 | Data Coverage computed and graded | Low-data products flagged |
| 4 | Company-level accuracy aggregated | Weighted by demand volume |
| 5 | Recommendation outcomes recorded | CSV import with 5 action types |
| 6 | Hit rate and stockout prevention computed | API returns correct rates |
| 7 | Health Score = business state only | No model quality mixed in |
| 8 | Trust Score = SynChain quality only | No business state mixed in |
| 9 | All computations are pure functions | Engine layer has no DB access |
| 10 | Unit tests cover accuracy edge cases | Division by zero, single data point, no data |
| 11 | Business validation audit passes | "Would a supply chain VP trust these numbers?" |

---

## Implementation Order

```
Step 1: Data Model + Migrations
  --> actual_demand table
  --> recommendation_outcomes table
  --> NO forecast_accuracy table (computed on-the-fly)

Step 2: Actual Demand Import
  --> CSV parser (follows existing pattern)
  --> Validation + upsert logic
  --> API endpoint

Step 3: Accuracy Engine (pure functions)
  --> forecast_period() -- horizon to calendar mapping
  --> MAPE, Bias, Accuracy per product
  --> Data Coverage per product
  --> Company-level aggregation
  --> Grading logic

Step 4: Accuracy Service + API
  --> DB orchestration (loads forecasts + actuals, computes on-the-fly)
  --> Query endpoint (no store)

Step 5: Recommendation Outcome Import
  --> CSV parser (5 action types)
  --> Outcome tracking API
  --> Hit rate / stockout prevention

Step 6: Split Health + Trust Dashboard
  --> Refactor calculate_inventory_health() -- business only
  --> New calculate_trust_score() -- SynChain quality only
  --> Two separate API endpoints

Step 7: Unit Tests + Business Audit
  --> Engine tests (pure functions)
  --> Coverage edge cases
  --> Business validation with realistic data
```

Each step is independently verifiable before moving to the next.
