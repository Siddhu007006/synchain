"""
Mathematical utilities for Digital Twin state updates.

EWMA (Exponentially Weighted Moving Average):
  - Used for smoothing demand, delay, confidence, and risk metrics
  - α = 0.3 by default: ~70% history, ~30% latest data point
  - Supply chains have inertia — overreacting is worse than underreacting

Trend Detection:
  - Classifies demand as Rising/Stable/Falling based on latest vs. average
  - Uses ±10% threshold to avoid noise-driven trend flips
"""

# Default smoothing factor. Approved value: 0.3.
# Lower α → smoother (more historical weight)
# Higher α → more reactive (more weight on latest data)
EWMA_ALPHA = 0.3

# Trend detection thresholds
TREND_RISING_THRESHOLD = 1.10  # latest > avg × 1.10 → Rising
TREND_FALLING_THRESHOLD = 0.90  # latest < avg × 0.90 → Falling


def ewma(current_value: float, old_avg: float, alpha: float = EWMA_ALPHA) -> float:
    """
    Compute EWMA update.

    Formula: new_avg = α × current_value + (1 - α) × old_avg

    If old_avg is 0 (first data point), returns current_value directly
    to avoid anchoring at zero.
    """
    if old_avg == 0.0:
        return current_value
    return round(alpha * current_value + (1 - alpha) * old_avg, 4)


def classify_trend(latest_demand: float, avg_demand: float) -> str:
    """
    Classify demand trend based on latest observation vs. EWMA average.

    Returns:
      - "Rising"  if latest > avg × 1.10  (demand growing)
      - "Falling" if latest < avg × 0.90  (demand shrinking)
      - "Stable"  otherwise               (within normal range)
    """
    if avg_demand <= 0:
        return "Stable"
    ratio = latest_demand / avg_demand
    if ratio > TREND_RISING_THRESHOLD:
        return "Rising"
    elif ratio < TREND_FALLING_THRESHOLD:
        return "Falling"
    return "Stable"


def compute_reliability_score(avg_delay: float, max_delay: float) -> float:
    """
    Compute supplier reliability score (0–100).

    Formula: 100 - (avg_delay / max_delay × 100)

    If max_delay is 0 (no delays recorded), returns 100.0 (perfect reliability).
    """
    if max_delay <= 0:
        return 100.0
    return round(max(0.0, 100.0 - (avg_delay / max_delay * 100.0)), 2)


def compute_selection_rate(times_selected: int, total_simulations: int) -> float:
    """
    Compute warehouse selection rate as a fraction (0.0–1.0).

    Returns 0.0 if no simulations have been run.
    """
    if total_simulations <= 0:
        return 0.0
    return round(times_selected / total_simulations, 4)


def compute_utilization(demand: float, capacity: float) -> float:
    """
    Compute warehouse utilization as a fraction (0.0–1.0+).

    Can exceed 1.0 if demand exceeds capacity (over-utilization).
    """
    if capacity <= 0:
        return 0.0
    return round(demand / capacity, 4)
