# TD4: Data Retention & Archival Strategy

**Priority:** Low  
**Phase:** Pre-Production  
**Blocking:** No (does not block E3/E4/E5)  
**Created:** 2026-06-04  
**Source:** E2 Completion Review  
**Status:** Tracked — DO NOT IMPLEMENT until trigger conditions are met

## Problem

Three data tables grow indefinitely with no retention policy:

| Table | Growth Rate | Primary Key |
|-------|------------|-------------|
| `twin_state_history` | ~8–15 rows per simulation | twin_id + changed_at |
| `forecast_records` | 3 rows per forecast call | twin_id + created_at |
| `simulations` + `results` | 1+1 rows per simulation | simulation_id |

## Growth Assumptions

### Current Volume (Development)
- ~50 simulations/day maximum (manual usage)
- ~15 history rows per simulation → ~750 history rows/day
- ~5 forecast calls/day → ~15 forecast rows/day
- **Annual estimate at current usage: ~275K history rows, ~5.5K forecast rows**

### Projected Volume (Production, Single User)
- ~200 simulations/day
- ~3,000 history rows/day → **~1.1M/year**
- ~50 forecast calls/day → **~55K/year**

### SQLite Capacity
- SQLite handles up to ~280TB databases; millions of rows are routine
- Performance degrades primarily on unindexed queries over >10M rows
- Current indexes: `twin_id`, `changed_at`, `created_at`, `product_name`

**Conclusion:** At projected volumes, no retention policy is needed for 3–5 years.

## Retention Options (When Needed)

### Option A: Time-Based TTL
```sql
DELETE FROM twin_state_history WHERE changed_at < datetime('now', '-90 days');
DELETE FROM forecast_records WHERE created_at < datetime('now', '-180 days');
```
- **Pro:** Simple, predictable
- **Con:** Loses all old data regardless of value

### Option B: Count-Based Per Entity
```sql
-- Keep last 500 history entries per twin
DELETE FROM twin_state_history
WHERE id NOT IN (
  SELECT id FROM twin_state_history
  WHERE twin_id = ? ORDER BY changed_at DESC LIMIT 500
);
```
- **Pro:** Guarantees bounded growth per twin
- **Con:** More complex query, varies by twin activity level

### Option C: Archive to Separate Table
```sql
INSERT INTO twin_state_history_archive SELECT * FROM twin_state_history WHERE ...;
DELETE FROM twin_state_history WHERE ...;
```
- **Pro:** Data preserved for compliance/audit
- **Con:** Two-table complexity, archive also grows

### Option D: Aggregate + Prune
```sql
-- Summarize old history into daily/weekly summaries, then delete raw
INSERT INTO state_summary (twin_id, entity_type, period, avg_value, ...)
  SELECT ... FROM twin_state_history WHERE changed_at < ? GROUP BY ...;
DELETE FROM twin_state_history WHERE changed_at < ?;
```
- **Pro:** Retains analytical value, minimal storage
- **Con:** Most complex; requires summary schema design

## Trigger Conditions

Implement retention policy when ANY of these conditions are met:

| Trigger | Threshold | Measurement |
|---------|-----------|-------------|
| Total database size | > 500 MB | `PRAGMA page_count * PRAGMA page_size` |
| History table rows | > 5M rows | `SELECT COUNT(*) FROM twin_state_history` |
| Query latency | > 500ms for history queries | Application logging |
| Production deployment | Before first production release | Deployment checklist |

## Recommended Future Approach

1. **Short-term (when triggered):** Option A (time-based TTL) via a management command
2. **Medium-term (if audit required):** Option C (archive) for `forecast_records` only
3. **Long-term (multi-tenant):** Option D (aggregate + prune) with per-tenant policies

## Decision: DO NOT IMPLEMENT NOW

**Reason:** Current projected data volume is negligible and does not justify additional complexity. SQLite will handle projected growth for years without intervention. Premature optimization of storage adds code paths that must be tested, maintained, and can introduce bugs in production data.

## Files That Would Be Affected (Future)

- New: `backend/management/retention.py` (cleanup commands)
- Modified: `backend/digital_twin/models.py` (if archive tables needed)
- Modified: `backend/forecasting/models.py` (if archive tables needed)
- New: Alembic migration for any archive tables
