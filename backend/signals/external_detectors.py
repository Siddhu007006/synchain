"""
External signal detectors — detect conditions from cached external data.

Each detector:
  1. Inherits from SignalDetector (same ABC as E3 detectors)
  2. Reads from ExternalDataCache (never calls external APIs directly)
  3. Returns 0+ SignalOutput instances
  4. Gracefully returns [] if cache is missing/expired

Cache key resolution (C2 fix):
  Detectors must read from the ACTIVE provider's cache entry, not a
  static "news_synthetic" key. When real API keys are configured
  and EXTERNAL_PROVIDER_MODE=auto, the scheduler writes to "news_real".
  Detectors now use _get_cache_data(category) which:
    1. Tries the active provider key (real or synthetic, based on config)
    2. Falls back to the synthetic key if the active key has no data

Detectors:
  - NewsDisruptionDetector:    Disruption news with relevance > 40
  - WeatherAlertDetector:      Severe weather conditions
  - CommodityShockDetector:    Commodity price change > ±10%
  - EconomicShiftDetector:     PMI < 45 or Inflation > 5%
"""

import logging

from digital_twin.models import DigitalTwin
from signals.detectors import SignalDetector, SignalOutput
from signals.external_cache import CacheManager
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.external_detectors")


# ---------------------------------------------------------------------------
# Cache key resolution — reads active provider, falls back to synthetic
# ---------------------------------------------------------------------------


def _get_cache_data(category: str, db: Session) -> dict | None:
    """
    Read external data from cache using the active provider key.

    Resolution order:
      1. Determine active provider name for category (real or synthetic)
         based on current config (EXTERNAL_PROVIDER_MODE + API key presence)
      2. Try to read that cache key
      3. If empty/expired, fall back to the synthetic key
      4. Return None if both are empty (cache not yet populated)

    This means:
      - With real API keys: reads "news_real", falls back to "news_synthetic"
      - Without real keys:  reads "news_synthetic" directly
    """
    cache = CacheManager(db)

    # Determine active provider name from config
    try:
        from signals.providers import get_active_provider_info

        info = get_active_provider_info()
        active_provider = info.get(category, {}).get(
            "active_provider", f"{category}_synthetic"
        )
    except Exception:
        active_provider = f"{category}_synthetic"

    # Try active provider cache first
    data = cache.get(active_provider, "global")
    if data:
        return data

    # Fall back to synthetic if active provider cache is empty/expired
    synthetic_key = f"{category}_synthetic"
    if active_provider != synthetic_key:
        data = cache.get(synthetic_key, "global")
        if data:
            logger.debug(
                "Active provider cache '%s' empty, using synthetic fallback for %s",
                active_provider,
                category,
            )
            return data

    return None


# ---------------------------------------------------------------------------
# News Disruption Detector
# ---------------------------------------------------------------------------

NEWS_DISRUPTION_THRESHOLD = 40  # relevance_score > 40 triggers


class NewsDisruptionDetector(SignalDetector):
    """
    Detects supply chain disruption from cached news data.

    Condition: News event with relevance_score > 40
    Severity:  min(1.0, relevance_score / 100)
    """

    @property
    def source(self) -> str:
        return "NewsDisruption"

    @property
    def signal_type(self) -> str:
        return "external"

    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        data = _get_cache_data("news", db)
        if not data:
            return []

        events = data.get("events", [])
        signals = []

        for event in events:
            relevance = event.get("relevance_score", 0)
            if relevance > NEWS_DISRUPTION_THRESHOLD:
                severity = min(1.0, round(relevance / 100, 4))
                signals.append(
                    SignalOutput(
                        source=self.source,
                        signal_type=self.signal_type,
                        severity=severity,
                        payload={
                            "headline": event.get("headline", ""),
                            "category": event.get("category", ""),
                            "relevance_score": relevance,
                            "source": event.get("source", "synthetic"),
                            "provider": data.get("provider", "unknown"),
                        },
                    )
                )

        return signals


# ---------------------------------------------------------------------------
# Weather Alert Detector
# ---------------------------------------------------------------------------

# Severity mapping by weather severity level
_WEATHER_SEVERITY = {
    "normal": 0.0,
    "minor": 0.2,
    "moderate": 0.4,
    "severe": 0.7,
    "extreme": 1.0,
}

WEATHER_ALERT_MIN_SEVERITY = "moderate"  # only moderate+ triggers


class WeatherAlertDetector(SignalDetector):
    """
    Detects severe weather from cached weather data.

    Condition: Weather severity_level >= moderate
    Severity:  Mapped: minor=0.2, moderate=0.4, severe=0.7, extreme=1.0
    """

    @property
    def source(self) -> str:
        return "WeatherAlert"

    @property
    def signal_type(self) -> str:
        return "external"

    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        data = _get_cache_data("weather", db)
        if not data:
            return []

        severity_level = data.get("severity_level", "normal")
        severity = _WEATHER_SEVERITY.get(severity_level, 0.0)

        # Only trigger for moderate or above
        if severity < _WEATHER_SEVERITY.get(WEATHER_ALERT_MIN_SEVERITY, 0.4):
            return []

        return [
            SignalOutput(
                source=self.source,
                signal_type=self.signal_type,
                severity=severity,
                payload={
                    "condition": data.get("condition", "Unknown"),
                    "severity_level": severity_level,
                    "region": data.get("region", "global"),
                    "temperature_c": data.get("temperature_c"),
                    "wind_speed_kmh": data.get("wind_speed_kmh"),
                    "provider": data.get("provider", "unknown"),
                },
            )
        ]


# ---------------------------------------------------------------------------
# Commodity Shock Detector
# ---------------------------------------------------------------------------

COMMODITY_SHOCK_THRESHOLD = 10.0  # ±10% change triggers
COMMODITY_SHOCK_MAX_CHANGE = 30.0  # 30% = max severity


class CommodityShockDetector(SignalDetector):
    """
    Detects commodity price shocks from cached data.

    Condition: Price change > ±10% from baseline
    Severity:  min(1.0, abs(change_pct) / 30)
    """

    @property
    def source(self) -> str:
        return "CommodityShock"

    @property
    def signal_type(self) -> str:
        return "external"

    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        data = _get_cache_data("commodity", db)
        if not data:
            return []

        commodities = data.get("commodities", [])
        signals = []

        for c in commodities:
            change_pct = abs(c.get("change_pct", 0))
            if change_pct > COMMODITY_SHOCK_THRESHOLD:
                severity = min(1.0, round(change_pct / COMMODITY_SHOCK_MAX_CHANGE, 4))
                signals.append(
                    SignalOutput(
                        source=self.source,
                        signal_type=self.signal_type,
                        severity=severity,
                        payload={
                            "commodity": c.get("commodity", ""),
                            "current_price": c.get("current_price"),
                            "baseline_price": c.get("baseline_price"),
                            "change_pct": c.get("change_pct"),
                            "provider": data.get("provider", "unknown"),
                        },
                    )
                )

        return signals


# ---------------------------------------------------------------------------
# Economic Shift Detector
# ---------------------------------------------------------------------------

ECONOMIC_PMI_THRESHOLD = 45.0  # PMI < 45 = contraction
ECONOMIC_INFLATION_THRESHOLD = 5.0  # Inflation > 5% = high
ECONOMIC_PMI_MAX_DEVIATION = 20.0  # PMI 30 = max severity
ECONOMIC_INFLATION_MAX = 5.0  # Inflation 8% = max severity


class EconomicShiftDetector(SignalDetector):
    """
    Detects economic condition shifts from cached data.

    Conditions:
      PMI < 45 → severity = min(1.0, (50 - pmi) / 20)
      Inflation > 5% → severity = min(1.0, (inflation - 3) / 5)
    """

    @property
    def source(self) -> str:
        return "EconomicShift"

    @property
    def signal_type(self) -> str:
        return "external"

    def evaluate(self, twin: DigitalTwin, db: Session) -> list[SignalOutput]:
        data = _get_cache_data("economic", db)
        if not data:
            return []

        indicators = data.get("indicators", {})
        signals = []

        # PMI contraction check
        pmi = indicators.get("pmi")
        if pmi is not None and pmi < ECONOMIC_PMI_THRESHOLD:
            severity = min(1.0, round((50 - pmi) / ECONOMIC_PMI_MAX_DEVIATION, 4))
            signals.append(
                SignalOutput(
                    source=self.source,
                    signal_type=self.signal_type,
                    severity=severity,
                    payload={
                        "indicator": "pmi",
                        "value": pmi,
                        "threshold": ECONOMIC_PMI_THRESHOLD,
                        "direction": "contraction",
                        "provider": data.get("provider", "unknown"),
                    },
                )
            )

        # Inflation check
        # NOTE: Severity baseline is 3% (normal inflation), NOT the 5% trigger threshold.
        # This is intentional: at the trigger point (inflation=5%), severity is already
        # 0.40 because 5% inflation is significantly above normal (3%).
        # Formula: (inflation - 3) / 5 → measures "how far above normal," not
        # "how far above threshold." This creates a designed discontinuity at the
        # trigger: no signal at 4.99% → severity 0.40 at 5.01%.
        # Reviewed and accepted in Business Logic Audit (F2.15, 2026-06-06).
        inflation = indicators.get("inflation_pct")
        if inflation is not None and inflation > ECONOMIC_INFLATION_THRESHOLD:
            severity = min(1.0, round((inflation - 3) / ECONOMIC_INFLATION_MAX, 4))
            signals.append(
                SignalOutput(
                    source=self.source,
                    signal_type=self.signal_type,
                    severity=severity,
                    payload={
                        "indicator": "inflation",
                        "value": inflation,
                        "threshold": ECONOMIC_INFLATION_THRESHOLD,
                        "direction": "rising",
                        "provider": data.get("provider", "unknown"),
                    },
                )
            )

        return signals


# ---------------------------------------------------------------------------
# Registry — all external detectors
# ---------------------------------------------------------------------------

EXTERNAL_DETECTORS: list[type[SignalDetector]] = [
    NewsDisruptionDetector,
    WeatherAlertDetector,
    CommodityShockDetector,
    EconomicShiftDetector,
]
