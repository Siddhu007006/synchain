# TD3: Rewrite Baseline Alembic Migration for Clean-Slate Deployment

**Priority:** Medium  
**Phase:** Pre-Production  
**Blocking:** No (does not block E2/E3)  
**Created:** 2026-06-04  
**Source:** E1 Completion Audit (M2)

## Problem

The baseline Alembic migration (`dec3154b1634_baseline_schema.py`) uses `batch_alter_table('simulations')` which requires the `simulations` table to already exist. On a clean database (no pre-existing tables), this fails with `NoSuchTableError: simulations`.

Currently, the dev database works because tables were created by `Base.metadata.create_all()` before the migration was stamped. This means Alembic cannot bootstrap a fresh database from scratch.

## Root Cause

The baseline migration was written as a *diff migration* (adding columns to existing tables) rather than a *create-from-scratch* migration. This happened because the migration was created after the tables already existed via `create_all`.

## Required Fix

1. Rewrite `dec3154b1634_baseline_schema.py` to:
   - CREATE `simulations` and `results` tables from scratch (not ALTER)
   - Use `op.create_table()` instead of `batch_alter_table()`
2. Ensure `a7b2c3d4e5f6_digital_twin_tables.py` (E1 migration) applies cleanly on top
3. Verify full upgrade path: `empty DB → dec3154b1634 → a7b2c3d4e5f6 → head`
4. Verify downgrade path: `head → dec3154b1634 → empty`

## Acceptance Criteria

- [ ] `alembic upgrade head` succeeds on a completely empty SQLite database
- [ ] `alembic downgrade base` succeeds from head
- [ ] All 83+ tests still pass after migration rewrite
- [ ] Dev database remains functional (no data loss)

## Files Affected

- `backend/alembic/versions/dec3154b1634_baseline_schema.py`
