"""
SignalEngine — orchestrates signal detection across all detectors.

Responsibilities:
  1. Instantiate and run all registered detectors (E3+E5 atomic)
  2. Evaluate compound rules against atomic outputs (E6)
  3. Persist emitted signals as SignalEvent rows
  4. Isolate detector failures (log + skip, never fail the simulation)
  5. Provide query methods for signal retrieval and summarization

Evaluation order:
  Phase 1: Atomic detectors (E3 internal + E5 external) → atomic SignalEvents
  Phase 2: CompoundDetector (E6) → compound SignalEvents

Health Score Formula (approved):
  health_score = 1.0 - weighted_avg_severity(last_10_signals)
  Weight = position-based recency: newest signal gets weight 10, oldest gets 1.
  If no signals exist, health_score = 1.0 (healthy).
"""

import json
import logging

from digital_twin.models import DigitalTwin, SignalEvent
from signals.detectors import ALL_DETECTORS, SignalOutput
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.signals")


class SignalEngine:
    """Runs all detectors against a twin and persists results."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, twin: DigitalTwin) -> list[SignalEvent]:
        """
        Run all detectors against twin state, persist emitted signals.

        Evaluation order:
          1. Atomic detectors (E3+E5) — produce atomic SignalEvents
          2. CompoundDetector (E6) — pattern-match on atomic outputs

        Returns list of ALL persisted SignalEvent objects (atomic + compound).
        Called after TwinManager state updates, before commit.
        """
        all_events: list[SignalEvent] = []
        atomic_outputs: list[SignalOutput] = []

        # Phase 1: Atomic detectors
        for detector_cls in ALL_DETECTORS:
            try:
                detector = detector_cls()
                outputs = detector.evaluate(twin, self.db)

                for output in outputs:
                    atomic_outputs.append(output)
                    event = SignalEvent(
                        twin_id=twin.id,
                        source=output.source,
                        signal_type=output.signal_type,
                        severity=output.severity,
                        payload=json.dumps(output.payload),
                    )
                    self.db.add(event)
                    all_events.append(event)

            except Exception:
                logger.exception(
                    "Detector %s failed for twin %d (non-blocking)",
                    detector_cls.__name__,
                    twin.id,
                )

        # Phase 2: Compound detection (E6)
        try:
            from signals.compound import CompoundDetector

            compound_detector = CompoundDetector()
            compound_outputs = compound_detector.evaluate(atomic_outputs)

            for output in compound_outputs:
                event = SignalEvent(
                    twin_id=twin.id,
                    source=output.source,
                    signal_type=output.signal_type,
                    severity=output.severity,
                    payload=json.dumps(output.payload),
                )
                self.db.add(event)
                all_events.append(event)

        except Exception:
            logger.exception(
                "Compound detection failed for twin %d (non-blocking)",
                twin.id,
            )

        return all_events

    def list_signals(
        self,
        twin_id: int,
        signal_type: str | None = None,
        min_severity: float | None = None,
        limit: int = 50,
    ) -> list[SignalEvent]:
        """Query persisted signals with optional filtering."""
        stmt = (
            select(SignalEvent)
            .where(SignalEvent.twin_id == twin_id)
            .order_by(SignalEvent.created_at.desc())
        )

        if signal_type:
            stmt = stmt.where(SignalEvent.signal_type == signal_type)
        if min_severity is not None:
            stmt = stmt.where(SignalEvent.severity >= min_severity)

        stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_summary(self, twin_id: int) -> dict:
        """
        Compute signal summary with health score.

        Health score = 1.0 - weighted_avg_severity(last 10 signals)
        Weight = position-based: newest=10, ..., oldest=1.
        """
        # Get all signals for counts
        all_signals = self.list_signals(twin_id, limit=1000)

        # Counts by type
        by_type: dict[str, int] = {}
        for s in all_signals:
            by_type[s.signal_type] = by_type.get(s.signal_type, 0) + 1

        # Counts by severity label
        by_severity: dict[str, int] = {"info": 0, "warning": 0, "critical": 0}
        for s in all_signals:
            label = _severity_label(s.severity)
            by_severity[label] += 1

        # Latest critical signal
        latest_critical = None
        for s in all_signals:
            if s.severity >= 0.7:
                latest_critical = s
                break

        # Health score: recency-weighted average of last 10 signals
        recent_10 = all_signals[:10]
        health_score = _compute_health_score(recent_10)

        return {
            "total_signals": len(all_signals),
            "by_type": by_type,
            "by_severity": by_severity,
            "latest_critical": latest_critical,
            "health_score": health_score,
        }

    def get_active_signals_for_product(
        self,
        twin_id: int,
        product: str,
        limit: int = 10,
    ) -> list[SignalEvent]:
        """
        Get recent signals relevant to a specific product.

        Includes:
          - demand signals matching the product
          - supply/risk/market signals (twin-wide, relevant to all products)
        """
        all_recent = self.list_signals(twin_id, limit=limit * 3)

        relevant = []
        for s in all_recent:
            if len(relevant) >= limit:
                break

            payload = _parse_payload(s.payload)

            # Demand signals: filter to matching product
            if s.signal_type == "demand":
                if payload.get("product") == product:
                    relevant.append(s)
            # Market signals: filter to matching product (trend shifts)
            elif s.signal_type == "market":
                if payload.get("product") == product:
                    relevant.append(s)
            else:
                # Supply and risk signals are twin-wide
                relevant.append(s)

        return relevant


def _severity_label(severity: float) -> str:
    """Classify severity into human-readable label."""
    if severity >= 0.7:
        return "critical"
    elif severity >= 0.3:
        return "warning"
    return "info"


def _compute_health_score(recent_signals: list[SignalEvent]) -> float:
    """
    Compute health score from recent signals.

    Formula: 1.0 - weighted_average(severities)
    Weight = position index (newest=N, oldest=1).
    No signals = 1.0 (perfectly healthy).
    """
    if not recent_signals:
        return 1.0

    n = len(recent_signals)
    total_weight = 0.0
    weighted_severity = 0.0

    for i, signal in enumerate(recent_signals):
        weight = n - i  # newest gets highest weight
        weighted_severity += signal.severity * weight
        total_weight += weight

    if total_weight <= 0:
        return 1.0

    avg_severity = weighted_severity / total_weight
    return round(max(0.0, min(1.0, 1.0 - avg_severity)), 4)


def _parse_payload(payload_str: str) -> dict:
    """Safely parse a JSON payload string."""
    try:
        return json.loads(payload_str)
    except (json.JSONDecodeError, TypeError):
        return {}
