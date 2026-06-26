/**
 * SynChain — Shared TypeScript types matching backend Pydantic schemas.
 *
 * Source of truth: backend/schemas.py
 */

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface SimulationInput {
  product: string;
  stock: number;
  warehouse: "W1" | "W2" | "W3";
  demand: number;
  supplier_delay: number;
  market_trend: "Positive" | "Neutral" | "Negative";
  supply_status: "High" | "Medium" | "Low";
  season: "Festival" | "Normal" | "Off-season";
  /** Optional Digital Twin ID. When provided, the simulation updates twin state
   *  and enables signal generation, forecasting, and compound intelligence. */
  twin_id?: number | null;
  /** V2.4: Optional product FK */
  product_id?: number | null;
  /** V2.4: Optional company FK */
  company_id?: number | null;
  /** V2.5: Optional supplier FK */
  supplier_id?: number | null;
  /** V2.5: Optional warehouse record FK */
  warehouse_record_id?: number | null;
}

// ---------------------------------------------------------------------------
// Agent Breakdown (Phase B)
// ---------------------------------------------------------------------------

export interface AgentBreakdownItem {
  agent_name: string;
  input_summary: Record<string, unknown>;
  output_data: Record<string, unknown>;
  confidence: number;
  explanation: string;
  execution_ms: number;
  status: "success" | "warning" | "failed";
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface SimulationCreateResponse {
  simulation_id: number;
  status: string;
}

export interface SimulationResult {
  demand_forecast: number;
  recommended_inventory: number;
  selected_warehouse: string;
  route: string;
  risk: string;
  strategy: string;
  agent_breakdown: AgentBreakdownItem[];
  overall_confidence: number;
  explanation: string;
}

export interface SimulationDetailResponse {
  simulation_id: number;
  input: SimulationInput;
  result: SimulationResult;
  /** V2.4 traceability — null for old simulations */
  product_id: number | null;
  product_name: string | null;
  company_id: number | null;
  company_name: string | null;
}

// ---------------------------------------------------------------------------
// Scenario types (Phase C)
// ---------------------------------------------------------------------------

export interface ScenarioImpact {
  demand_change: number;
  inventory_change: number;
  confidence_change: number;
  risk_change: string;
  recommendation_changed: boolean;
  warehouse_changed: boolean;
  route_changed: boolean;
}

export interface ScenarioResultSummary {
  demand_forecast: number;
  recommended_inventory: number;
  selected_warehouse: string;
  route: string;
  risk: string;
  overall_confidence: number;
  strategy: string;
}

export interface ScenarioComparison {
  scenario_name: string;
  scenario_description: string;
  modified_input: SimulationInput;
  result: ScenarioResultSummary;
  impact: ScenarioImpact;
}

export interface ScenarioResponse {
  simulation_id: number;
  base_result: ScenarioResultSummary;
  scenarios: ScenarioComparison[];
}

// ---------------------------------------------------------------------------
// History types (Phase C)
// ---------------------------------------------------------------------------

export interface SimulationSummary {
  simulation_id: number;
  product: string;
  warehouse: string;
  demand: number;
  risk: string | null;
  overall_confidence: number | null;
  demand_forecast: number | null;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string;
}

// ---------------------------------------------------------------------------
// Digital Twin types (E1)
// ---------------------------------------------------------------------------

export interface TwinSummary {
  id: number;
  name: string;
  simulation_count: number;
  company_id: number | null;
  created_at: string | null;
  updated_at: string | null;
}

/** Enriched twin summary returned by GET /companies/{id}/twins */
export interface CompanyTwinSummary {
  id: number;
  name: string;
  company_id: number | null;
  simulation_count: number;
  signal_count: number;
  health_score: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProductStateSnapshot {
  product_name: string;
  latest_stock: number;
  latest_demand: number;
  avg_demand: number;
  demand_trend: string;
  simulation_count: number;
  updated_at: string | null;
}

export interface WarehouseStateSnapshot {
  warehouse_id: string;
  times_selected: number;
  utilization_pct: number;
  selection_rate: number;
  avg_delivery_score: number;
  avg_risk_score: number;
  updated_at: string | null;
}

export interface SupplierStateSnapshot {
  avg_delay: number;
  max_delay_seen: number;
  reliability_score: number;
  supply_status_mode: string;
  updated_at: string | null;
}

export interface MarketStateSnapshot {
  trend_mode: string;
  season_mode: string;
  avg_confidence: number;
  avg_risk_score: number;
  updated_at: string | null;
}

export interface TwinDetailResponse {
  id: number;
  name: string;
  simulation_count: number;
  created_at: string | null;
  updated_at: string | null;
  product_states: ProductStateSnapshot[];
  warehouse_states: WarehouseStateSnapshot[];
  supplier_state: SupplierStateSnapshot | null;
  market_state: MarketStateSnapshot | null;
}

export interface StateHistoryEntry {
  id: number;
  entity_type: string;
  entity_id: string;
  field_name: string;
  old_value: string | null;
  new_value: string;
  changed_at: string | null;
}

export interface TwinHistoryResponse {
  twin_id: number;
  total_entries: number;
  entries: StateHistoryEntry[];
}

// ---------------------------------------------------------------------------
// Forecast types (E2)
// ---------------------------------------------------------------------------

export interface ForecastSourceState {
  avg_demand: number;
  demand_trend: string;
  simulation_count: number;
  season: string;
  supplier_reliability: number;
}

export interface ActiveSignalEntry {
  source: string;
  signal_type: string;
  severity: number;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface ForecastPointResponse {
  horizon: number;
  forecast_demand: number;
  trend_factor: number;
  season_factor: number;
  supply_risk: string;
  confidence: number;
  explanation: string;
}

export interface ForecastResponse {
  twin_id: number;
  product: string;
  generated_at: string;
  source_state: ForecastSourceState;
  forecasts: ForecastPointResponse[];
  active_signals: ActiveSignalEntry[];
}

export interface ForecastRecordEntry {
  id: number;
  product_name: string;
  horizon: number;
  forecast_demand: number;
  trend_factor: number;
  season_factor: number;
  supply_risk: string;
  confidence: number;
  explanation: string;
  source_avg_demand: number;
  source_trend: string;
  source_season: string;
  source_reliability: number;
  created_at: string | null;
}

export interface ForecastRecordsResponse {
  twin_id: number;
  total_records: number;
  records: ForecastRecordEntry[];
}

export interface LatestForecast {
  forecast_demand: number;
  confidence: number;
  supply_risk: string;
  generated_at: string | null;
}

export interface ProductForecastSummary {
  product: string;
  avg_demand: number;
  demand_trend: string;
  latest_forecast: LatestForecast | null;
}

export interface ForecastSummaryResponse {
  twin_id: number;
  products: ProductForecastSummary[];
}

// ---------------------------------------------------------------------------
// Company types (V2 Phase 1)
// ---------------------------------------------------------------------------

export interface Company {
  id: number;
  name: string;
  industry: string;
  country: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface CompanyListResponse {
  total: number;
  companies: Company[];
}

export interface CompanyCreateRequest {
  name: string;
  industry?: string;
  country?: string;
}

export interface CompanyUpdateRequest {
  name?: string;
  industry?: string;
  country?: string;
}

// ---------------------------------------------------------------------------
// Product types (V2.3)
// ---------------------------------------------------------------------------

export interface Product {
  id: number;
  company_id: number;
  name: string;
  category: string;
  /** Prefills SimulationInput.stock in V2.4 */
  current_stock: number;
  /** Prefills SimulationInput.demand in V2.4 */
  avg_monthly_demand: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProductListResponse {
  total: number;
  products: Product[];
}

export interface ProductCreateRequest {
  name: string;
  category?: string;
  current_stock?: number;
  avg_monthly_demand?: number;
}

export interface ProductUpdateRequest {
  name?: string;
  category?: string;
  current_stock?: number;
  avg_monthly_demand?: number;
}

// ---------------------------------------------------------------------------
// Supplier types (V2.5)
// ---------------------------------------------------------------------------

export interface Supplier {
  id: number;
  company_id: number;
  name: string;
  /** Prefills SimulationInput.supplier_delay */
  lead_time_days: number;
  /** Prefills SimulationInput.supply_status */
  supply_status: "High" | "Medium" | "Low";
  reliability_pct: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface SupplierListResponse {
  total: number;
  suppliers: Supplier[];
}

export interface SupplierCreateRequest {
  name: string;
  lead_time_days?: number;
  supply_status?: "High" | "Medium" | "Low";
  reliability_pct?: number;
}

export interface SupplierUpdateRequest {
  name?: string;
  lead_time_days?: number;
  supply_status?: "High" | "Medium" | "Low";
  reliability_pct?: number;
}

// ---------------------------------------------------------------------------
// Warehouse types (V2.5)
// ---------------------------------------------------------------------------

export interface CompanyWarehouse {
  id: number;
  company_id: number;
  name: string;
  /** Prefills SimulationInput.warehouse */
  warehouse_id: "W1" | "W2" | "W3";
  location: string;
  capacity: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface WarehouseListResponse {
  total: number;
  warehouses: CompanyWarehouse[];
}

export interface WarehouseCreateRequest {
  name: string;
  warehouse_id: "W1" | "W2" | "W3";
  location?: string;
  capacity?: number;
}

export interface WarehouseUpdateRequest {
  name?: string;
  warehouse_id?: "W1" | "W2" | "W3";
  location?: string;
  capacity?: number;
}

// ---------------------------------------------------------------------------
// Signal types (E3 / E5 / E6)
// ---------------------------------------------------------------------------

export interface SignalEventEntry {
  id: number;
  source: string;
  signal_type: string;
  severity: number;
  severity_label: "info" | "warning" | "critical";
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface SignalCountByType {
  demand: number;
  supply: number;
  risk: number;
  market: number;
  external: number;
  compound: number;
}

export interface SignalCountBySeverity {
  info: number;
  warning: number;
  critical: number;
}

export interface SignalListResponse {
  twin_id: number;
  total_signals: number;
  signals: SignalEventEntry[];
}

export interface SignalSummaryResponse {
  twin_id: number;
  total_signals: number;
  by_type: SignalCountByType;
  by_severity: SignalCountBySeverity;
  latest_critical: SignalEventEntry | null;
  health_score: number;
}

// ---------------------------------------------------------------------------
// CSV Import types (V2.6)
// ---------------------------------------------------------------------------

export interface ImportRowError {
  row: number;
  field: string;
  message: string;
}

export interface ImportPreviewRow {
  row: number;
  data: Record<string, unknown>;
  valid: boolean;
  errors: string[];
}

export interface ImportPreviewResponse {
  entity_type: string;
  file_name: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  preview: ImportPreviewRow[];
}

export interface ImportResultResponse {
  entity_type: string;
  file_name: string;
  total_rows: number;
  success: number;
  failed: number;
  created: number;
  updated: number;
  errors: ImportRowError[];
  job_id: number;
}

export interface ImportJob {
  id: number;
  entity_type: string;
  file_name: string;
  rows_processed: number;
  rows_success: number;
  rows_failed: number;
  created_at: string | null;
}

export interface ImportJobListResponse {
  total: number;
  imports: ImportJob[];
}

export type ImportEntityType = "products" | "suppliers" | "warehouses";

