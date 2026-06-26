"""
Compound signal detection — pattern matching on co-occurring atomic signals.

Compound signals detect emergent patterns where multiple atomic signals
co-occur, representing a qualitatively different, more severe situation
than any individual signal.

Architecture:
  - CompoundRule: Declarative rule definition (dataclass)
  - CompoundDetector: Evaluates rules against recently emitted atomic signals
  - Severity functions: max, avg, max_boosted

Design Decisions (from E6 Architecture Report):
  D1: Declarative rules (data structures, not detector classes)
  D2: Three severity functions (max, avg, max_boosted)
  D3: Minimum trigger severity gate per rule
  D4: Stored in existing signal_events table (signal_type="compound")
  D6: Additive Penalty Stacking — compound penalties add on top of atomic
      penalties. This is intentional: correlated failures are worse than
      the sum of individual failures. The confidence floor (0.10) prevents
      unbounded degradation.
      Post-E6 Business Logic Audit will validate penalty calibration.

Compound Rules:
  - SupplyShock:       DemandSpike + SupplierDegradation
  - FulfillmentCrisis: WarehouseOverload + DemandSpike
  - MarketDisruption:  TrendShift + SupplierDegradation
  - PerfectStorm:      WeatherAlert + SupplierDegradation + DemandSpike (3-trigger)
  - CostSqueeze:       CommodityShock + EconomicShift
"""

import logging
from dataclasses import dataclass

from signals.detectors import SignalOutput

logger = logging.getLogger("synchain.compound")


# ---------------------------------------------------------------------------
# Severity aggregation functions
# ---------------------------------------------------------------------------


def severity_max(severities: list[float], boost: float = 1.0) -> float:
    """Return max severity from triggers."""
    if not severities:
        return 0.0
    return round(min(1.0, max(severities)), 4)


def severity_avg(severities: list[float], boost: float = 1.0) -> float:
    """Return average severity from triggers."""
    if not severities:
        return 0.0
    return round(min(1.0, sum(severities) / len(severities)), 4)


def severity_max_boosted(severities: list[float], boost: float = 1.2) -> float:
    """
    Return max severity × boost factor, capped at 1.0.

    The boost represents the insight that co-occurring problems are
    worse than isolated ones.
    """
    if not severities:
        return 0.0
    return round(min(1.0, max(severities) * boost), 4)


_SEVERITY_FNS = {
    "max": severity_max,
    "avg": severity_avg,
    "max_boosted": severity_max_boosted,
}


# ---------------------------------------------------------------------------
# CompoundRule — declarative rule definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompoundRule:
    """
    Declarative compound signal rule.

    A rule fires when ALL trigger sources are present in the current
    evaluation's atomic signals, each with severity >= min_trigger_severity.
    """

    name: str
    triggers: tuple[str, ...]
    output_source: str
    severity_fn: str  # "max" | "avg" | "max_boosted"
    severity_boost: float = 1.0  # only used by max_boosted
    min_trigger_severity: float = 0.3
    confidence_weight: float = 0.0
    can_elevate_risk: bool = False
    description: str = ""

    def matches(self, atomic_signals: dict[str, float]) -> bool:
        """
        Check if all triggers are present with sufficient severity.

        Args:
            atomic_signals: dict mapping source name → severity
                            for signals from the current evaluation.

        Returns:
            True if all triggers are present with severity >= min_trigger_severity.
        """
        for trigger in self.triggers:
            severity = atomic_signals.get(trigger, 0.0)
            if severity < self.min_trigger_severity:
                return False
        return True

    def compute_severity(self, atomic_signals: dict[str, float]) -> float:
        """
        Compute compound severity from matching trigger severities.

        Uses the configured severity function (max, avg, max_boosted).
        """
        trigger_severities = [
            atomic_signals[t] for t in self.triggers if t in atomic_signals
        ]

        fn = _SEVERITY_FNS.get(self.severity_fn, severity_max)
        return fn(trigger_severities, self.severity_boost)


# ---------------------------------------------------------------------------
# Rule Registry — all compound rules
# ---------------------------------------------------------------------------

COMPOUND_RULES: tuple[CompoundRule, ...] = (
    CompoundRule(
        name="SupplyShock",
        triggers=("DemandSpike", "SupplierDegradation"),
        output_source="SupplyShock",
        severity_fn="max",
        min_trigger_severity=0.3,
        confidence_weight=0.12,
        can_elevate_risk=True,
        description="Demand exceeds supply capacity — supplier can't keep up with demand growth",
    ),
    CompoundRule(
        name="FulfillmentCrisis",
        triggers=("WarehouseOverload", "DemandSpike"),
        output_source="FulfillmentCrisis",
        severity_fn="max_boosted",
        severity_boost=1.2,
        min_trigger_severity=0.3,
        confidence_weight=0.10,
        can_elevate_risk=True,
        description="Warehouses cannot absorb demand — operational bottleneck",
    ),
    CompoundRule(
        name="MarketDisruption",
        triggers=("TrendShift", "SupplierDegradation"),
        output_source="MarketDisruption",
        severity_fn="max",
        min_trigger_severity=0.3,
        confidence_weight=0.08,
        can_elevate_risk=False,
        description="Market volatility + unreliable supply — strategic uncertainty",
    ),
    CompoundRule(
        name="PerfectStorm",
        triggers=("WeatherAlert", "SupplierDegradation", "DemandSpike"),
        output_source="PerfectStorm",
        severity_fn="max_boosted",
        severity_boost=1.3,
        min_trigger_severity=0.4,
        confidence_weight=0.15,
        can_elevate_risk=True,
        description="Triple threat: physical disruption + supply failure + demand surge",
    ),
    CompoundRule(
        name="CostSqueeze",
        triggers=("CommodityShock", "EconomicShift"),
        output_source="CostSqueeze",
        severity_fn="avg",
        min_trigger_severity=0.3,
        confidence_weight=0.06,
        can_elevate_risk=False,
        description="Rising costs + economic pressure — margin erosion",
    ),
)


# ---------------------------------------------------------------------------
# CompoundDetector — evaluates rules against atomic signals
# ---------------------------------------------------------------------------


class CompoundDetector:
    """
    Evaluates compound rules against atomic signals from the current evaluation.

    Called by SignalEngine after atomic detectors have run and their signals
    have been collected (but before commit).

    Usage:
        detector = CompoundDetector()
        compounds = detector.evaluate(atomic_outputs)
    """

    def evaluate(self, atomic_outputs: list[SignalOutput]) -> list[SignalOutput]:
        """
        Evaluate all compound rules against atomic signal outputs.

        Args:
            atomic_outputs: List of SignalOutput from atomic detectors
                           in the current evaluation cycle.

        Returns:
            List of SignalOutput for compound signals that fired.
        """
        if not atomic_outputs:
            return []

        # Build source → severity map (take max severity if multiple signals
        # from same source, e.g., multiple DemandSpike for different products)
        atomic_map: dict[str, float] = {}
        for output in atomic_outputs:
            existing = atomic_map.get(output.source, 0.0)
            atomic_map[output.source] = max(existing, output.severity)

        compounds: list[SignalOutput] = []

        for rule in COMPOUND_RULES:
            if rule.matches(atomic_map):
                severity = rule.compute_severity(atomic_map)

                # Build trigger detail for payload
                trigger_severities = {
                    t: round(atomic_map.get(t, 0.0), 4) for t in rule.triggers
                }

                compounds.append(
                    SignalOutput(
                        source=rule.output_source,
                        signal_type="compound",
                        severity=severity,
                        payload={
                            "triggers": list(rule.triggers),
                            "trigger_severities": trigger_severities,
                            "severity_fn": rule.severity_fn,
                            "severity_boost": rule.severity_boost,
                            "description": rule.description,
                        },
                    )
                )

                logger.info(
                    "Compound signal %s fired (severity %.4f) from triggers %s",
                    rule.output_source,
                    severity,
                    trigger_severities,
                )

        return compounds
