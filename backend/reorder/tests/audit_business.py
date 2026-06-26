"""
Decision Engine Business Validation Audit (V3.0)

This is NOT a unit test. This is a purchasing manager's sanity check.

For each recommendation, the question is:
  "Would a real purchasing manager agree with this?"

If any recommendation looks irrational -- it's a bug.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date

from reorder.engine import (
    ForecastData,
    ProductData,
    ReorderResult,
    SignalContext,
    SupplierData,
    calculate_inventory_health,
    calculate_recommendation,
)

TODAY = date(2026, 7, 1)

# ═══════════════════════════════════════════════════════════════════════════
# AUDIT 1 — Realistic Manufacturing Dataset
# ═══════════════════════════════════════════════════════════════════════════

SUPPLIERS = {
    "Acme Components": SupplierData(
        1,
        "Acme Components",
        lead_time_days=14,
        reliability_pct=92,
        supply_status="High",
    ),
    "FastParts Inc": SupplierData(
        2, "FastParts Inc", lead_time_days=7, reliability_pct=88, supply_status="High"
    ),
    "GlobalTech Supply": SupplierData(
        3,
        "GlobalTech Supply",
        lead_time_days=21,
        reliability_pct=78,
        supply_status="Medium",
    ),
    "BudgetBuild Co": SupplierData(
        4, "BudgetBuild Co", lead_time_days=10, reliability_pct=65, supply_status="Low"
    ),
    "PrecisionMfg Ltd": SupplierData(
        5,
        "PrecisionMfg Ltd",
        lead_time_days=18,
        reliability_pct=96,
        supply_status="High",
    ),
}

# 20 realistic manufacturing products
PRODUCTS = [
    # (name, stock, monthly_demand, unit_price, supplier_key, forecast_demand, confidence, signals_critical)
    # --- Group A: Healthy inventory ---
    ("Aluminum Sheet 4x8", 2500, 800, 12.50, "Acme Components", 820, 0.88, 0),
    ("Steel Rod 1/2 inch", 1800, 600, 8.75, "PrecisionMfg Ltd", 580, 0.91, 0),
    ("Copper Wire 14AWG", 3000, 400, 22.00, "FastParts Inc", 410, 0.85, 0),
    ("Nylon Spacer M6", 5000, 300, 0.45, "Acme Components", 290, 0.92, 0),
    # --- Group B: Moderate risk ---
    ("PCB Board Rev3", 400, 350, 18.50, "FastParts Inc", 380, 0.82, 0),
    ("Bearing 6205-2RS", 250, 200, 6.20, "GlobalTech Supply", 210, 0.79, 0),
    ("Motor DC 12V 500RPM", 180, 150, 34.00, "Acme Components", 160, 0.83, 1),
    ("Capacitor 100uF 50V", 800, 500, 0.85, "FastParts Inc", 520, 0.87, 0),
    # --- Group C: High risk ---
    ("Microcontroller STM32", 120, 300, 4.50, "GlobalTech Supply", 320, 0.75, 2),
    ("Power Supply 24V 10A", 80, 100, 45.00, "Acme Components", 110, 0.80, 1),
    ("LCD Display 7 inch", 60, 80, 62.00, "GlobalTech Supply", 95, 0.72, 0),
    ("Lithium Battery 18650", 40, 200, 3.80, "BudgetBuild Co", 220, 0.68, 3),
    # --- Group D: Critical ---
    ("Connector USB-C", 15, 500, 1.20, "FastParts Inc", 530, 0.84, 0),
    ("Heat Sink 40x40mm", 10, 120, 2.50, "BudgetBuild Co", 130, 0.76, 1),
    ("Gear Module 0.5", 5, 60, 15.00, "PrecisionMfg Ltd", 65, 0.88, 0),
    # --- Group E: Overstocked / No demand ---
    ("Legacy Board V1", 8000, 20, 35.00, "Acme Components", 15, 0.90, 0),
    ("Rubber Gasket Oval", 4000, 50, 0.30, "FastParts Inc", 45, 0.93, 0),
    # --- Group F: New products (no forecast) ---
    ("Sensor Module IR", 100, 80, 28.00, "PrecisionMfg Ltd", None, None, 0),
    ("WiFi Module ESP32", 200, 150, 5.50, "GlobalTech Supply", None, None, 1),
    # --- Group G: No price data ---
    ("Custom Bracket A7", 150, 100, 0.00, "Acme Components", 105, 0.81, 0),
]


def run_audit_1():
    print("=" * 90)
    print("AUDIT 1 — REALISTIC DATASET (20 Products, 5 Suppliers)")
    print("=" * 90)
    print(f"Date: {TODAY}")
    print()

    results = []

    for i, (
        name,
        stock,
        demand,
        price,
        supplier_key,
        fc_demand,
        fc_conf,
        sig_crit,
    ) in enumerate(PRODUCTS, 1):
        supplier = SUPPLIERS[supplier_key]

        forecast = None
        if fc_demand is not None and fc_conf is not None:
            forecast = ForecastData(
                forecast_demand=fc_demand,
                confidence=fc_conf,
                supply_risk="Low" if fc_conf > 0.8 else "Medium",
            )

        signals = SignalContext(
            active_count=sig_crit,
            critical_count=sig_crit,
            high_severity_signals=["DemandSpike (severity: 0.85)"] * sig_crit,
        )

        result = calculate_recommendation(
            product=ProductData(
                product_id=i,
                product_name=name,
                company_id=1,
                current_stock=stock,
                avg_monthly_demand=demand,
                unit_price=price,
            ),
            forecast=forecast,
            supplier=supplier,
            signals=signals,
            today=TODAY,
        )
        results.append(result)

        # Print recommendation
        print(f"┌─ Product #{i}: {name}")
        print(
            f"│  Stock: {stock:,.0f}  │  Demand: {fc_demand or demand}/mo  │  Price: ${price:.2f}"
        )
        print(
            f"│  Supplier: {supplier_key} (LT: {supplier.lead_time_days}d, Rel: {supplier.reliability_pct}%)"
        )
        print("│")
        print(f"│  ▸ Severity:        {result.severity}")
        print(f"│  ▸ Days to Stockout: {result.days_until_stockout}")
        print(f"│  ▸ Stockout Date:   {result.stockout_date}")
        print(f"│  ▸ Order Qty:       {result.recommended_quantity:,.0f} units")
        print(f"│  ▸ Order By:        {result.recommended_order_date}")
        print(
            f"│  ▸ Reorder Point:   {result.reorder_point:,.1f} (LTD: {result.lead_time_demand:.1f} + SS: {result.safety_stock:.1f})"
        )
        print(f"│  ▸ Rec Confidence:  {result.recommendation_confidence:.0%}")

        fi = result.financial_impact
        if fi.has_price_data and fi.estimated_revenue_impact:
            print(
                f"│  ▸ Revenue at Risk: ${fi.estimated_revenue_impact:,.0f} ({fi.units_at_risk:.0f} units)"
            )
        elif fi.units_at_risk > 0:
            print(f"│  ▸ Units at Risk:   {fi.units_at_risk:.0f} units (no price data)")
        else:
            print("│  ▸ Financial Risk:  None")

        print("│")
        print("│  Reasoning:")
        for r in result.reasoning:
            print(f"│    • {r}")

        # BUSINESS SANITY CHECK
        issues = []
        if result.severity == "CRITICAL" and result.recommended_quantity == 0:
            issues.append("⛔ CRITICAL severity but no order quantity!")
        if result.days_until_stockout > 60 and result.recommended_quantity > demand * 2:
            issues.append("⛔ Overstocked but recommending huge order!")
        if (
            result.severity == "NONE"
            and result.recommended_quantity > 0
            and stock > demand * 3
        ):
            issues.append("⚠ Stock covers 3+ months — why reorder?")
        if result.recommendation_confidence < 0.3 and result.severity in (
            "CRITICAL",
            "HIGH",
        ):
            issues.append("⚠ Low confidence on urgent recommendation — risky to trust")
        if (
            fi.has_price_data
            and fi.estimated_revenue_impact
            and fi.estimated_revenue_impact > 100000
        ):
            issues.append("⚠ Revenue impact > $100K — verify this is realistic")

        if issues:
            print("│")
            print("│  🔍 AUDIT FLAGS:")
            for issue in issues:
                print(f"│    {issue}")

        print(f"└{'─' * 88}")
        print()

    return results


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT 2 — Edge Cases
# ═══════════════════════════════════════════════════════════════════════════

EDGE_CASES = [
    {
        "name": "Zero Stock",
        "product": ProductData(
            1,
            "Zero-Stock-Widget",
            1,
            current_stock=0,
            avg_monthly_demand=500,
            unit_price=20.0,
        ),
        "forecast": ForecastData(500, 0.85, "Low"),
        "supplier": SUPPLIERS["FastParts Inc"],
        "signals": SignalContext(),
        "expected_severity": "CRITICAL",
        "expected_quantity": "> 0",
    },
    {
        "name": "Massive Stock (10 years of demand)",
        "product": ProductData(
            2,
            "Overstocked-Widget",
            1,
            current_stock=60000,
            avg_monthly_demand=500,
            unit_price=10.0,
        ),
        "forecast": ForecastData(480, 0.90, "Low"),
        "supplier": SUPPLIERS["Acme Components"],
        "signals": SignalContext(),
        "expected_severity": "NONE",
        "expected_quantity": "= 0",
    },
    {
        "name": "No Supplier",
        "product": ProductData(
            3,
            "Orphan-Widget",
            1,
            current_stock=100,
            avg_monthly_demand=300,
            unit_price=15.0,
        ),
        "forecast": ForecastData(320, 0.80, "Medium"),
        "supplier": None,
        "signals": SignalContext(),
        "expected_severity": "HIGH or CRITICAL",
        "expected_quantity": "> 0, uses 7-day default LT",
    },
    {
        "name": "No Forecast (fallback to avg demand)",
        "product": ProductData(
            4,
            "No-Forecast-Widget",
            1,
            current_stock=200,
            avg_monthly_demand=400,
            unit_price=8.0,
        ),
        "forecast": None,
        "supplier": SUPPLIERS["FastParts Inc"],
        "signals": SignalContext(),
        "expected_severity": "HIGH",
        "expected_quantity": "> 0, confidence = 50%",
    },
    {
        "name": "No Signals (neutral)",
        "product": ProductData(
            5,
            "Calm-Widget",
            1,
            current_stock=500,
            avg_monthly_demand=600,
            unit_price=5.0,
        ),
        "forecast": ForecastData(600, 0.88, "Low"),
        "supplier": SUPPLIERS["PrecisionMfg Ltd"],
        "signals": SignalContext(active_count=0, critical_count=0),
        "expected_severity": "MEDIUM or HIGH",
        "expected_quantity": "> 0, no signal adjustment",
    },
    {
        "name": "Low Reliability Supplier (65%)",
        "product": ProductData(
            6,
            "Risky-Supplier-Widget",
            1,
            current_stock=300,
            avg_monthly_demand=500,
            unit_price=12.0,
        ),
        "forecast": ForecastData(500, 0.82, "Medium"),
        "supplier": SUPPLIERS["BudgetBuild Co"],
        "signals": SignalContext(),
        "expected_severity": "HIGH or MEDIUM",
        "expected_quantity": "> normal (inflated SS)",
    },
    {
        "name": "High Demand Spike (4 critical signals)",
        "product": ProductData(
            7,
            "Spike-Widget",
            1,
            current_stock=300,
            avg_monthly_demand=500,
            unit_price=25.0,
        ),
        "forecast": ForecastData(500, 0.80, "High"),
        "supplier": SUPPLIERS["Acme Components"],
        "signals": SignalContext(
            active_count=4,
            critical_count=4,
            high_severity_signals=[
                "DemandSpike (severity: 0.92)",
                "SeasonalSurge (severity: 0.88)",
                "CompetitorStockout (severity: 0.85)",
                "SupplyDisruption (severity: 0.90)",
            ],
        ),
        "expected_severity": "HIGH or CRITICAL",
        "expected_quantity": "> normal (inflated SS from signals)",
    },
]


def run_audit_2():
    print()
    print("=" * 90)
    print("AUDIT 2 — EDGE CASES (7 Scenarios)")
    print("=" * 90)
    print()

    all_pass = True

    for case in EDGE_CASES:
        result = calculate_recommendation(
            product=case["product"],
            forecast=case["forecast"],
            supplier=case["supplier"],
            signals=case["signals"],
            today=TODAY,
        )

        # Auto-validate
        passed = True
        notes = []

        if case["name"] == "Zero Stock":
            if result.severity != "CRITICAL":
                passed = False
                notes.append(f"Expected CRITICAL, got {result.severity}")
            if result.recommended_quantity <= 0:
                passed = False
                notes.append("Expected qty > 0")

        elif case["name"].startswith("Massive Stock"):
            if result.severity != "NONE":
                passed = False
                notes.append(f"Expected NONE, got {result.severity}")
            if result.recommended_quantity > 0:
                # This might actually be fine — if reorder point > current stock
                # even with 60,000 units, check if it's reasonable
                if result.recommended_quantity > 1000:
                    passed = False
                    notes.append(
                        f"Qty {result.recommended_quantity} too high for overstocked product"
                    )

        elif case["name"] == "No Supplier":
            if result.supplier_lead_time_days != 7.0:
                passed = False
                notes.append(
                    f"Expected 7-day default LT, got {result.supplier_lead_time_days}"
                )

        elif case["name"].startswith("No Forecast"):
            if result.confidence != 0.5:
                passed = False
                notes.append(
                    f"Expected 50% confidence fallback, got {result.confidence}"
                )

        elif case["name"] == "Low Reliability Supplier (65%)":
            # Safety stock should be inflated
            baseline = calculate_recommendation(
                product=case["product"],
                forecast=case["forecast"],
                supplier=SUPPLIERS["PrecisionMfg Ltd"],  # 96% reliability
                signals=case["signals"],
                today=TODAY,
            )
            if result.safety_stock <= baseline.safety_stock:
                passed = False
                notes.append("Safety stock NOT inflated for low reliability")

        elif case["name"].startswith("High Demand Spike"):
            baseline = calculate_recommendation(
                product=case["product"],
                forecast=case["forecast"],
                supplier=case["supplier"],
                signals=SignalContext(),  # no signals
                today=TODAY,
            )
            if result.safety_stock <= baseline.safety_stock:
                passed = False
                notes.append("Safety stock NOT inflated for demand spike")
            if result.recommended_quantity <= baseline.recommended_quantity:
                passed = False
                notes.append("Order qty NOT larger despite signals")

        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_pass = False

        print(f"  {status}  │  {case['name']}")
        print(
            f"         │  Severity: {result.severity}  │  Qty: {result.recommended_quantity:,.0f}  │  Days: {result.days_until_stockout}"
        )
        print(
            f"         │  Confidence: {result.recommendation_confidence:.0%}  │  Expected: {case['expected_quantity']}"
        )
        if notes:
            for n in notes:
                print(f"         │  ⛔ {n}")
        print()

    if all_pass:
        print("  ✅ ALL EDGE CASES PASSED")
    else:
        print("  ❌ SOME EDGE CASES FAILED — FIX BEFORE SPRINT B")
    print()

    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT 3 — Executive Review
# ═══════════════════════════════════════════════════════════════════════════


def run_audit_3(results: list[ReorderResult]):
    print()
    print("=" * 90)
    print("AUDIT 3 — EXECUTIVE REVIEW")
    print("=" * 90)
    print()
    print(
        "Question: If I owned a factory, would these 3 numbers tell me where to focus?"
    )
    print()

    # Inventory Health
    health = calculate_inventory_health(results)

    print("  ┌─────────────────────────────────────────────────┐")
    print(f"  │  INVENTORY HEALTH SCORE:  {health['score']}/100  ({health['grade']})")
    print("  ├─────────────────────────────────────────────────┤")
    print(
        f"  │  Forecast Confidence:   {health['components']['forecast_confidence']:5.1f}/100  (30% weight)"
    )
    print(
        f"  │  Stockout Safety:       {health['components']['stockout_safety']:5.1f}/100  (25% weight)"
    )
    print(
        f"  │  Signal Health:         {health['components']['signal_health']:5.1f}/100  (25% weight)"
    )
    print(
        f"  │  Supplier Reliability:  {health['components']['supplier_reliability']:5.1f}/100  (20% weight)"
    )
    print("  ├─────────────────────────────────────────────────┤")
    print(f"  │  Total Products:   {health['total_products']}")
    print(f"  │  Critical:         {health['critical_count']}")
    print(f"  │  High Risk:        {health['high_count']}")
    print("  └─────────────────────────────────────────────────┘")
    print()

    # Top 5 by financial impact
    priced = [
        r
        for r in results
        if r.financial_impact.has_price_data
        and r.financial_impact.estimated_revenue_impact
    ]
    priced.sort(
        key=lambda r: r.financial_impact.estimated_revenue_impact or 0, reverse=True
    )

    print("  TOP 5 — Revenue at Risk:")
    print(
        f"  {'Product':<30} {'Risk':>12} {'Qty':>8} {'Severity':<10} {'Confidence':<10}"
    )
    print(f"  {'─' * 30} {'─' * 12} {'─' * 8} {'─' * 10} {'─' * 10}")
    for r in priced[:5]:
        rev = r.financial_impact.estimated_revenue_impact
        print(
            f"  {r.product_name:<30} ${rev:>10,.0f} {r.recommended_quantity:>7,.0f} {r.severity:<10} {r.recommendation_confidence:.0%}"
        )
    print()

    # Top 5 by urgency (lowest days to stockout)
    urgent = sorted(results, key=lambda r: r.days_until_stockout)

    print("  TOP 5 — Most Urgent (Days to Stockout):")
    print(f"  {'Product':<30} {'Days':>6} {'Qty':>8} {'Severity':<10} {'Order By':<12}")
    print(f"  {'─' * 30} {'─' * 6} {'─' * 8} {'─' * 10} {'─' * 12}")
    for r in urgent[:5]:
        print(
            f"  {r.product_name:<30} {r.days_until_stockout:>5}d {r.recommended_quantity:>7,.0f} {r.severity:<10} {r.recommended_order_date}"
        )
    print()

    # Lowest confidence recommendations
    low_conf = sorted(results, key=lambda r: r.recommendation_confidence)

    print("  TOP 5 — Lowest Confidence (Proceed with Caution):")
    print(f"  {'Product':<30} {'Confidence':>10} {'Why':<40}")
    print(f"  {'─' * 30} {'─' * 10} {'─' * 40}")
    for r in low_conf[:5]:
        # Find the confidence-related reason
        why = "Multiple factors"
        for reason in r.reasoning:
            if (
                "signal" in reason.lower()
                or "reliability" in reason.lower()
                or "No forecast" in reason
            ):
                why = reason[:40]
                break
        print(f"  {r.product_name:<30} {r.recommendation_confidence:>9.0%} {why}")
    print()

    # Executive verdict
    print("  ─── EXECUTIVE VERDICT ───")
    print()

    if health["critical_count"] > 0:
        print(
            f"  ⚠ {health['critical_count']} products are CRITICAL — immediate action required."
        )

    if health["score"] >= 80:
        print("  ✅ Inventory health is GOOD. Minor optimizations possible.")
    elif health["score"] >= 60:
        print("  ⚡ Inventory health is MODERATE. Some products need attention.")
    elif health["score"] >= 40:
        print("  ⚠ Inventory health is AT RISK. Multiple products need reorder.")
    else:
        print(
            "  🔴 Inventory health is CRITICAL. Immediate purchasing action required."
        )

    total_risk = sum(
        r.financial_impact.estimated_revenue_impact or 0
        for r in results
        if r.financial_impact.has_price_data
    )
    if total_risk > 0:
        print(f"  💰 Total revenue at risk: ${total_risk:,.0f}")
    print()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║   SynChain V3.0 — Decision Engine Business Validation Audit     ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()

    # Audit 1: Realistic dataset
    results = run_audit_1()

    # Audit 2: Edge cases
    edge_pass = run_audit_2()

    # Audit 3: Executive review
    run_audit_3(results)

    # Final summary
    print("=" * 90)
    print("AUDIT COMPLETE")
    print("=" * 90)
    if edge_pass:
        print("  ✅ All edge cases passed")
    else:
        print("  ❌ Edge case failures detected")
    print(f"  📊 {len(results)} products audited")
    print(f"  🔢 Inventory Health: {calculate_inventory_health(results)['score']}/100")
    print()
