"""
External data providers — abstraction layer for external intelligence.

Architecture:
  DataProvider (ABC) → fetch() returns structured dict
  Each signal type has a synthetic provider (default) and can be
  swapped for a real API provider via configuration.

Synthetic Data Strategy:
  - Deterministic: uses hash(data_key + time_bucket) as seed
  - Time-bucketed: same 6-hour window → same output (matches cache TTL)
  - Realistic distributions: severity follows supply chain patterns

Provider Registry:
  PROVIDER_REGISTRY maps provider names to classes.
  Active providers selected via EXTERNAL_PROVIDER_MODE config.
"""

import hashlib
import math
import time
from abc import ABC, abstractmethod

# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class DataProvider(ABC):
    """Base for all external data sources."""

    SCHEMA_VERSION: int = 1  # Override in subclasses when payload evolves

    @abstractmethod
    def fetch(self, context: dict) -> dict:
        """
        Fetch external data.

        Args:
            context: Optional context (e.g., {"data_key": "global"})

        Returns:
            Structured dict with provider-specific data.
            Must never raise — return empty/default on failure.
        """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Provider identifier (e.g., 'news_synthetic')."""

    @property
    @abstractmethod
    def category(self) -> str:
        """Signal category: news | weather | commodity | economic."""


# ---------------------------------------------------------------------------
# Seed utility
# ---------------------------------------------------------------------------


def _deterministic_seed(data_key: str, bucket_hours: int = 6) -> int:
    """
    Generate a deterministic seed from data_key + time bucket.

    Same 6-hour window → same seed → same synthetic output.
    This makes synthetic data reproducible within a cache refresh cycle.
    """
    bucket = int(time.time()) // (bucket_hours * 3600)
    raw = f"{data_key}:{bucket}"
    return int(hashlib.md5(raw.encode()).hexdigest()[:8], 16)


def _seeded_float(seed: int, index: int = 0) -> float:
    """Generate a pseudo-random float [0, 1) from seed + index."""
    h = hashlib.md5(f"{seed}:{index}".encode()).hexdigest()[:8]
    return int(h, 16) / 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Synthetic News Provider
# ---------------------------------------------------------------------------

_NEWS_HEADLINES = [
    {
        "headline": "Port congestion delays shipments across major trade routes",
        "category": "logistics",
        "base_score": 65,
    },
    {
        "headline": "Factory fire disrupts component supply in manufacturing hub",
        "category": "supply",
        "base_score": 80,
    },
    {
        "headline": "Trade tariffs announced affecting raw material imports",
        "category": "trade",
        "base_score": 55,
    },
    {
        "headline": "Labor strikes halt operations at key distribution centers",
        "category": "logistics",
        "base_score": 70,
    },
    {
        "headline": "New trade agreement opens alternative supply routes",
        "category": "trade",
        "base_score": 20,
    },
    {
        "headline": "Semiconductor shortage eases as new facilities come online",
        "category": "supply",
        "base_score": 15,
    },
    {
        "headline": "Cyber attack disrupts logistics network operations",
        "category": "security",
        "base_score": 85,
    },
    {
        "headline": "Regulatory changes require supply chain restructuring",
        "category": "regulatory",
        "base_score": 45,
    },
]


class SyntheticNewsProvider(DataProvider):
    """Generates synthetic supply chain news events."""

    SCHEMA_VERSION = 1

    @property
    def source_name(self) -> str:
        return "news_synthetic"

    @property
    def category(self) -> str:
        return "news"

    def fetch(self, context: dict) -> dict:
        data_key = context.get("data_key", "global")
        seed = _deterministic_seed(data_key)

        # Determine how many news events (0-3)
        event_count = int(_seeded_float(seed, 0) * 4)  # 0, 1, 2, or 3
        events = []

        for i in range(event_count):
            idx = int(_seeded_float(seed, i + 1) * len(_NEWS_HEADLINES))
            template = _NEWS_HEADLINES[idx]
            # Add noise to relevance score
            noise = (_seeded_float(seed, i + 10) - 0.5) * 20
            relevance = max(0, min(100, template["base_score"] + noise))

            events.append(
                {
                    "headline": template["headline"],
                    "category": template["category"],
                    "relevance_score": round(relevance, 1),
                    "source": "synthetic",
                }
            )

        return {
            "events": events,
            "fetched_at": int(time.time()),
            "provider": self.source_name,
        }


# ---------------------------------------------------------------------------
# Synthetic Weather Provider
# ---------------------------------------------------------------------------

_WEATHER_CONDITIONS = [
    {"condition": "Clear", "severity_level": "normal", "base_severity": 0.0},
    {"condition": "Rain", "severity_level": "minor", "base_severity": 0.1},
    {"condition": "Thunderstorm", "severity_level": "moderate", "base_severity": 0.4},
    {"condition": "Severe Storm", "severity_level": "severe", "base_severity": 0.7},
    {
        "condition": "Hurricane/Typhoon",
        "severity_level": "extreme",
        "base_severity": 1.0,
    },
    {"condition": "Heavy Snow", "severity_level": "moderate", "base_severity": 0.4},
    {"condition": "Flooding", "severity_level": "severe", "base_severity": 0.7},
    {"condition": "Extreme Heat", "severity_level": "moderate", "base_severity": 0.3},
]


class SyntheticWeatherProvider(DataProvider):
    """Generates synthetic weather conditions."""

    SCHEMA_VERSION = 1

    @property
    def source_name(self) -> str:
        return "weather_synthetic"

    @property
    def category(self) -> str:
        return "weather"

    def fetch(self, context: dict) -> dict:
        data_key = context.get("data_key", "global")
        seed = _deterministic_seed(data_key)

        idx = int(_seeded_float(seed, 0) * len(_WEATHER_CONDITIONS))
        condition = _WEATHER_CONDITIONS[idx]

        # Generate realistic temperature and wind
        temp_base = 15 + (_seeded_float(seed, 1) * 30)  # 15-45°C
        wind_base = 5 + (_seeded_float(seed, 2) * 80)  # 5-85 km/h

        return {
            "condition": condition["condition"],
            "severity_level": condition["severity_level"],
            "base_severity": condition["base_severity"],
            "temperature_c": round(temp_base, 1),
            "wind_speed_kmh": round(wind_base, 1),
            "region": context.get("region", "global"),
            "fetched_at": int(time.time()),
            "provider": self.source_name,
        }


# ---------------------------------------------------------------------------
# Synthetic Commodity Provider
# ---------------------------------------------------------------------------

_COMMODITIES = [
    {"name": "Steel", "baseline_price": 800.0},
    {"name": "Aluminum", "baseline_price": 2400.0},
    {"name": "Crude Oil", "baseline_price": 75.0},
    {"name": "Copper", "baseline_price": 9000.0},
    {"name": "Plastics (HDPE)", "baseline_price": 1200.0},
]


class SyntheticCommodityProvider(DataProvider):
    """Generates synthetic commodity price data using sine-wave + noise."""

    SCHEMA_VERSION = 1

    @property
    def source_name(self) -> str:
        return "commodity_synthetic"

    @property
    def category(self) -> str:
        return "commodity"

    def fetch(self, context: dict) -> dict:
        data_key = context.get("data_key", "global")
        seed = _deterministic_seed(data_key)

        commodities = []
        for i, c in enumerate(_COMMODITIES):
            # Sine wave (slow cycle) + random noise
            cycle = math.sin(_seeded_float(seed, i) * math.pi * 2)
            noise = (_seeded_float(seed, i + 10) - 0.5) * 0.3
            change_pct = round((cycle * 0.15 + noise) * 100, 2)  # -22% to +22%
            current = round(c["baseline_price"] * (1 + change_pct / 100), 2)

            commodities.append(
                {
                    "commodity": c["name"],
                    "baseline_price": c["baseline_price"],
                    "current_price": current,
                    "change_pct": change_pct,
                }
            )

        return {
            "commodities": commodities,
            "fetched_at": int(time.time()),
            "provider": self.source_name,
        }


# ---------------------------------------------------------------------------
# Synthetic Economic Provider
# ---------------------------------------------------------------------------


class SyntheticEconomicProvider(DataProvider):
    """Generates synthetic economic indicators with slow drift."""

    SCHEMA_VERSION = 1

    @property
    def source_name(self) -> str:
        return "economic_synthetic"

    @property
    def category(self) -> str:
        return "economic"

    def fetch(self, context: dict) -> dict:
        data_key = context.get("data_key", "global")
        seed = _deterministic_seed(data_key)

        # PMI: centers around 50, drifts 35-65
        pmi_drift = (_seeded_float(seed, 0) - 0.5) * 30
        pmi = round(max(30, min(65, 50 + pmi_drift)), 1)

        # Inflation: centers around 3%, drifts 0.5-8%
        inflation_drift = (_seeded_float(seed, 1) - 0.5) * 10
        inflation = round(max(0.5, min(8.0, 3.0 + inflation_drift)), 1)

        # Consumer confidence: centers around 100, drifts 70-130
        cc_drift = (_seeded_float(seed, 2) - 0.5) * 60
        consumer_confidence = round(max(60, min(140, 100 + cc_drift)), 1)

        return {
            "indicators": {
                "pmi": pmi,
                "inflation_pct": inflation,
                "consumer_confidence": consumer_confidence,
            },
            "fetched_at": int(time.time()),
            "provider": self.source_name,
        }


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------

PROVIDER_REGISTRY: dict[str, type[DataProvider]] = {
    # E5: Synthetic providers (always available)
    "news_synthetic": SyntheticNewsProvider,
    "weather_synthetic": SyntheticWeatherProvider,
    "commodity_synthetic": SyntheticCommodityProvider,
    "economic_synthetic": SyntheticEconomicProvider,
}

# E7: Register real providers (deferred import to avoid circular deps)
try:
    from signals.real_providers import (
        AlphaVantageProvider,
        FREDProvider,
        NewsAPIProvider,
        OpenWeatherMapProvider,
    )

    PROVIDER_REGISTRY.update(
        {
            "news_real": NewsAPIProvider,
            "weather_real": OpenWeatherMapProvider,
            "commodity_real": AlphaVantageProvider,
            "economic_real": FREDProvider,
        }
    )
except ImportError:
    pass  # Graceful — real providers are optional


# Default provider mapping by category
DEFAULT_PROVIDERS: dict[str, str] = {
    "news": "news_synthetic",
    "weather": "weather_synthetic",
    "commodity": "commodity_synthetic",
    "economic": "economic_synthetic",
}

# E7: API key config mapping (category → settings field name)
_API_KEY_MAP: dict[str, str] = {
    "news": "newsapi_key",
    "weather": "openweathermap_key",
    "commodity": "alphavantage_key",
    "economic": "fred_key",
}

# Future: Multi-provider priority chains (E8+)
# Architecture supports ordered fallback lists per category:
#   PROVIDER_PRIORITY = {
#       "news": ["news_newsapi", "news_gnews", "news_synthetic"],
#       "weather": ["weather_owm", "weather_weatherapi", "weather_synthetic"],
#   }
# The get_provider() function would iterate the priority list, trying
# each provider until one succeeds. For E7, we use single-provider-per-category.


def _get_api_key(category: str) -> str:
    """
    Get the API key for a category from settings.

    Returns empty string if no key configured.
    Fail-soft: logs warning if key looks malformed (< 8 chars) but doesn't crash.
    """
    import logging

    from config import settings

    key_field = _API_KEY_MAP.get(category, "")
    if not key_field:
        return ""

    key = getattr(settings, key_field, "")
    if key and len(key) < 8:
        logger = logging.getLogger("synchain.providers")
        logger.warning(
            "API key for %s looks too short (%d chars) — may be invalid",
            category,
            len(key),
        )
    return key


def get_provider(category: str, mode: str = "auto") -> DataProvider:
    """
    Get a provider instance for the given category and mode.

    Modes:
      - "auto" (default): Use real provider if API key is configured,
        otherwise fall back to synthetic.
      - "synthetic": Always use synthetic provider.
      - "real": Always use real provider (with API key injection).

    Args:
        category: news | weather | commodity | economic
        mode: "auto" | "synthetic" | "real"

    Returns:
        Instantiated DataProvider.

    Raises:
        ValueError: If category is unknown.
    """
    if mode == "auto":
        api_key = _get_api_key(category)
        if api_key:
            real_key = f"{category}_real"
            cls = PROVIDER_REGISTRY.get(real_key)
            if cls:
                return cls(api_key=api_key)
        # Fallback to synthetic
        synthetic_key = f"{category}_synthetic"
        cls = PROVIDER_REGISTRY.get(synthetic_key)
        if cls:
            return cls()
        raise ValueError(f"No provider for category={category}")

    elif mode == "real":
        api_key = _get_api_key(category)
        real_key = f"{category}_real"
        cls = PROVIDER_REGISTRY.get(real_key)
        if cls:
            return cls(api_key=api_key)
        raise ValueError(f"No real provider for category={category}")

    else:  # "synthetic" or any other value
        key = f"{category}_{mode}"
        cls = PROVIDER_REGISTRY.get(key)
        if not cls:
            default_key = DEFAULT_PROVIDERS.get(category)
            if default_key:
                cls = PROVIDER_REGISTRY.get(default_key)
        if not cls:
            raise ValueError(f"No provider for category={category}, mode={mode}")
        return cls()


def get_active_provider_info() -> dict[str, dict]:
    """
    Get info about which provider is active for each category.

    Returns dict of {category: {configured, active_provider, mode}}.
    Used by the /external/config endpoint.
    """
    from config import settings

    mode = settings.external_provider_mode

    result = {}
    for category in DEFAULT_PROVIDERS:
        api_key = _get_api_key(category)
        has_key = bool(api_key)

        if mode == "auto":
            active = f"{category}_real" if has_key else f"{category}_synthetic"
        elif mode == "real":
            active = f"{category}_real"
        else:
            active = f"{category}_synthetic"

        result[category] = {
            "configured": has_key,
            "active_provider": active,
        }

    return result
