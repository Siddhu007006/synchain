"""
TwinManager — CRUD operations and state update logic for Digital Twins.

Responsibilities:
  1. Create, read, list, and delete twins
  2. Initialize warehouse states (W1/W2/W3) on twin creation
  3. Update twin state after each simulation (EWMA + history logging)
  4. Provide state snapshots for the REST API

State Update Flow (after a simulation completes):
  SimulationInput + SimulationResult → update_state_from_simulation()
    ├── update_product_state()    (EWMA on demand, trend detection)
    ├── update_warehouse_state()  (selection count, utilization, risk)
    ├── update_supplier_state()   (EWMA on delay, reliability score)
    └── update_market_state()     (mode tracking, EWMA on confidence/risk)

Every field mutation is logged to twin_state_history.
"""

import json

from digital_twin.math_utils import (
    classify_trend,
    compute_reliability_score,
    compute_selection_rate,
    compute_utilization,
    ewma,
)
from digital_twin.models import (
    DigitalTwin,
    MarketState,
    ProductState,
    SupplierState,
    TwinStateHistory,
    WarehouseState,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

# Static warehouse capacities — must match logistics_agent.py
WAREHOUSE_CONFIG = {
    "W1": {"capacity": 10_000},
    "W2": {"capacity": 15_000},
    "W3": {"capacity": 8_000},
}


class TwinManager:
    """Service layer for Digital Twin CRUD and state management."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_twin(self, name: str = "Default Supply Chain") -> DigitalTwin:
        """Create a new twin with pre-initialized warehouse states."""
        twin = DigitalTwin(name=name)
        self.db.add(twin)
        self.db.flush()  # Get twin.id

        # Initialize warehouse states for W1, W2, W3
        for wh_id in WAREHOUSE_CONFIG:
            self.db.add(WarehouseState(twin_id=twin.id, warehouse_id=wh_id))

        # Initialize aggregate supplier state
        self.db.add(SupplierState(twin_id=twin.id))

        # Initialize global market state
        self.db.add(MarketState(twin_id=twin.id))

        self.db.commit()
        self.db.refresh(twin)
        return twin

    def get_twin(self, twin_id: int) -> DigitalTwin | None:
        """Get a twin by ID with all relationships loaded."""
        return self.db.get(DigitalTwin, twin_id)

    def list_twins(self) -> list[DigitalTwin]:
        """List all twins ordered by creation date."""
        stmt = select(DigitalTwin).order_by(DigitalTwin.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def delete_twin(self, twin_id: int) -> bool:
        """Delete a twin and all related state (cascade)."""
        twin = self.get_twin(twin_id)
        if not twin:
            return False
        self.db.delete(twin)
        self.db.commit()
        return True

    def get_history(
        self, twin_id: int, limit: int = 100, offset: int = 0
    ) -> list[TwinStateHistory]:
        """Get state change history for a twin, newest first."""
        stmt = (
            select(TwinStateHistory)
            .where(TwinStateHistory.twin_id == twin_id)
            .order_by(TwinStateHistory.changed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def count_history(self, twin_id: int) -> int:
        """Count total history entries for a twin."""
        stmt = select(TwinStateHistory).where(TwinStateHistory.twin_id == twin_id)
        return len(list(self.db.scalars(stmt).all()))

    # ------------------------------------------------------------------
    # State update (called after each simulation)
    # ------------------------------------------------------------------

    def update_state_from_simulation(
        self,
        twin_id: int,
        sim_input: dict,
        sim_result: dict,
    ) -> DigitalTwin | None:
        """
        Update all twin state domains after a simulation completes.

        Args:
            twin_id:    ID of the twin to update
            sim_input:  Dict from SimulationInput (product, stock, demand, etc.)
            sim_result: Dict from SimulationResult (demand_forecast, risk, etc.)

        Returns:
            Updated DigitalTwin or None if twin not found.
        """
        twin = self.get_twin(twin_id)
        if not twin:
            return None

        # Increment simulation count
        twin.simulation_count += 1

        # Update each state domain
        self._update_product_state(twin, sim_input, sim_result)
        self._update_warehouse_state(twin, sim_result)
        self._update_supplier_state(twin, sim_input)
        self._update_market_state(twin, sim_input, sim_result)

        # Phase E3: Signal detection (after state updated, before commit)
        try:
            from signals.engine import SignalEngine

            signal_engine = SignalEngine(self.db)
            signal_engine.evaluate(twin)
        except Exception:
            import logging

            logging.getLogger("synchain.signals").exception(
                "Signal evaluation failed for twin %d (non-blocking)",
                twin_id,
            )

        self.db.commit()
        self.db.refresh(twin)
        return twin

    # ------------------------------------------------------------------
    # Private state update methods
    # ------------------------------------------------------------------

    def _update_product_state(
        self, twin: DigitalTwin, sim_input: dict, sim_result: dict
    ) -> None:
        """Update or create product state using EWMA demand smoothing."""
        product_name = sim_input.get("product", "Unknown")
        demand = sim_input.get("demand", 0.0)
        stock = sim_input.get("stock", 0.0)

        # Find or create product state
        product_state = None
        for ps in twin.product_states:
            if ps.product_name == product_name:
                product_state = ps
                break

        if not product_state:
            product_state = ProductState(
                twin_id=twin.id,
                product_name=product_name,
            )
            self.db.add(product_state)
            self.db.flush()

        # Log and update fields
        old_avg = product_state.avg_demand
        new_avg = ewma(demand, old_avg)

        self._log_change(
            twin.id,
            "product",
            product_name,
            "latest_stock",
            product_state.latest_stock,
            stock,
        )
        self._log_change(
            twin.id,
            "product",
            product_name,
            "latest_demand",
            product_state.latest_demand,
            demand,
        )
        self._log_change(
            twin.id, "product", product_name, "avg_demand", old_avg, new_avg
        )

        old_trend = product_state.demand_trend
        new_trend = classify_trend(demand, new_avg)
        if old_trend != new_trend:
            self._log_change(
                twin.id, "product", product_name, "demand_trend", old_trend, new_trend
            )

        product_state.latest_stock = stock
        product_state.latest_demand = demand
        product_state.avg_demand = new_avg
        product_state.demand_trend = new_trend
        product_state.simulation_count += 1

    def _update_warehouse_state(self, twin: DigitalTwin, sim_result: dict) -> None:
        """Update warehouse selection stats and utilization."""
        selected_wh = sim_result.get("selected_warehouse", "")
        demand_forecast = sim_result.get("demand_forecast", 0.0)

        # Map risk to numeric score for avg_risk_score tracking
        risk_map = {"Low": 0.2, "Medium": 0.5, "High": 0.8}
        risk_score = risk_map.get(sim_result.get("risk", "Medium"), 0.5)

        for ws in twin.warehouse_states:
            if ws.warehouse_id == selected_wh:
                old_selected = ws.times_selected
                ws.times_selected += 1
                self._log_change(
                    twin.id,
                    "warehouse",
                    ws.warehouse_id,
                    "times_selected",
                    old_selected,
                    ws.times_selected,
                )

                # Update utilization based on demand vs capacity
                capacity = WAREHOUSE_CONFIG.get(ws.warehouse_id, {}).get(
                    "capacity", 10000
                )
                old_util = ws.utilization_pct
                new_util = compute_utilization(demand_forecast, capacity)
                ws.utilization_pct = new_util
                self._log_change(
                    twin.id,
                    "warehouse",
                    ws.warehouse_id,
                    "utilization_pct",
                    old_util,
                    new_util,
                )

                # EWMA on risk score for this warehouse
                old_risk = ws.avg_risk_score
                ws.avg_risk_score = ewma(risk_score, old_risk)
                self._log_change(
                    twin.id,
                    "warehouse",
                    ws.warehouse_id,
                    "avg_risk_score",
                    old_risk,
                    ws.avg_risk_score,
                )

            # Update selection rate for all warehouses
            old_rate = ws.selection_rate
            ws.selection_rate = compute_selection_rate(
                ws.times_selected, twin.simulation_count
            )
            if old_rate != ws.selection_rate:
                self._log_change(
                    twin.id,
                    "warehouse",
                    ws.warehouse_id,
                    "selection_rate",
                    old_rate,
                    ws.selection_rate,
                )

    def _update_supplier_state(self, twin: DigitalTwin, sim_input: dict) -> None:
        """Update aggregate supplier reliability metrics."""
        delay = sim_input.get("supplier_delay", 0.0)
        supply_status = sim_input.get("supply_status", "Medium")

        ss = twin.supplier_state
        if not ss:
            return

        # EWMA on delay
        old_delay = ss.avg_delay
        ss.avg_delay = ewma(delay, old_delay)
        self._log_change(
            twin.id, "supplier", "aggregate", "avg_delay", old_delay, ss.avg_delay
        )

        # Track max delay
        if delay > ss.max_delay_seen:
            old_max = ss.max_delay_seen
            ss.max_delay_seen = delay
            self._log_change(
                twin.id, "supplier", "aggregate", "max_delay_seen", old_max, delay
            )

        # Recompute reliability
        old_reliability = ss.reliability_score
        ss.reliability_score = compute_reliability_score(
            ss.avg_delay, ss.max_delay_seen
        )
        if old_reliability != ss.reliability_score:
            self._log_change(
                twin.id,
                "supplier",
                "aggregate",
                "reliability_score",
                old_reliability,
                ss.reliability_score,
            )

        # Track supply status mode (most common)
        ss.supply_status_mode = supply_status  # simplified: latest wins for V1

    def _update_market_state(
        self, twin: DigitalTwin, sim_input: dict, sim_result: dict
    ) -> None:
        """Update global market condition trends."""
        market_trend = sim_input.get("market_trend", "Neutral")
        season = sim_input.get("season", "Normal")
        confidence = sim_result.get("overall_confidence", 0.0)

        # Map risk to numeric for EWMA
        risk_map = {"Low": 0.2, "Medium": 0.5, "High": 0.8}
        risk_score = risk_map.get(sim_result.get("risk", "Medium"), 0.5)

        ms = twin.market_state
        if not ms:
            return

        # Track trend mode (latest value — V1 simplification)
        if ms.trend_mode != market_trend:
            self._log_change(
                twin.id, "market", "global", "trend_mode", ms.trend_mode, market_trend
            )
            ms.trend_mode = market_trend

        if ms.season_mode != season:
            self._log_change(
                twin.id, "market", "global", "season_mode", ms.season_mode, season
            )
            ms.season_mode = season

        # EWMA on confidence
        old_conf = ms.avg_confidence
        ms.avg_confidence = ewma(confidence, old_conf)
        self._log_change(
            twin.id, "market", "global", "avg_confidence", old_conf, ms.avg_confidence
        )

        # EWMA on risk
        old_risk = ms.avg_risk_score
        ms.avg_risk_score = ewma(risk_score, old_risk)
        self._log_change(
            twin.id, "market", "global", "avg_risk_score", old_risk, ms.avg_risk_score
        )

    # ------------------------------------------------------------------
    # History logging
    # ------------------------------------------------------------------

    def _log_change(
        self,
        twin_id: int,
        entity_type: str,
        entity_id: str,
        field_name: str,
        old_value,
        new_value,
    ) -> None:
        """Record a state mutation to twin_state_history."""
        entry = TwinStateHistory(
            twin_id=twin_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=json.dumps(old_value) if old_value is not None else None,
            new_value=json.dumps(new_value),
        )
        self.db.add(entry)
