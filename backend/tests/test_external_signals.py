"""
Phase E5 Tests — External Intelligence.

Covers:
  1. Synthetic providers (data generation, determinism)
  2. External data cache (upsert, get, expiry, status)
  3. External detectors (trigger conditions, severity, graceful empty)
  4. Signal weight registration
  5. Integration (cache → detector → forecast pipeline)
  6. API endpoints (status, refresh)
"""

import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Test DB setup (mirrors conftest pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def e5_db():
    """Dedicated in-memory DB for E5 tests."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng)
    session = Session()
    yield session
    session.close()


# =========================================================================
# 1. Synthetic Providers
# =========================================================================


class TestSyntheticProviders:
    """Test that all 4 synthetic providers generate valid data."""

    def test_news_provider_returns_data(self):
        from signals.providers import SyntheticNewsProvider

        p = SyntheticNewsProvider()
        data = p.fetch({"data_key": "global"})
        assert "events" in data
        assert "fetched_at" in data
        assert "provider" in data
        assert data["provider"] == "news_synthetic"
        assert isinstance(data["events"], list)

    def test_weather_provider_returns_data(self):
        from signals.providers import SyntheticWeatherProvider

        p = SyntheticWeatherProvider()
        data = p.fetch({"data_key": "global"})
        assert "condition" in data
        assert "severity_level" in data
        assert "temperature_c" in data
        assert "wind_speed_kmh" in data
        assert data["provider"] == "weather_synthetic"

    def test_commodity_provider_returns_data(self):
        from signals.providers import SyntheticCommodityProvider

        p = SyntheticCommodityProvider()
        data = p.fetch({"data_key": "global"})
        assert "commodities" in data
        assert len(data["commodities"]) == 5
        for c in data["commodities"]:
            assert "commodity" in c
            assert "baseline_price" in c
            assert "current_price" in c
            assert "change_pct" in c

    def test_economic_provider_returns_data(self):
        from signals.providers import SyntheticEconomicProvider

        p = SyntheticEconomicProvider()
        data = p.fetch({"data_key": "global"})
        assert "indicators" in data
        ind = data["indicators"]
        assert "pmi" in ind
        assert "inflation_pct" in ind
        assert "consumer_confidence" in ind
        assert 30 <= ind["pmi"] <= 65
        assert 0.5 <= ind["inflation_pct"] <= 8.0

    def test_provider_determinism(self):
        """Same data_key in same time bucket → same output."""
        from signals.providers import SyntheticNewsProvider

        p = SyntheticNewsProvider()
        r1 = p.fetch({"data_key": "test_key"})
        r2 = p.fetch({"data_key": "test_key"})
        assert r1["events"] == r2["events"]

    def test_different_keys_differ(self):
        """Different data_keys → different output."""
        from signals.providers import SyntheticCommodityProvider

        p = SyntheticCommodityProvider()
        r1 = p.fetch({"data_key": "key_a"})
        r2 = p.fetch({"data_key": "key_b"})
        # Prices should differ (extremely unlikely to match)
        prices1 = [c["current_price"] for c in r1["commodities"]]
        prices2 = [c["current_price"] for c in r2["commodities"]]
        assert prices1 != prices2

    def test_provider_registry(self):
        from signals.providers import get_provider

        for cat in ["news", "weather", "commodity", "economic"]:
            p = get_provider(cat, "synthetic")
            assert p.category == cat

    def test_provider_schema_version(self):
        from signals.providers import SyntheticNewsProvider

        p = SyntheticNewsProvider()
        assert p.SCHEMA_VERSION == 1

    def test_provider_source_names(self):
        from signals.providers import (
            SyntheticCommodityProvider,
            SyntheticEconomicProvider,
            SyntheticNewsProvider,
            SyntheticWeatherProvider,
        )

        assert SyntheticNewsProvider().source_name == "news_synthetic"
        assert SyntheticWeatherProvider().source_name == "weather_synthetic"
        assert SyntheticCommodityProvider().source_name == "commodity_synthetic"
        assert SyntheticEconomicProvider().source_name == "economic_synthetic"


# =========================================================================
# 2. External Data Cache
# =========================================================================


class TestCacheManager:
    """Test cache upsert, get, expiry, and status."""

    def test_upsert_and_get(self, e5_db):
        from signals.external_cache import CacheManager

        cm = CacheManager(e5_db)
        cm.upsert("test_provider", "global", {"hello": "world"}, ttl_hours=12)
        e5_db.commit()

        result = cm.get("test_provider", "global")
        assert result is not None
        assert result["hello"] == "world"

    def test_upsert_updates_existing(self, e5_db):
        from signals.external_cache import CacheManager

        cm = CacheManager(e5_db)
        cm.upsert("prov", "key", {"v": 1}, ttl_hours=12)
        e5_db.commit()

        cm.upsert("prov", "key", {"v": 2}, ttl_hours=12)
        e5_db.commit()

        result = cm.get("prov", "key")
        assert result["v"] == 2

    def test_get_missing_returns_none(self, e5_db):
        from signals.external_cache import CacheManager

        cm = CacheManager(e5_db)
        result = cm.get("nonexistent", "global")
        assert result is None

    def test_expired_cache_returns_none(self, e5_db):
        from signals.external_cache import CacheManager, ExternalDataCache

        cm = CacheManager(e5_db)

        # Insert entry that's already expired
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        entry = ExternalDataCache(
            provider="expired_prov",
            data_key="global",
            data_json=json.dumps({"old": True}),
            schema_version=1,
            fetched_at=past - timedelta(hours=11),
            expires_at=past,
        )
        e5_db.add(entry)
        e5_db.commit()

        result = cm.get("expired_prov", "global", require_valid=True)
        assert result is None

    def test_expired_cache_available_without_validation(self, e5_db):
        from signals.external_cache import CacheManager, ExternalDataCache

        cm = CacheManager(e5_db)

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        entry = ExternalDataCache(
            provider="expired2",
            data_key="global",
            data_json=json.dumps({"old": True}),
            schema_version=1,
            fetched_at=past - timedelta(hours=11),
            expires_at=past,
        )
        e5_db.add(entry)
        e5_db.commit()

        result = cm.get("expired2", "global", require_valid=False)
        assert result is not None
        assert result["old"] is True

    def test_schema_version_stored(self, e5_db):
        from signals.external_cache import CacheManager, ExternalDataCache
        from sqlalchemy import select

        cm = CacheManager(e5_db)
        cm.upsert("versioned", "global", {"x": 1}, schema_version=3, ttl_hours=12)
        e5_db.commit()

        entry = e5_db.scalars(
            select(ExternalDataCache).where(ExternalDataCache.provider == "versioned")
        ).first()
        assert entry.schema_version == 3

    def test_get_all_status(self, e5_db):
        from signals.external_cache import CacheManager

        cm = CacheManager(e5_db)
        cm.upsert("prov_a", "global", {"a": 1}, ttl_hours=12)
        cm.upsert("prov_b", "global", {"b": 2}, ttl_hours=12)
        e5_db.commit()

        statuses = cm.get_all_status()
        assert len(statuses) == 2
        for s in statuses:
            assert "provider" in s
            assert "cached" in s
            assert "schema_version" in s
            assert "expires_in_minutes" in s
            assert s["is_valid"] is True

    def test_corrupt_json_returns_none(self, e5_db):
        from signals.external_cache import CacheManager, ExternalDataCache

        cm = CacheManager(e5_db)
        entry = ExternalDataCache(
            provider="corrupt",
            data_key="global",
            data_json="NOT VALID JSON{{{",
            schema_version=1,
            fetched_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        e5_db.add(entry)
        e5_db.commit()

        result = cm.get("corrupt", "global")
        assert result is None


# =========================================================================
# 3. External Detectors
# =========================================================================


class TestNewsDetector:
    """Test NewsDisruptionDetector."""

    def _populate_cache(self, db, events):
        from signals.external_cache import CacheManager

        cm = CacheManager(db)
        cm.upsert(
            "news_synthetic",
            "global",
            {
                "events": events,
                "fetched_at": int(time.time()),
                "provider": "news_synthetic",
            },
        )
        db.commit()

    def test_disruption_triggers(self, e5_db):
        from signals.external_detectors import NewsDisruptionDetector

        self._populate_cache(
            e5_db,
            [
                {
                    "headline": "Port strike",
                    "category": "logistics",
                    "relevance_score": 70,
                    "source": "test",
                }
            ],
        )
        detector = NewsDisruptionDetector()
        # Create a mock twin
        signals = detector.evaluate(_mock_twin(), e5_db)
        assert len(signals) == 1
        assert signals[0].source == "NewsDisruption"
        assert abs(signals[0].severity - 0.7) < 0.01

    def test_low_relevance_no_trigger(self, e5_db):
        from signals.external_detectors import NewsDisruptionDetector

        self._populate_cache(
            e5_db,
            [
                {
                    "headline": "Normal news",
                    "category": "general",
                    "relevance_score": 20,
                    "source": "test",
                }
            ],
        )
        signals = NewsDisruptionDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 0

    def test_no_cache_returns_empty(self, e5_db):
        from signals.external_detectors import NewsDisruptionDetector

        signals = NewsDisruptionDetector().evaluate(_mock_twin(), e5_db)
        assert signals == []

    def test_multiple_events(self, e5_db):
        from signals.external_detectors import NewsDisruptionDetector

        self._populate_cache(
            e5_db,
            [
                {
                    "headline": "Strike",
                    "category": "logistics",
                    "relevance_score": 60,
                    "source": "t",
                },
                {
                    "headline": "Fire",
                    "category": "supply",
                    "relevance_score": 80,
                    "source": "t",
                },
                {
                    "headline": "Peace",
                    "category": "general",
                    "relevance_score": 10,
                    "source": "t",
                },
            ],
        )
        signals = NewsDisruptionDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 2  # 60 and 80, not 10


class TestWeatherDetector:
    """Test WeatherAlertDetector."""

    def _populate_cache(self, db, condition, severity_level, base_severity=0.0):
        from signals.external_cache import CacheManager

        cm = CacheManager(db)
        cm.upsert(
            "weather_synthetic",
            "global",
            {
                "condition": condition,
                "severity_level": severity_level,
                "base_severity": base_severity,
                "temperature_c": 30.0,
                "wind_speed_kmh": 50.0,
                "region": "global",
            },
        )
        db.commit()

    def test_severe_triggers(self, e5_db):
        from signals.external_detectors import WeatherAlertDetector

        self._populate_cache(e5_db, "Severe Storm", "severe")
        signals = WeatherAlertDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 1
        assert signals[0].severity == 0.7

    def test_extreme_triggers(self, e5_db):
        from signals.external_detectors import WeatherAlertDetector

        self._populate_cache(e5_db, "Hurricane", "extreme")
        signals = WeatherAlertDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 1
        assert signals[0].severity == 1.0

    def test_moderate_triggers(self, e5_db):
        from signals.external_detectors import WeatherAlertDetector

        self._populate_cache(e5_db, "Thunderstorm", "moderate")
        signals = WeatherAlertDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 1
        assert signals[0].severity == 0.4

    def test_normal_no_trigger(self, e5_db):
        from signals.external_detectors import WeatherAlertDetector

        self._populate_cache(e5_db, "Clear", "normal")
        signals = WeatherAlertDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 0

    def test_minor_no_trigger(self, e5_db):
        from signals.external_detectors import WeatherAlertDetector

        self._populate_cache(e5_db, "Rain", "minor")
        signals = WeatherAlertDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 0

    def test_no_cache_returns_empty(self, e5_db):
        from signals.external_detectors import WeatherAlertDetector

        signals = WeatherAlertDetector().evaluate(_mock_twin(), e5_db)
        assert signals == []


class TestCommodityDetector:
    """Test CommodityShockDetector."""

    def _populate_cache(self, db, commodities):
        from signals.external_cache import CacheManager

        cm = CacheManager(db)
        cm.upsert(
            "commodity_synthetic",
            "global",
            {
                "commodities": commodities,
                "fetched_at": int(time.time()),
                "provider": "commodity_synthetic",
            },
        )
        db.commit()

    def test_spike_triggers(self, e5_db):
        from signals.external_detectors import CommodityShockDetector

        self._populate_cache(
            e5_db,
            [
                {
                    "commodity": "Steel",
                    "baseline_price": 800,
                    "current_price": 960,
                    "change_pct": 20.0,
                }
            ],
        )
        signals = CommodityShockDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 1
        # severity = 20/30 ≈ 0.6667
        assert abs(signals[0].severity - 0.6667) < 0.01

    def test_stable_no_trigger(self, e5_db):
        from signals.external_detectors import CommodityShockDetector

        self._populate_cache(
            e5_db,
            [
                {
                    "commodity": "Steel",
                    "baseline_price": 800,
                    "current_price": 840,
                    "change_pct": 5.0,
                }
            ],
        )
        signals = CommodityShockDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 0

    def test_max_severity_capped(self, e5_db):
        from signals.external_detectors import CommodityShockDetector

        self._populate_cache(
            e5_db,
            [
                {
                    "commodity": "Oil",
                    "baseline_price": 75,
                    "current_price": 150,
                    "change_pct": 100.0,
                }
            ],
        )
        signals = CommodityShockDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 1
        assert signals[0].severity == 1.0

    def test_no_cache_returns_empty(self, e5_db):
        from signals.external_detectors import CommodityShockDetector

        signals = CommodityShockDetector().evaluate(_mock_twin(), e5_db)
        assert signals == []


class TestEconomicDetector:
    """Test EconomicShiftDetector."""

    def _populate_cache(self, db, pmi, inflation):
        from signals.external_cache import CacheManager

        cm = CacheManager(db)
        cm.upsert(
            "economic_synthetic",
            "global",
            {
                "indicators": {
                    "pmi": pmi,
                    "inflation_pct": inflation,
                    "consumer_confidence": 100,
                },
            },
        )
        db.commit()

    def test_pmi_contraction(self, e5_db):
        from signals.external_detectors import EconomicShiftDetector

        self._populate_cache(e5_db, pmi=40.0, inflation=2.0)
        signals = EconomicShiftDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 1
        assert signals[0].payload["indicator"] == "pmi"
        # severity = (50-40)/20 = 0.5
        assert abs(signals[0].severity - 0.5) < 0.01

    def test_high_inflation(self, e5_db):
        from signals.external_detectors import EconomicShiftDetector

        self._populate_cache(e5_db, pmi=55.0, inflation=7.0)
        signals = EconomicShiftDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 1
        assert signals[0].payload["indicator"] == "inflation"
        # severity = (7-3)/5 = 0.8
        assert abs(signals[0].severity - 0.8) < 0.01

    def test_both_trigger(self, e5_db):
        from signals.external_detectors import EconomicShiftDetector

        self._populate_cache(e5_db, pmi=38.0, inflation=6.5)
        signals = EconomicShiftDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 2
        indicators = {s.payload["indicator"] for s in signals}
        assert indicators == {"pmi", "inflation"}

    def test_healthy_economy_no_trigger(self, e5_db):
        from signals.external_detectors import EconomicShiftDetector

        self._populate_cache(e5_db, pmi=52.0, inflation=2.5)
        signals = EconomicShiftDetector().evaluate(_mock_twin(), e5_db)
        assert len(signals) == 0

    def test_no_cache_returns_empty(self, e5_db):
        from signals.external_detectors import EconomicShiftDetector

        signals = EconomicShiftDetector().evaluate(_mock_twin(), e5_db)
        assert signals == []


# =========================================================================
# 4. Signal Weight Registration
# =========================================================================


class TestSignalWeights:
    """Verify E5 weights registered in forecasting engine."""

    def test_all_external_weights_registered(self):
        from forecasting.engine import SIGNAL_CONFIDENCE_WEIGHTS

        assert "NewsDisruption" in SIGNAL_CONFIDENCE_WEIGHTS
        assert "WeatherAlert" in SIGNAL_CONFIDENCE_WEIGHTS
        assert "CommodityShock" in SIGNAL_CONFIDENCE_WEIGHTS
        assert "EconomicShift" in SIGNAL_CONFIDENCE_WEIGHTS

    def test_weight_values(self):
        from forecasting.engine import SIGNAL_CONFIDENCE_WEIGHTS

        assert SIGNAL_CONFIDENCE_WEIGHTS["NewsDisruption"] == 0.06
        assert SIGNAL_CONFIDENCE_WEIGHTS["WeatherAlert"] == 0.10
        assert SIGNAL_CONFIDENCE_WEIGHTS["CommodityShock"] == 0.08
        assert SIGNAL_CONFIDENCE_WEIGHTS["EconomicShift"] == 0.05

    def test_weather_in_risk_elevation(self):
        from forecasting.engine import RISK_ELEVATION_SOURCES

        assert "WeatherAlert" in RISK_ELEVATION_SOURCES

    def test_total_weight_count(self):
        from forecasting.engine import SIGNAL_CONFIDENCE_WEIGHTS

        assert len(SIGNAL_CONFIDENCE_WEIGHTS) == 13  # 4 E3 + 4 E5 + 5 E6

    def test_e3_weights_unchanged(self):
        from forecasting.engine import SIGNAL_CONFIDENCE_WEIGHTS

        assert SIGNAL_CONFIDENCE_WEIGHTS["DemandSpike"] == 0.10
        assert SIGNAL_CONFIDENCE_WEIGHTS["SupplierDegradation"] == 0.15
        assert SIGNAL_CONFIDENCE_WEIGHTS["WarehouseOverload"] == 0.08
        assert SIGNAL_CONFIDENCE_WEIGHTS["TrendShift"] == 0.00


# =========================================================================
# 5. Detector Registry
# =========================================================================


class TestDetectorRegistry:
    """Verify external detectors registered in ALL_DETECTORS."""

    def test_all_detectors_count(self):
        from signals.detectors import ALL_DETECTORS

        assert len(ALL_DETECTORS) == 8  # 4 internal + 4 external

    def test_external_detectors_present(self):
        from signals.detectors import ALL_DETECTORS
        from signals.external_detectors import (
            CommodityShockDetector,
            EconomicShiftDetector,
            NewsDisruptionDetector,
            WeatherAlertDetector,
        )

        detector_types = [
            type(d) if not isinstance(d, type) else d for d in ALL_DETECTORS
        ]
        assert NewsDisruptionDetector in detector_types
        assert WeatherAlertDetector in detector_types
        assert CommodityShockDetector in detector_types
        assert EconomicShiftDetector in detector_types


# =========================================================================
# 6. Scheduler
# =========================================================================


class TestScheduler:
    """Test synchronous refresh_all_providers."""

    def test_refresh_all_populates_cache(self, e5_db):
        from signals.external_cache import CacheManager
        from signals.scheduler import refresh_all_providers

        results = refresh_all_providers(e5_db, mode="synthetic", ttl_hours=12)

        assert results["news"] is True
        assert results["weather"] is True
        assert results["commodity"] is True
        assert results["economic"] is True

        cm = CacheManager(e5_db)
        assert cm.get("news_synthetic", "global") is not None
        assert cm.get("weather_synthetic", "global") is not None
        assert cm.get("commodity_synthetic", "global") is not None
        assert cm.get("economic_synthetic", "global") is not None

    def test_refresh_is_idempotent(self, e5_db):
        from signals.external_cache import CacheManager
        from signals.scheduler import refresh_all_providers

        refresh_all_providers(e5_db, mode="synthetic", ttl_hours=12)
        refresh_all_providers(e5_db, mode="synthetic", ttl_hours=12)

        cm = CacheManager(e5_db)
        statuses = cm.get_all_status()
        assert len(statuses) == 4  # No duplicates


# =========================================================================
# 7. Integration: External signals flow into forecast
# =========================================================================


class TestE5ForecastIntegration:
    """Test that external signals affect forecast confidence."""

    def test_weather_signal_lowers_confidence(self):
        from forecasting.engine import compute_signal_penalty

        signals = [{"source": "WeatherAlert", "severity": 0.7}]
        penalty, details = compute_signal_penalty(signals)
        assert abs(penalty - 0.07) < 0.001  # 0.10 × 0.7

    def test_news_signal_penalty(self):
        from forecasting.engine import compute_signal_penalty

        signals = [{"source": "NewsDisruption", "severity": 0.8}]
        penalty, details = compute_signal_penalty(signals)
        assert abs(penalty - 0.048) < 0.001  # 0.06 × 0.8

    def test_commodity_signal_penalty(self):
        from forecasting.engine import compute_signal_penalty

        signals = [{"source": "CommodityShock", "severity": 0.5}]
        penalty, details = compute_signal_penalty(signals)
        assert abs(penalty - 0.04) < 0.001  # 0.08 × 0.5

    def test_economic_signal_penalty(self):
        from forecasting.engine import compute_signal_penalty

        signals = [{"source": "EconomicShift", "severity": 0.6}]
        penalty, details = compute_signal_penalty(signals)
        assert abs(penalty - 0.03) < 0.001  # 0.05 × 0.6

    def test_weather_elevates_risk(self):
        from forecasting.engine import compute_risk_elevation

        risk, elevated, source = compute_risk_elevation(
            "Low", [{"source": "WeatherAlert", "severity": 0.7}]
        )
        assert risk == "Medium"
        assert elevated is True

    def test_weather_below_threshold_no_elevation(self):
        from forecasting.engine import compute_risk_elevation

        risk, elevated, _ = compute_risk_elevation(
            "Low", [{"source": "WeatherAlert", "severity": 0.3}]
        )
        assert risk == "Low"
        assert elevated is False

    def test_all_external_signals_combined(self):
        from forecasting.engine import compute_signal_penalty

        signals = [
            {"source": "NewsDisruption", "severity": 1.0},
            {"source": "WeatherAlert", "severity": 1.0},
            {"source": "CommodityShock", "severity": 1.0},
            {"source": "EconomicShift", "severity": 1.0},
        ]
        penalty, details = compute_signal_penalty(signals)
        expected = 0.06 + 0.10 + 0.08 + 0.05  # 0.29
        assert abs(penalty - expected) < 0.001


# =========================================================================
# Mock helper
# =========================================================================


class _MockTwin:
    """Minimal twin mock for detector evaluate() calls."""

    id = 1
    name = "test-twin"


def _mock_twin():
    return _MockTwin()
