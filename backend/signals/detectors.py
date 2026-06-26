"""
Signal detectors — pattern recognition on Digital Twin state.

Each detector:
  1. Inherits from SignalDetector (ABC)
  2. Reads twin state (never writes)
  3. Returns 0+ SignalOutput instances
  4. Has a documented severity formula

Detectors:
  - DemandSpikeDetector:          latest_demand > avg × 1.25
  - SupplierDegradationDetector:  reliability_score < 60.0
  - WarehouseOverloadDetector:    utilization_pct > 0.85
  - TrendShiftDetector:           demand_trend changed in last simulation
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from digital_twin.models import DigitalTwin, TwinStateHistory
from sqlalchemy import select
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Output container
# ---------------------------------------------------------------------------


@dataclass
class SignalOutput:
    """Output from a detector — maps 1:1 to a SignalEvent row."""

    source: str  # Detector name (e.g. 'DemandSpike')
    signal_type: str  # demand | supply | risk | market
    severity: float  # 0.0–1.0
    payload: dict  # Structured context


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class SignalDetector(ABC):
    """Abstract base for all signal detectors."""

    @property
    @abstractmethod
    def source(self) -> str:
        """Unique detector identifier."""

    @property
    @abstractmethod
    def signal_type(self) -> str:
        """Signal category: demand | supply | risk | market."""

    @abstractmethod
    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        """Evaluate twin state and return 0+ signals."""


# ---------------------------------------------------------------------------
# DemandSpikeDetector
# ---------------------------------------------------------------------------

DEMAND_SPIKE_THRESHOLD = 1.25  # latest > avg × 1.25 triggers


class DemandSpikeDetector(SignalDetector):
    """
    Detects demand spikes per product.

    Condition: latest_demand > avg_demand × 1.25
    Severity:  min(1.0, (latest_demand / avg_demand) - 1.0)
               e.g. 50% above average → severity 0.5
    """

    @property
    def source(self) -> str:
        return "DemandSpike"

    @property
    def signal_type(self) -> str:
        return "demand"

    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        signals = []
        for ps in twin.product_states:
            if ps.avg_demand <= 0:
                continue

            spike_ratio = ps.latest_demand / ps.avg_demand
            if spike_ratio > DEMAND_SPIKE_THRESHOLD:
                severity = min(1.0, round(spike_ratio - 1.0, 4))
                signals.append(
                    SignalOutput(
                        source=self.source,
                        signal_type=self.signal_type,
                        severity=severity,
                        payload={
                            "product": ps.product_name,
                            "latest_demand": ps.latest_demand,
                            "avg_demand": ps.avg_demand,
                            "spike_ratio": round(spike_ratio, 4),
                        },
                    )
                )
        return signals


# ---------------------------------------------------------------------------
# SupplierDegradationDetector
# ---------------------------------------------------------------------------

SUPPLIER_DEGRADATION_THRESHOLD = 60.0  # reliability < 60 triggers


class SupplierDegradationDetector(SignalDetector):
    """
    Detects supplier reliability degradation.

    Condition: reliability_score < 60.0
    Severity:  min(1.0, (60.0 - reliability_score) / 60.0)
               e.g. score 30 → severity 0.5
    """

    @property
    def source(self) -> str:
        return "SupplierDegradation"

    @property
    def signal_type(self) -> str:
        return "supply"

    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        ss = twin.supplier_state
        if not ss:
            return []

        if ss.reliability_score >= SUPPLIER_DEGRADATION_THRESHOLD:
            return []

        severity = min(
            1.0,
            round(
                (SUPPLIER_DEGRADATION_THRESHOLD - ss.reliability_score)
                / SUPPLIER_DEGRADATION_THRESHOLD,
                4,
            ),
        )
        return [
            SignalOutput(
                source=self.source,
                signal_type=self.signal_type,
                severity=severity,
                payload={
                    "reliability_score": ss.reliability_score,
                    "avg_delay": ss.avg_delay,
                    "max_delay_seen": ss.max_delay_seen,
                    "supply_status_mode": ss.supply_status_mode,
                },
            )
        ]


# ---------------------------------------------------------------------------
# WarehouseOverloadDetector
# ---------------------------------------------------------------------------

WAREHOUSE_OVERLOAD_THRESHOLD = 0.85  # utilization > 85% triggers


class WarehouseOverloadDetector(SignalDetector):
    """
    Detects warehouse over-utilization.

    Condition: utilization_pct > 0.85
    Severity:  min(1.0, (utilization - 0.85) / 0.15)
               e.g. utilization 0.92 → severity 0.47
    """

    @property
    def source(self) -> str:
        return "WarehouseOverload"

    @property
    def signal_type(self) -> str:
        return "risk"

    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        signals = []
        for ws in twin.warehouse_states:
            if ws.utilization_pct > WAREHOUSE_OVERLOAD_THRESHOLD:
                severity = min(
                    1.0,
                    round(
                        (ws.utilization_pct - WAREHOUSE_OVERLOAD_THRESHOLD)
                        / (1.0 - WAREHOUSE_OVERLOAD_THRESHOLD),
                        4,
                    ),
                )
                signals.append(
                    SignalOutput(
                        source=self.source,
                        signal_type=self.signal_type,
                        severity=severity,
                        payload={
                            "warehouse_id": ws.warehouse_id,
                            "utilization_pct": ws.utilization_pct,
                            "times_selected": ws.times_selected,
                            "capacity_threshold": WAREHOUSE_OVERLOAD_THRESHOLD,
                        },
                    )
                )
        return signals


# ---------------------------------------------------------------------------
# TrendShiftDetector
# ---------------------------------------------------------------------------

# Severity map: (old_trend, new_trend) → severity
_SHIFT_SEVERITY = {
    ("Stable", "Rising"): 0.3,
    ("Stable", "Falling"): 0.3,
    ("Rising", "Stable"): 0.2,
    ("Falling", "Stable"): 0.2,
    ("Rising", "Falling"): 0.8,
    ("Falling", "Rising"): 0.8,
}

# Shift type classification
_SHIFT_TYPE = {
    ("Stable", "Rising"): "acceleration",
    ("Stable", "Falling"): "deceleration",
    ("Rising", "Stable"): "deceleration",
    ("Falling", "Stable"): "acceleration",
    ("Rising", "Falling"): "reversal",
    ("Falling", "Rising"): "reversal",
}


class TrendShiftDetector(SignalDetector):
    """
    Detects demand trend shifts by reading twin_state_history.

    Condition: A demand_trend field change exists in the most recent history
    Severity:  Depends on shift direction:
               Stable↔Rising/Falling: 0.2–0.3
               Rising↔Falling (reversal): 0.8
    """

    @property
    def source(self) -> str:
        return "TrendShift"

    @property
    def signal_type(self) -> str:
        return "market"

    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        # Find the most recent demand_trend change per product
        stmt = (
            select(TwinStateHistory)
            .where(
                TwinStateHistory.twin_id == twin.id,
                TwinStateHistory.entity_type == "product",
                TwinStateHistory.field_name == "demand_trend",
            )
            .order_by(TwinStateHistory.changed_at.desc(), TwinStateHistory.id.desc())
        )
        recent_changes = list(db.scalars(stmt).all())

        if not recent_changes:
            return []

        # Group by entity_id (product name) — take only the latest per product
        seen_products: set[str] = set()
        signals = []

        for change in recent_changes:
            if change.entity_id in seen_products:
                continue
            seen_products.add(change.entity_id)

            old_trend = json.loads(change.old_value) if change.old_value else None
            new_trend = json.loads(change.new_value) if change.new_value else None

            if not old_trend or not new_trend or old_trend == new_trend:
                continue

            shift_key = (old_trend, new_trend)
            severity = _SHIFT_SEVERITY.get(shift_key, 0.3)
            shift_type = _SHIFT_TYPE.get(shift_key, "unknown")

            signals.append(
                SignalOutput(
                    source=self.source,
                    signal_type=self.signal_type,
                    severity=severity,
                    payload={
                        "product": change.entity_id,
                        "old_trend": old_trend,
                        "new_trend": new_trend,
                        "shift_type": shift_type,
                    },
                )
            )

        return signals


# ---------------------------------------------------------------------------
# Registry — all detectors in evaluation order
# ---------------------------------------------------------------------------

# Phase E3: Internal detectors (evaluate twin state)
_INTERNAL_DETECTORS: list[type[SignalDetector]] = [
    DemandSpikeDetector,
    SupplierDegradationDetector,
    WarehouseOverloadDetector,
    TrendShiftDetector,
]

# Phase E5: External detectors (evaluate cached external data)
try:
    from signals.external_detectors import EXTERNAL_DETECTORS

    _EXTERNAL_DETECTORS: list[type[SignalDetector]] = EXTERNAL_DETECTORS
except ImportError:
    _EXTERNAL_DETECTORS = []

ALL_DETECTORS: list[type[SignalDetector]] = _INTERNAL_DETECTORS + _EXTERNAL_DETECTORS
