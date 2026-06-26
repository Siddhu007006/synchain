"""
LogisticsAgent — Cost-based warehouse selection and route mapping.

Upgrade from L2 (binary if/else) to L2+ (cost-optimized multi-warehouse).

Warehouse Selection Logic (documented):
─────────────────────────────────
  WAREHOUSES = {
    "W1": { route: "R1", cost_factor: 1.0, capacity: 10000 },
    "W2": { route: "R4", cost_factor: 1.2, capacity: 15000 },
    "W3": { route: "R7", cost_factor: 0.9, capacity:  8000 },
  }

  For each warehouse:
    score = capacity_fit_score × 0.6 + cost_score × 0.4

  capacity_fit_score:
    capacity >= predicted_demand → 1.0
    capacity >= predicted_demand × 0.8 → 0.7
    capacity < predicted_demand × 0.8 → 0.3

  cost_score:
    Inverse of cost_factor normalized: lower cost → higher score
    cost_score = 1.0 - (cost_factor - min_cost) / (max_cost - min_cost + 0.01)

  Select warehouse with highest combined score.
  If stock >= predicted_demand, prefer current warehouse (bonus +0.15).

Confidence Formula (documented):
─────────────────────────────────
  C_logistics = 0.50 (base)
              + decisiveness  (0.00–0.30)
              + route_validity (0.10)
              + margin        (0.00–0.10)

  decisiveness:
    score_gap (best - second) > 0.3 → 0.30  (clear winner)
    score_gap > 0.15                → 0.20
    score_gap > 0.05                → 0.10
    Otherwise                       → 0.00  (too close to call)

  route_validity:
    Selected warehouse in route map → 0.10

  margin:
    best_score > 0.8 → 0.10  (strong fit overall)
    best_score > 0.6 → 0.05
    Otherwise        → 0.00
─────────────────────────────────
"""

from agents.base_agent import AgentStepResult, BaseAgent

# --- Warehouse network (source of truth) ---
# Three distinct fulfillment strategies:
#   W1 — Standard:  balanced capacity/cost, default hub
#   W2 — Premium:   highest capacity (15k), higher cost (1.2×)
#   W3 — Budget:    smallest capacity (8k), lowest cost (0.9×)
#
# cost_factor is relative to W1. Lower = cheaper per-unit fulfillment.
WAREHOUSES = {
    "W1": {"route": "R1", "cost_factor": 1.0, "capacity": 10000},
    "W2": {"route": "R4", "cost_factor": 1.2, "capacity": 15000},
    "W3": {"route": "R7", "cost_factor": 0.9, "capacity": 8000},
}


class LogisticsAgent(BaseAgent):
    """Cost-optimized warehouse selection with W1/W2/W3 support."""

    @property
    def name(self) -> str:
        return "LogisticsAgent"

    def run(
        self,
        warehouse: str,
        stock: float,
        predicted_demand: float,
    ) -> AgentStepResult:
        input_summary = {
            "current_warehouse": warehouse,
            "stock": stock,
            "predicted_demand": predicted_demand,
        }

        def _compute(warehouse, stock, predicted_demand):
            cost_factors = [w["cost_factor"] for w in WAREHOUSES.values()]
            min_cost = min(cost_factors)
            max_cost = max(cost_factors)
            cost_range = max_cost - min_cost + 0.01

            scores = {}
            for wh_id, wh_data in WAREHOUSES.items():
                # Capacity fit
                cap = wh_data["capacity"]
                if cap >= predicted_demand:
                    cap_score = 1.0
                elif cap >= predicted_demand * 0.8:
                    cap_score = 0.7
                else:
                    cap_score = 0.3

                # Cost (lower = better)
                cost_score = 1.0 - (wh_data["cost_factor"] - min_cost) / cost_range

                # Combined
                combined = (cap_score * 0.6) + (cost_score * 0.4)

                # Home warehouse bonus
                if wh_id == warehouse and stock >= predicted_demand:
                    combined += 0.15

                scores[wh_id] = round(combined, 3)

            # Select best
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            best_wh = ranked[0][0]
            best_score = ranked[0][1]
            second_score = ranked[1][1] if len(ranked) > 1 else 0.0
            route = WAREHOUSES[best_wh]["route"]

            return best_wh, route, scores, best_score, second_score

        (selected_warehouse, route, scores, best_score, second_score), elapsed_ms = (
            self._timed_execute(
                _compute,
                warehouse=warehouse,
                stock=stock,
                predicted_demand=predicted_demand,
            )
        )

        # --- Confidence formula ---
        base_confidence = 0.50

        score_gap = best_score - second_score
        if score_gap > 0.3:
            decisiveness = 0.30
        elif score_gap > 0.15:
            decisiveness = 0.20
        elif score_gap > 0.05:
            decisiveness = 0.10
        else:
            decisiveness = 0.00

        route_validity = 0.10 if selected_warehouse in WAREHOUSES else 0.00

        if best_score > 0.8:
            margin = 0.10
        elif best_score > 0.6:
            margin = 0.05
        else:
            margin = 0.00

        confidence = round(
            min(base_confidence + decisiveness + route_validity + margin, 1.0), 2
        )

        # --- Explanation ---
        scores_str = ", ".join(f"{k}={v:.2f}" for k, v in sorted(scores.items()))
        capacity_info = f"capacity {WAREHOUSES[selected_warehouse]['capacity']:,}"
        cost_info = f"cost factor {WAREHOUSES[selected_warehouse]['cost_factor']}"

        explanation = (
            f"Selected {selected_warehouse} via route {route} "
            f"({capacity_info}, {cost_info}). "
            f"Warehouse scores: [{scores_str}]. "
            f"Confidence {confidence:.0%}: "
            f"{'clear winner' if decisiveness >= 0.30 else 'moderate margin' if decisiveness >= 0.10 else 'close competition'} "
            f"(gap {score_gap:.2f})."
        )

        return AgentStepResult(
            agent_name=self.name,
            input_summary=input_summary,
            output_data={
                "selected_warehouse": selected_warehouse,
                "route": route,
                "warehouse_scores": scores,
            },
            confidence=confidence,
            explanation=explanation,
            execution_ms=elapsed_ms,
            status="success",
        )
