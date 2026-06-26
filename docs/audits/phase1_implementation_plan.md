# Implementation Plan — SynChain Stabilization Sprint Phase 1: Critical Production Security

Phase 1 focus: Hardening production authentication, applying rate limiting to core endpoints, resolving the CSV import route collision (removing shadowed routes), and ensuring file upload protection constraints.

## User Review Required

> [!IMPORTANT]
> - **Removal of Route Shadowing**: The endpoints in `csv_import.py` (registered directly on `/companies/{id}/import/...` without prefix) will be removed in favor of the dynamic import route in `import_router.py` (`/companies/{id}/import/{entity_type}`).
> - **Production Config Hardening**: In production (`DEBUG=false`), the server will trigger a startup failure if `JWT_SECRET_KEY` is missing or matches the default development fallback key (`synchain-dev-only-not-for-production`).
> - **Audit Script Alignment**: `run_full_audit.py` will be updated to hit the dynamic import endpoint with `?dry_run=false` to reflect the clean route architecture and assert the correct `success` / `failed` fields in the response.

## Open Questions

None. The requirements for removing fallback secrets, adding rate limiting, and de-duplicating the import endpoints are precise.

---

## Proposed Changes

We will modify the backend authentication, routing, and verification files.

### Configuration & Dependencies

#### [MODIFY] [config.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/config.py)
- Enforce that if `settings.debug` is `False`, the `jwt_secret_key` must be provided and must not equal the development key `synchain-dev-only-not-for-production`.
- Raise `RuntimeError` to crash the process on startup if the key is missing or set to the fallback.

#### [MODIFY] [dependencies.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/auth/dependencies.py)
- Inject `request.state.user_id = user.id` inside `get_current_user` for both the standard authentication path and the `debug` auth bypass path. This enables the rate limiter to track authenticated requests per user ID.

---

### Authentication Router & Rate Limiting

#### [MODIFY] [router.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/auth/router.py)
- Import `rate_limit` dependency from `rate_limiter.py`.
- Apply `Depends(rate_limit("auth"))` to registration (`POST /auth/register`), login (`POST /auth/login`), and token refresh (`POST /auth/refresh`) routes.

---

### Simulation Endpoint & App Mounting

#### [MODIFY] [main.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/main.py)
- Import `rate_limit` dependency from `rate_limiter.py`.
- Apply `Depends(rate_limit("write"))` to both the `v1.post("/simulate")` and the `legacy.post("/simulate")` endpoints.
- Remove legacy router imports and mountings for `csv_import_router` (de-registering the shadowed `/companies/{id}/import/...` specific endpoints).

---

### CSV Import Components

#### [MODIFY] [csv_import.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/company/csv_import.py)
- Delete the `router = APIRouter(...)` instantiation.
- Remove all `@router.post` handlers and route functions (`import_products`, `import_suppliers`, `import_warehouses`).
- Retain all parsing, header checking, validation, and database upsert functions as helper utilities (`parse_csv_bytes`, `check_headers`, `VALIDATORS`, `UPSERTERS`, etc.) since they are imported and utilized by `import_router.py`.

#### [MODIFY] [import_router.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/company/import_router.py)
- Import `rate_limit` from `rate_limiter.py`.
- Apply `Depends(rate_limit("write"))` to the dynamic CSV import endpoint `POST /{company_id}/import/{entity_type}`.
- Wrap the core parsing and validation calls in a comprehensive `try...except Exception` block, ensuring that any unhandled parser exceptions raise a clean, client-facing `ValidationError` (HTTP 422) instead of a raw 500 error.
- Enforce the 1MB `MAX_FILE_SIZE` limitation.

---

### Verification and Test Scripts

#### [MODIFY] [run_full_audit.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/run_full_audit.py)
- Adjust the CSV import POST calls to target the dynamic endpoint `/api/v1/companies/{COMPANY_ID}/import/{entity_type}?dry_run=false`.
- Update assertions on the response schemas (checking `success == 3` or `success == 2` instead of `imported`).

#### [MODIFY] [test_e9_production.py](file:///c:/Users/Siddharth%20Reddy/projects/Synchain/backend/tests/test_e9_production.py)
- Add new automated test cases to verify route-level rate limiting (returning HTTP 429) for the login, register, and simulate routes by mocking low limits and issuing sequential calls via the test client.

---

## Verification Plan

We will perform automated test execution and database verification.

### Automated Tests
- Run the full test suite using `pytest` to ensure all existing security and pipeline tests remain green.
- Run `python run_full_audit.py` to verify backend compatibility and empty-database startup readiness.

### Manual Verification
- Start the server with `DEBUG=false` and verify startup crashes when `JWT_SECRET_KEY` is not set.
- Send requests without token when `DEBUG=false` and verify it returns HTTP 401.
