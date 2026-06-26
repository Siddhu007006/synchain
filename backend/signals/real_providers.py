"""
Real API providers for external intelligence.

Each provider implements the DataProvider ABC from providers.py and returns
data in the SAME schema as its synthetic counterpart. Detectors read from
cache and do not distinguish real from synthetic.

Design Decisions (E7 Architecture Report):
  D1: Same output schema as synthetic (detectors are schema-agnostic)
  D2: Never raise — return {} on failure (graceful degradation)
  D3: Auto mode — real if API key present, synthetic otherwise
  D4: httpx synchronous client (runs in background scheduler)
  D5: Fallback at provider-selection level (not cache level)
  D6: schema_version=2 for richer real data fields

Providers:
  - NewsAPIProvider:          newsapi.org — supply chain news headlines
  - OpenWeatherMapProvider:   openweathermap.org — weather conditions
  - AlphaVantageProvider:     alphavantage.co — commodity prices
  - FREDProvider:             api.stlouisfed.org — economic indicators (PMI, CPI)

Future: Multi-provider priority chains (e.g., NewsAPI → GNews fallback)
  are architecturally supported via PROVIDER_REGISTRY but not implemented
  in E7. See E8 planning notes.
"""

import logging
import time

from signals.http_client import RateLimitedClient
from signals.providers import DataProvider

logger = logging.getLogger("synchain.real_providers")

# Shared HTTP client — reused across all providers
_http_client: RateLimitedClient | None = None


def _get_client() -> RateLimitedClient:
    """Get or create shared HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = RateLimitedClient(timeout=10.0)
    return _http_client


# ---------------------------------------------------------------------------
# News — NewsAPI.org
# ---------------------------------------------------------------------------

# Supply chain related search query
_NEWS_QUERY = (
    "supply chain disruption OR logistics delay OR manufacturing shortage "
    "OR port congestion OR trade tariff"
)


class NewsAPIProvider(DataProvider):
    """
    Fetches supply chain news from NewsAPI.org.

    API: https://newsapi.org/v2/everything
    Free tier: 100 requests/day
    Returns: Headlines with relevance scoring.
    """

    SCHEMA_VERSION = 2

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    @property
    def source_name(self) -> str:
        return "news_real"

    @property
    def category(self) -> str:
        return "news"

    def fetch(self, context: dict) -> dict:
        if not self._api_key:
            logger.warning("NewsAPI key is empty, returning empty result")
            return {}

        client = _get_client()
        data = client.get_json(
            "https://newsapi.org/v2/everything",
            params={
                "q": _NEWS_QUERY,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": 5,
                "apiKey": self._api_key,
            },
        )

        if not data or data.get("status") != "ok":
            logger.warning(
                "NewsAPI returned error: %s",
                data.get("message", "unknown") if data else "no response",
            )
            return {}

        articles = data.get("articles", [])
        events = []

        for article in articles:
            # Map relevance: NewsAPI doesn't provide a score, so we estimate
            # based on title keyword density and source reputation
            title = (article.get("title") or "").lower()
            relevance = _estimate_news_relevance(title)

            events.append(
                {
                    "headline": article.get("title", ""),
                    "category": _classify_news_category(title),
                    "relevance_score": relevance,
                    "source": article.get("source", {}).get("name", "unknown"),
                    # E7 v2 fields (not read by E5 detectors, available for future use)
                    "published_at": article.get("publishedAt", ""),
                    "source_url": article.get("url", ""),
                    "author": article.get("author", ""),
                }
            )

        return {
            "events": events,
            "fetched_at": int(time.time()),
            "provider": self.source_name,
        }


def _estimate_news_relevance(title: str) -> float:
    """
    Estimate relevance score (0-100) from headline text.

    Heuristic: count supply-chain keywords, scale to 0-100.
    More keywords → higher relevance.
    """
    keywords = [
        "supply chain",
        "disruption",
        "shortage",
        "delay",
        "port",
        "logistics",
        "tariff",
        "strike",
        "factory",
        "manufacturing",
        "freight",
        "shipping",
        "embargo",
        "sanctions",
        "recall",
        "fire",
        "flood",
        "earthquake",
    ]
    matches = sum(1 for kw in keywords if kw in title)
    # 0 matches → 20 (baseline), 1 → 40, 2 → 60, 3+ → 80+
    return min(100.0, round(20 + matches * 25, 1))


def _classify_news_category(title: str) -> str:
    """Classify news headline into supply chain category."""
    if any(w in title for w in ["port", "logistics", "freight", "shipping", "strike"]):
        return "logistics"
    if any(w in title for w in ["factory", "manufacturing", "supply", "shortage"]):
        return "supply"
    if any(w in title for w in ["tariff", "trade", "sanctions", "embargo"]):
        return "trade"
    if any(w in title for w in ["cyber", "hack", "breach"]):
        return "security"
    if any(w in title for w in ["regulation", "compliance", "regulatory"]):
        return "regulatory"
    return "general"


# ---------------------------------------------------------------------------
# Weather — OpenWeatherMap
# ---------------------------------------------------------------------------

# Weather condition ID ranges → severity mapping
# See: https://openweathermap.org/weather-conditions
_OWM_SEVERITY_MAP = {
    "Clear": ("normal", 0.0),
    "Clouds": ("normal", 0.0),
    "Drizzle": ("minor", 0.1),
    "Rain": ("minor", 0.2),
    "Snow": ("moderate", 0.4),
    "Thunderstorm": ("moderate", 0.5),
    "Tornado": ("extreme", 1.0),
    "Squall": ("severe", 0.7),
    "Ash": ("severe", 0.6),
    "Fog": ("minor", 0.1),
    "Mist": ("normal", 0.0),
    "Haze": ("normal", 0.0),
    "Dust": ("minor", 0.2),
    "Sand": ("moderate", 0.3),
    "Smoke": ("moderate", 0.4),
}


class OpenWeatherMapProvider(DataProvider):
    """
    Fetches weather data from OpenWeatherMap API.

    API: https://api.openweathermap.org/data/2.5/weather
    Free tier: 1000 calls/day
    Returns: Current weather conditions with severity mapping.
    """

    SCHEMA_VERSION = 2

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    @property
    def source_name(self) -> str:
        return "weather_real"

    @property
    def category(self) -> str:
        return "weather"

    def fetch(self, context: dict) -> dict:
        if not self._api_key:
            logger.warning("OpenWeatherMap key is empty, returning empty result")
            return {}

        # Default to a major logistics hub (Singapore) for global scope
        lat = context.get("lat", 1.3521)
        lon = context.get("lon", 103.8198)

        client = _get_client()
        data = client.get_json(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat": lat,
                "lon": lon,
                "appid": self._api_key,
                "units": "metric",
            },
        )

        if not data or "weather" not in data:
            logger.warning("OpenWeatherMap returned invalid data")
            return {}

        weather = data["weather"][0] if data.get("weather") else {}
        main_condition = weather.get("main", "Clear")
        severity_level, base_severity = _OWM_SEVERITY_MAP.get(
            main_condition, ("normal", 0.0)
        )

        # Boost severity if wind is very high (> 60 km/h)
        wind_speed = data.get("wind", {}).get("speed", 0) * 3.6  # m/s → km/h
        if wind_speed > 60 and severity_level in ("normal", "minor"):
            severity_level = "moderate"
            base_severity = max(base_severity, 0.4)

        main_data = data.get("main", {})

        return {
            "condition": weather.get("description", main_condition),
            "severity_level": severity_level,
            "base_severity": base_severity,
            "temperature_c": round(main_data.get("temp", 20.0), 1),
            "wind_speed_kmh": round(wind_speed, 1),
            "region": context.get("region", "global"),
            "fetched_at": int(time.time()),
            "provider": self.source_name,
            # E7 v2 fields
            "humidity": main_data.get("humidity", 0),
            "pressure_hpa": main_data.get("pressure", 0),
        }


# ---------------------------------------------------------------------------
# Commodity — Alpha Vantage
# ---------------------------------------------------------------------------

# Commodity symbols tracked
_COMMODITY_SYMBOLS = [
    {"symbol": "WTI", "function": "WTI", "name": "Crude Oil", "baseline_price": 75.0},
    {
        "symbol": "COPPER",
        "function": "COPPER",
        "name": "Copper",
        "baseline_price": 9000.0,
    },
    {
        "symbol": "ALUMINUM",
        "function": "ALUMINUM",
        "name": "Aluminum",
        "baseline_price": 2400.0,
    },
]


class AlphaVantageProvider(DataProvider):
    """
    Fetches commodity price data from Alpha Vantage.

    API: https://www.alphavantage.co/query
    Free tier: 25 requests/day, 5 requests/minute
    Returns: Commodity prices with change percentages.

    Note: Free tier is rate-limited. With 6-hour refresh (4 calls/day for
    3 commodities = 12 calls), we stay well within the 25/day limit.
    """

    SCHEMA_VERSION = 2

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    @property
    def source_name(self) -> str:
        return "commodity_real"

    @property
    def category(self) -> str:
        return "commodity"

    def fetch(self, context: dict) -> dict:
        if not self._api_key:
            logger.warning("Alpha Vantage key is empty, returning empty result")
            return {}

        client = _get_client()
        commodities = []

        for spec in _COMMODITY_SYMBOLS:
            data = client.get_json(
                "https://www.alphavantage.co/query",
                params={
                    "function": spec["function"],
                    "interval": "monthly",
                    "apikey": self._api_key,
                },
            )

            if not data or "data" not in data:
                logger.warning(
                    "Alpha Vantage returned no data for %s",
                    spec["name"],
                )
                # Use baseline as fallback for this commodity
                commodities.append(
                    {
                        "commodity": spec["name"],
                        "baseline_price": spec["baseline_price"],
                        "current_price": spec["baseline_price"],
                        "change_pct": 0.0,
                    }
                )
                continue

            # Parse the most recent data point
            entries = data.get("data", [])
            if entries:
                latest = entries[0]
                current_price = float(latest.get("value", spec["baseline_price"]))
                change_pct = round(
                    ((current_price - spec["baseline_price"]) / spec["baseline_price"])
                    * 100,
                    2,
                )
                commodities.append(
                    {
                        "commodity": spec["name"],
                        "baseline_price": spec["baseline_price"],
                        "current_price": round(current_price, 2),
                        "change_pct": change_pct,
                    }
                )
            else:
                commodities.append(
                    {
                        "commodity": spec["name"],
                        "baseline_price": spec["baseline_price"],
                        "current_price": spec["baseline_price"],
                        "change_pct": 0.0,
                    }
                )

        return {
            "commodities": commodities,
            "fetched_at": int(time.time()),
            "provider": self.source_name,
        }


# ---------------------------------------------------------------------------
# Economic — FRED (Federal Reserve Economic Data)
# ---------------------------------------------------------------------------

# FRED series IDs for economic indicators
_FRED_SERIES = {
    "pmi": "MANEMP",  # Manufacturing employment (proxy for PMI)
    "inflation_pct": "CPIAUCSL",  # Consumer Price Index
    "consumer_confidence": "UMCSENT",  # U of Michigan Consumer Sentiment
}


class FREDProvider(DataProvider):
    """
    Fetches economic indicators from the FRED API.

    API: https://api.stlouisfed.org/fred/series/observations
    Free tier: Unlimited (requires free API key)
    Returns: PMI, Inflation, Consumer Confidence indicators.
    """

    SCHEMA_VERSION = 2

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    @property
    def source_name(self) -> str:
        return "economic_real"

    @property
    def category(self) -> str:
        return "economic"

    def fetch(self, context: dict) -> dict:
        if not self._api_key:
            logger.warning("FRED key is empty, returning empty result")
            return {}

        client = _get_client()
        indicators = {}

        for indicator_name, series_id in _FRED_SERIES.items():
            data = client.get_json(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self._api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1,
                },
            )

            if not data or "observations" not in data:
                logger.warning("FRED returned no data for %s", series_id)
                indicators[indicator_name] = _fred_default(indicator_name)
                continue

            observations = data.get("observations", [])
            if observations:
                raw_value = observations[0].get("value", ".")
                if raw_value == "." or not raw_value:
                    # FRED uses "." for missing data
                    indicators[indicator_name] = _fred_default(indicator_name)
                else:
                    indicators[indicator_name] = round(float(raw_value), 1)
            else:
                indicators[indicator_name] = _fred_default(indicator_name)

        # Normalize PMI: MANEMP is in thousands, map to PMI-like 30-70 scale
        if "pmi" in indicators and indicators["pmi"] > 100:
            # Very rough normalization: recent US manufacturing employment
            # is ~12,000-13,000 (thousands). Map to ~45-55 PMI range.
            raw = indicators["pmi"]
            indicators["pmi"] = round(max(30, min(70, 50 + (raw - 12500) / 200)), 1)

        # Normalize inflation: CPI is an index (~300+), compute YoY approx
        # For simplicity, assume baseline CPI = 280 (2023 level)
        if "inflation_pct" in indicators and indicators["inflation_pct"] > 10:
            raw = indicators["inflation_pct"]
            indicators["inflation_pct"] = round(
                max(0.5, min(8.0, ((raw - 280) / 280) * 100)), 1
            )

        return {
            "indicators": indicators,
            "fetched_at": int(time.time()),
            "provider": self.source_name,
        }


def _fred_default(indicator_name: str) -> float:
    """Return safe default for a FRED indicator on fetch failure."""
    defaults = {
        "pmi": 50.0,
        "inflation_pct": 3.0,
        "consumer_confidence": 100.0,
    }
    return defaults.get(indicator_name, 0.0)
