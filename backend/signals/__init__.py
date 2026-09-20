"""
Signal Intelligence layer for SynChain (Phase E3 + E5 + E6).

Monitors Digital Twin state changes and external world conditions,
emitting structured signals — discrete, typed observations about
supply chain conditions.

Modules:
  - detectors.py:          4 internal detectors (DemandSpike, SupplierDegradation,
                           WarehouseOverload, TrendShift)
  - external_detectors.py: 4 external detectors (NewsDisruption, WeatherAlert,
                           CommodityShock, EconomicShift)
  - compound.py:           5 compound rules (SupplyShock, FulfillmentCrisis,
                           MarketDisruption, PerfectStorm, CostSqueeze)
  - providers.py:          DataProvider ABC + synthetic provider implementations
  - external_cache.py:     ExternalDataCache model + CacheManager
  - scheduler.py:          Background refresh scheduler for external providers
  - engine.py:             SignalEngine orchestrator (runs all detectors + compounds)
  - schemas.py:            Pydantic response models for signal API endpoints

Design Principles:
  - Signals are read-only observers (never mutate twin state)
  - Each detector is independent (no cross-detector dependencies)
  - Internal detectors are pure functions (twin state → signals)
  - External detectors read from cache (never call APIs during evaluation)
  - Compound detectors read atomic signal outputs (never twin state directly)
  - Severity normalized to 0.0–1.0
  - Payloads are structured JSON
  - Additive penalty stacking: compound + atomic penalties accumulate
    (confidence floor at 0.10 prevents unbounded degradation)

Future:
  - Real API providers: swap synthetic for NewsAPI, OpenWeatherMap, etc.
"""
