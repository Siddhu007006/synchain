import type {
  SimulationInput,
  SimulationCreateResponse,
  SimulationDetailResponse,
  ScenarioResponse,
  SimulationSummary,
  ApiError,
  TwinSummary,
  TwinDetailResponse,
  TwinHistoryResponse,
  ForecastResponse,
  ForecastRecordsResponse,
  ForecastSummaryResponse,
  SignalListResponse,
  SignalSummaryResponse,
  Company,
  CompanyListResponse,
  CompanyCreateRequest,
  CompanyUpdateRequest,
  CompanyTwinSummary,
  Product,
  ProductListResponse,
  ProductCreateRequest,
  ProductUpdateRequest,
  Supplier,
  SupplierListResponse,
  SupplierCreateRequest,
  SupplierUpdateRequest,
  CompanyWarehouse,
  WarehouseListResponse,
  WarehouseCreateRequest,
  WarehouseUpdateRequest,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ---------------------------------------------------------------------------
// Shared fetch helper
// ---------------------------------------------------------------------------
async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: `Server error (${res.status})` }));
    const detail = body?.detail;
    // Serialize object details (e.g. 409 with counts) so callers can parse them
    const message = typeof detail === "string"
      ? detail
      : `HTTP ${res.status}: ${JSON.stringify(detail)}`;
    throw new Error(message);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Simulation
// ---------------------------------------------------------------------------

/**
 * Run a supply chain simulation.
 * POST /simulate → returns { simulation_id, status }
 */
export async function runSimulation(
  input: SimulationInput
): Promise<SimulationCreateResponse> {
  return apiFetch<SimulationCreateResponse>(`${API_BASE}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

/**
 * Retrieve a completed simulation by ID.
 * GET /simulate/{id} → returns { simulation_id, input, result }
 */
export async function getSimulationResult(
  simulationId: number
): Promise<SimulationDetailResponse> {
  return apiFetch<SimulationDetailResponse>(`${API_BASE}/simulate/${simulationId}`);
}

/**
 * Run 4 what-if scenarios against a stored simulation.
 * GET /simulate/{id}/scenarios
 */
export async function getScenarioComparison(
  simulationId: number
): Promise<ScenarioResponse> {
  return apiFetch<ScenarioResponse>(`${API_BASE}/simulate/${simulationId}/scenarios`);
}

/**
 * List past simulation summaries (most recent first).
 * GET /simulations
 * V2.7: Optional company_id filter for company dashboards.
 */
export async function getSimulationHistory(
  limit: number = 20,
  companyId?: number
): Promise<SimulationSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (companyId != null) params.set("company_id", String(companyId));
  return apiFetch<SimulationSummary[]>(`${API_BASE}/simulations?${params}`);
}

// ---------------------------------------------------------------------------
// V2 — Companies
// ---------------------------------------------------------------------------

/** POST /companies → create a new company */
export async function createCompany(
  payload: CompanyCreateRequest
): Promise<Company> {
  return apiFetch<Company>(`${API_BASE}/companies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** GET /companies → list all companies for current org */
export async function listCompanies(
  limit = 50,
  offset = 0
): Promise<CompanyListResponse> {
  return apiFetch<CompanyListResponse>(
    `${API_BASE}/companies?limit=${limit}&offset=${offset}`
  );
}

/** GET /companies/{id} → get a single company */
export async function getCompany(companyId: number): Promise<Company> {
  return apiFetch<Company>(`${API_BASE}/companies/${companyId}`);
}

/** PATCH /companies/{id} → partial update */
export async function updateCompany(
  companyId: number,
  payload: CompanyUpdateRequest
): Promise<Company> {
  return apiFetch<Company>(`${API_BASE}/companies/${companyId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** PATCH /companies/{id}/archive → archive company (safe, preserves all data) */
export async function archiveCompany(companyId: number): Promise<{ id: number; name: string; is_archived: boolean; message: string }> {
  return apiFetch(`${API_BASE}/companies/${companyId}/archive`, { method: "PATCH" });
}

/** PATCH /companies/{id}/unarchive → restore archived company */
export async function unarchiveCompany(companyId: number): Promise<{ id: number; name: string; is_archived: boolean; message: string }> {
  return apiFetch(`${API_BASE}/companies/${companyId}/unarchive`, { method: "PATCH" });
}

// ---------------------------------------------------------------------------
// E1 — Digital Twin
// ---------------------------------------------------------------------------

/** POST /twins → create a new twin (optionally owned by a company) */
export async function createTwin(
  name: string,
  companyId?: number | null
): Promise<TwinSummary> {
  return apiFetch<TwinSummary>(`${API_BASE}/twins`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, company_id: companyId ?? null }),
  });
}

/** GET /twins → list all twins, optionally filtered by company_id */
export async function listTwins(companyId?: number | null): Promise<TwinSummary[]> {
  const url = companyId != null
    ? `${API_BASE}/twins?company_id=${companyId}`
    : `${API_BASE}/twins`;
  return apiFetch<TwinSummary[]>(url);
}

/** GET /companies/{id}/twins → enriched twin list owned by company */
export async function listCompanyTwins(
  companyId: number
): Promise<CompanyTwinSummary[]> {
  return apiFetch<CompanyTwinSummary[]>(`${API_BASE}/companies/${companyId}/twins`);
}

/** POST /companies/{id}/twins → create twin owned by company */
export async function createCompanyTwin(
  companyId: number,
  name: string
): Promise<CompanyTwinSummary> {
  return apiFetch<CompanyTwinSummary>(`${API_BASE}/companies/${companyId}/twins`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

// ---------------------------------------------------------------------------
// V2.3 — Products
// ---------------------------------------------------------------------------

/**
 * GET /companies/{id}/products
 *
 * V2.4 note: each product carries current_stock and avg_monthly_demand.
 * The simulation form will use these to auto-populate stock and demand
 * when a product is selected — no additional API calls needed.
 */
export async function listCompanyProducts(
  companyId: number,
  limit = 100,
  offset = 0
): Promise<ProductListResponse> {
  return apiFetch<ProductListResponse>(
    `${API_BASE}/companies/${companyId}/products?limit=${limit}&offset=${offset}`
  );
}

/** POST /companies/{id}/products → create product */
export async function createProduct(
  companyId: number,
  payload: ProductCreateRequest
): Promise<Product> {
  return apiFetch<Product>(`${API_BASE}/companies/${companyId}/products`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** GET /companies/{id}/products/{productId} → single product */
export async function getProduct(
  companyId: number,
  productId: number
): Promise<Product> {
  return apiFetch<Product>(`${API_BASE}/companies/${companyId}/products/${productId}`);
}

/** PATCH /companies/{id}/products/{productId} → partial update */
export async function updateProduct(
  companyId: number,
  productId: number,
  payload: ProductUpdateRequest
): Promise<Product> {
  return apiFetch<Product>(
    `${API_BASE}/companies/${companyId}/products/${productId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
}

/** DELETE /companies/{id}/products/{productId} */
export async function deleteProduct(
  companyId: number,
  productId: number
): Promise<void> {
  return apiFetch<void>(
    `${API_BASE}/companies/${companyId}/products/${productId}`,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// V2.5 — Suppliers
// ---------------------------------------------------------------------------

export async function listCompanySuppliers(companyId: number): Promise<SupplierListResponse> {
  return apiFetch<SupplierListResponse>(`${API_BASE}/companies/${companyId}/suppliers`);
}

export async function createSupplier(companyId: number, payload: SupplierCreateRequest): Promise<Supplier> {
  return apiFetch<Supplier>(`${API_BASE}/companies/${companyId}/suppliers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateSupplier(companyId: number, supplierId: number, payload: SupplierUpdateRequest): Promise<Supplier> {
  return apiFetch<Supplier>(`${API_BASE}/companies/${companyId}/suppliers/${supplierId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteSupplier(companyId: number, supplierId: number): Promise<void> {
  return apiFetch<void>(`${API_BASE}/companies/${companyId}/suppliers/${supplierId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// V2.5 — Warehouses
// ---------------------------------------------------------------------------

export async function listCompanyWarehouses(companyId: number): Promise<WarehouseListResponse> {
  return apiFetch<WarehouseListResponse>(`${API_BASE}/companies/${companyId}/warehouses`);
}

export async function createWarehouse(companyId: number, payload: WarehouseCreateRequest): Promise<CompanyWarehouse> {
  return apiFetch<CompanyWarehouse>(`${API_BASE}/companies/${companyId}/warehouses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateWarehouse(companyId: number, warehouseDbId: number, payload: WarehouseUpdateRequest): Promise<CompanyWarehouse> {
  return apiFetch<CompanyWarehouse>(`${API_BASE}/companies/${companyId}/warehouses/${warehouseDbId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteWarehouse(companyId: number, warehouseDbId: number): Promise<void> {
  return apiFetch<void>(`${API_BASE}/companies/${companyId}/warehouses/${warehouseDbId}`, { method: "DELETE" });
}

/** GET /twins/{id} → full twin state */
export async function getTwin(twinId: number): Promise<TwinDetailResponse> {
  return apiFetch<TwinDetailResponse>(`${API_BASE}/twins/${twinId}`);
}

/** GET /twins/{id}/history → state change history */
export async function getTwinHistory(
  twinId: number,
  limit = 100,
  offset = 0
): Promise<TwinHistoryResponse> {
  return apiFetch<TwinHistoryResponse>(
    `${API_BASE}/twins/${twinId}/history?limit=${limit}&offset=${offset}`
  );
}

// ---------------------------------------------------------------------------
// E2 — Forecasting
// ---------------------------------------------------------------------------

/** GET /twins/{id}/forecast?product=X&horizons=1,3,5 */
export async function getTwinForecast(
  twinId: number,
  product: string,
  horizons = "1,3,5"
): Promise<ForecastResponse> {
  const params = new URLSearchParams({ product, horizons });
  return apiFetch<ForecastResponse>(`${API_BASE}/twins/${twinId}/forecast?${params}`);
}

/** GET /twins/{id}/forecasts → audit trail */
export async function getTwinForecastRecords(
  twinId: number,
  limit = 50,
  offset = 0
): Promise<ForecastRecordsResponse> {
  return apiFetch<ForecastRecordsResponse>(
    `${API_BASE}/twins/${twinId}/forecasts?limit=${limit}&offset=${offset}`
  );
}

/** GET /twins/{id}/forecast/summary → per-product summary */
export async function getTwinForecastSummary(
  twinId: number
): Promise<ForecastSummaryResponse> {
  return apiFetch<ForecastSummaryResponse>(`${API_BASE}/twins/${twinId}/forecast/summary`);
}

// ---------------------------------------------------------------------------
// E3 / E5 / E6 — Signals
// ---------------------------------------------------------------------------

/** GET /twins/{id}/signals → list signals with optional filters */
export async function getTwinSignals(
  twinId: number,
  params?: { signal_type?: string; min_severity?: number; limit?: number }
): Promise<SignalListResponse> {
  const qs = new URLSearchParams();
  if (params?.signal_type) qs.set("signal_type", params.signal_type);
  if (params?.min_severity != null) qs.set("min_severity", String(params.min_severity));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  const query = qs.toString() ? `?${qs}` : "";
  return apiFetch<SignalListResponse>(`${API_BASE}/twins/${twinId}/signals${query}`);
}

/** GET /twins/{id}/signals/summary → health score + counts */
export async function getTwinSignalSummary(
  twinId: number
): Promise<SignalSummaryResponse> {
  return apiFetch<SignalSummaryResponse>(`${API_BASE}/twins/${twinId}/signals/summary`);
}

// ---------------------------------------------------------------------------
// V2.6 — CSV Import
// ---------------------------------------------------------------------------

import type {
  ImportPreviewResponse,
  ImportResultResponse,
  ImportJobListResponse,
  ImportEntityType,
} from "./types";

/**
 * Upload a CSV file for preview (dry_run=true) or import (dry_run=false).
 *
 * Uses FormData because we're uploading a file, not sending JSON.
 */
async function importCSV<T>(
  companyId: number,
  entityType: ImportEntityType,
  file: File,
  dryRun: boolean
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(
    `${API_BASE}/companies/${companyId}/import/${entityType}?dry_run=${dryRun}`,
    { method: "POST", body: formData }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Server error (${res.status})` }));
    throw new Error(err.detail);
  }
  return res.json();
}

/** Preview CSV import (validate only, no DB writes) */
export async function previewImport(
  companyId: number,
  entityType: ImportEntityType,
  file: File
): Promise<ImportPreviewResponse> {
  return importCSV<ImportPreviewResponse>(companyId, entityType, file, true);
}

/** Execute CSV import (upsert valid rows into DB) */
export async function executeImport(
  companyId: number,
  entityType: ImportEntityType,
  file: File
): Promise<ImportResultResponse> {
  return importCSV<ImportResultResponse>(companyId, entityType, file, false);
}

/** GET /companies/{id}/imports → import history */
export async function listImportJobs(
  companyId: number,
  limit = 20
): Promise<ImportJobListResponse> {
  return apiFetch<ImportJobListResponse>(
    `${API_BASE}/companies/${companyId}/imports?limit=${limit}`
  );
}

/** Download CSV template for an entity type */
export function downloadTemplate(entityType: ImportEntityType): void {
  const url = `${API_BASE}/companies/templates/${entityType}.csv`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `${entityType}_template.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

