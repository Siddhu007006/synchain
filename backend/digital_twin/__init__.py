"""
Digital Twin state layer for SynChain.

Provides persistent, evolving state that enriches agent decisions
with historical context via EWMA-smoothed metrics.

Modules:
  - models.py:      SQLAlchemy ORM (6 state tables + history + signal_events)
  - schemas.py:     Pydantic request/response schemas for twin API
  - manager.py:     TwinManager service (CRUD + EWMA state updates)
  - math_utils.py:  EWMA smoothing, trend detection
"""
