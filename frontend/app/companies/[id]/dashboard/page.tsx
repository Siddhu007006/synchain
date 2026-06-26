"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Package,
  Truck,
  Warehouse,
  Cpu,
  Activity,
  Zap,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Shield,
  Play,
  Upload,
  Eye,
  Loader2,
  AlertCircle,
  Plus,
  Heart,
} from "lucide-react";
import {
  getCompany,
  listCompanyProducts,
  listCompanySuppliers,
  listCompanyWarehouses,
  listCompanyTwins,
  getTwinSignals,
  getTwinSignalSummary,
  getTwinForecast,
  getSimulationHistory,
} from "@/lib/api";
import type {
  Company,
  CompanyTwinSummary,
  Product,
  Supplier,
  CompanyWarehouse,
  SignalListResponse,
  SignalSummaryResponse,
  ForecastResponse,
  SimulationSummary,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatDate(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function healthColor(pct: number): string {
  if (pct >= 80) return "text-emerald-400";
  if (pct >= 50) return "text-amber-400";
  return "text-red-400";
}

function healthBg(pct: number): string {
  if (pct >= 80) return "bg-emerald-500";
  if (pct >= 50) return "bg-amber-500";
  return "bg-red-500";
}

function riskBadge(risk: string | null): string {
  if (!risk) return "text-muted-foreground";
  const r = risk.toLowerCase();
  if (r === "high" || r === "critical") return "text-red-400";
  if (r === "medium" || r === "warning") return "text-amber-400";
  return "text-emerald-400";
}

function severityLabel(sev: number): { text: string; color: string } {
  if (sev >= 0.8) return { text: "Critical", color: "text-red-400 bg-red-400/10 border-red-400/20" };
  if (sev >= 0.6) return { text: "High", color: "text-orange-400 bg-orange-400/10 border-orange-400/20" };
  if (sev >= 0.4) return { text: "Warning", color: "text-amber-400 bg-amber-400/10 border-amber-400/20" };
  return { text: "Info", color: "text-blue-400 bg-blue-400/10 border-blue-400/20" };
}

// ---------------------------------------------------------------------------
// Dashboard Section Card wrapper
// ---------------------------------------------------------------------------
function Section({
  title,
  icon: Icon,
  children,
  action,
  className = "",
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`border border-foreground/10 rounded-xl p-6 bg-foreground/[0.02] ${className}`}>
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-foreground/5 flex items-center justify-center">
            <Icon className="w-4 h-4 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-mono uppercase tracking-wider text-muted-foreground">
            {title}
          </h3>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------
function EmptyState({
  title,
  description,
  ctaLabel,
  ctaHref,
}: {
  title: string;
  description: string;
  ctaLabel: string;
  ctaHref: string;
}) {
  return (
    <div className="text-center py-8 px-4">
      <div className="w-12 h-12 rounded-xl bg-foreground/5 flex items-center justify-center mx-auto mb-3">
        <Plus className="w-5 h-5 text-muted-foreground" />
      </div>
      <div className="text-sm font-medium mb-1">{title}</div>
      <div className="text-xs text-muted-foreground mb-4">{description}</div>
      <Link href={ctaHref}>
        <Button variant="outline" size="sm" className="gap-1.5">
          {ctaLabel} <ArrowRight className="w-3 h-3" />
        </Button>
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metric Card
// ---------------------------------------------------------------------------
function MetricCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  accent?: string;
}) {
  return (
    <div className="border border-foreground/10 rounded-lg p-4 text-center">
      <div className="flex items-center justify-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${accent || "text-muted-foreground"}`} />
        <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div className={`text-2xl font-display ${accent || ""}`}>{value}</div>
    </div>
  );
}

// ===========================================================================
// Main Dashboard Component
// ===========================================================================
export default function CompanyDashboard() {
  const params = useParams();
  const router = useRouter();
  const companyId = Number(params.id);

  // Data state
  const [company, setCompany] = useState<Company | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [warehouses, setWarehouses] = useState<CompanyWarehouse[]>([]);
  const [twins, setTwins] = useState<CompanyTwinSummary[]>([]);
  const [recentSims, setRecentSims] = useState<SimulationSummary[]>([]);

  // Aggregated intelligence across all twins
  const [aggHealth, setAggHealth] = useState<number>(0);
  const [aggTotalSignals, setAggTotalSignals] = useState<number>(0);
  const [aggCriticalSignals, setAggCriticalSignals] = useState<number>(0);
  const [topSignals, setTopSignals] = useState<
    { name: string; severity: number; type: string; twin_name: string }[]
  >([]);

  // Forecast from primary twin (most simulations)
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [primaryTwinName, setPrimaryTwinName] = useState<string>("");

  // Loading / Error
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId || isNaN(companyId)) return;

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        // Parallel fetch all base data
        const [companyData, productsRes, suppliersRes, warehousesRes, twinsData, simsData] =
          await Promise.all([
            getCompany(companyId),
            listCompanyProducts(companyId),
            listCompanySuppliers(companyId),
            listCompanyWarehouses(companyId),
            listCompanyTwins(companyId),
            getSimulationHistory(5, companyId),
          ]);

        if (cancelled) return;

        setCompany(companyData);
        setProducts(productsRes.products);
        setSuppliers(suppliersRes.suppliers);
        setWarehouses(warehousesRes.warehouses);
        setTwins(twinsData);
        setRecentSims(simsData);

        // ── Aggregate intelligence across ALL twins ──
        if (twinsData.length > 0) {
          // Aggregate health: weighted by simulation_count
          const totalSims = twinsData.reduce((s, t) => s + t.simulation_count, 0);
          const weightedHealth =
            totalSims > 0
              ? twinsData.reduce(
                  (s, t) => s + t.health_score * t.simulation_count,
                  0
                ) / totalSims
              : twinsData.reduce((s, t) => s + t.health_score, 0) / twinsData.length;
          setAggHealth(Math.round(weightedHealth * 100));

          // Aggregate signal counts
          const totalSignals = twinsData.reduce((s, t) => s + t.signal_count, 0);
          setAggTotalSignals(totalSignals);

          // Fetch signals from each twin to get severity data
          const signalResults = await Promise.all(
            twinsData.map(async (t) => {
              try {
                const signals = await getTwinSignals(t.id, { limit: 20 });
                return { twin_name: t.name, signals };
              } catch {
                return { twin_name: t.name, signals: null };
              }
            })
          );

          if (cancelled) return;

          // Collect all signals, count critical, pick top 5
          const allSignals: { name: string; severity: number; type: string; twin_name: string }[] = [];
          let critical = 0;

          for (const { twin_name, signals } of signalResults) {
            if (!signals) continue;
            for (const sig of signals.signals || []) {
              allSignals.push({
                name: sig.signal_type || sig.source || "Unknown",
                severity: sig.severity ?? 0,
                type: sig.signal_type || "unknown",
                twin_name,
              });
              if ((sig.severity ?? 0) >= 0.8) critical++;
            }
          }

          setAggCriticalSignals(critical);
          // Top 5 by severity
          allSignals.sort((a, b) => b.severity - a.severity);
          setTopSignals(allSignals.slice(0, 5));

          // ── Forecast from primary twin (most simulations) ──
          const primaryTwin = [...twinsData].sort(
            (a, b) => b.simulation_count - a.simulation_count
          )[0];
          setPrimaryTwinName(primaryTwin.name);

          // Get forecast for first product with that twin
          if (productsRes.products.length > 0 && primaryTwin.simulation_count > 0) {
            try {
              const fc = await getTwinForecast(
                primaryTwin.id,
                productsRes.products[0].name
              );
              if (!cancelled) setForecast(fc);
            } catch {
              // Forecast not available — that's OK
            }
          }
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  // ─── Loading state ───
  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  // ─── Error state ───
  if (error || !company) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <div className="max-w-4xl mx-auto px-6 py-12 text-center">
          <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <div className="text-lg font-medium mb-2">Dashboard Error</div>
          <div className="text-sm text-muted-foreground">{error || "Company not found"}</div>
        </div>
      </div>
    );
  }

  const hasTwins = twins.length > 0;
  const hasProducts = products.length > 0;
  const hasSims = recentSims.length > 0;

  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* ── Header ── */}
        <div className="mb-8">
          <Link
            href={`/companies/${companyId}`}
            className="text-sm text-primary hover:underline inline-flex items-center gap-1.5 mb-4"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Company Details
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <div className="text-xs font-mono text-muted-foreground mb-1">
                COMPANY DASHBOARD
              </div>
              <h1 className="text-2xl sm:text-3xl font-display">{company.name}</h1>
              {(company.industry || company.country) && (
                <div className="text-sm text-muted-foreground mt-1">
                  {[company.industry, company.country].filter(Boolean).join(" \u00B7 ")}
                </div>
              )}
            </div>

            {/* Quick Actions — Desktop */}
            <div className="hidden sm:flex gap-2">
              <Link href={`/form?company_id=${companyId}`}>
                <Button variant="default" size="sm" className="gap-1.5">
                  <Play className="w-3.5 h-3.5" /> Run Simulation
                </Button>
              </Link>
              <Link href={`/companies/${companyId}`}>
                <Button variant="outline" size="sm" className="gap-1.5">
                  <Upload className="w-3.5 h-3.5" /> Import Data
                </Button>
              </Link>
            </div>
          </div>
        </div>

        {/* ── Executive Summary (4 metric cards) ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <MetricCard label="Products" value={products.length} icon={Package} />
          <MetricCard label="Suppliers" value={suppliers.length} icon={Truck} />
          <MetricCard label="Warehouses" value={warehouses.length} icon={Warehouse} />
          <MetricCard label="Twins" value={twins.length} icon={Cpu} />
        </div>

        {/* ── Main Grid: 2 columns on desktop ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ──────────── LEFT COLUMN ──────────── */}

          {/* Intelligence Summary */}
          <Section title="Supply Chain Health" icon={Heart}>
            {hasTwins ? (
              <div>
                <div className="flex items-center gap-6 mb-5">
                  <div>
                    <div className={`text-5xl font-display ${healthColor(aggHealth)}`}>
                      {aggHealth}%
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Aggregated across {twins.length} twin{twins.length > 1 ? "s" : ""}
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="h-2.5 bg-foreground/5 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${healthBg(aggHealth)}`}
                        style={{ width: `${Math.min(aggHealth, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-foreground/10 rounded-lg p-3 text-center">
                    <div className="flex items-center justify-center gap-1.5 mb-1">
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      <span className="text-xs font-mono text-muted-foreground">ACTIVE</span>
                    </div>
                    <div className="text-xl font-display">{aggTotalSignals}</div>
                    <div className="text-xs text-muted-foreground">signals</div>
                  </div>
                  <div className="border border-foreground/10 rounded-lg p-3 text-center">
                    <div className="flex items-center justify-center gap-1.5 mb-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                      <span className="text-xs font-mono text-muted-foreground">CRITICAL</span>
                    </div>
                    <div className="text-xl font-display text-red-400">{aggCriticalSignals}</div>
                    <div className="text-xs text-muted-foreground">signals</div>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState
                title="No Digital Twin"
                description="Create a twin to enable intelligence tracking"
                ctaLabel="Create Twin"
                ctaHref={`/companies/${companyId}`}
              />
            )}
          </Section>

          {/* Forecast Summary */}
          <Section
            title="Forecast Summary"
            icon={TrendingUp}
            action={
              hasTwins ? (
                <Link href="/intelligence/forecasts">
                  <Button variant="ghost" size="sm" className="gap-1 text-xs h-7">
                    View All <ArrowRight className="w-3 h-3" />
                  </Button>
                </Link>
              ) : null
            }
          >
            {forecast && forecast.forecasts.length > 0 ? (
              <div>
                <div className="text-xs text-muted-foreground mb-4">
                  Based on <span className="text-foreground font-medium">{primaryTwinName}</span>
                  {" \u00B7 "}
                  {forecast.product}
                </div>

                <div className="grid grid-cols-3 gap-3 mb-4">
                  {forecast.forecasts.map((f) => (
                    <div
                      key={f.horizon}
                      className="border border-foreground/10 rounded-lg p-3 text-center"
                    >
                      <div className="text-xs font-mono text-muted-foreground mb-1">
                        H{f.horizon}
                      </div>
                      <div className="text-xl font-display">
                        {Math.round(f.forecast_demand)}
                      </div>
                      <div className="text-xs text-muted-foreground">units</div>
                      <div className={`text-xs mt-1 ${riskBadge(f.supply_risk)}`}>
                        {f.supply_risk}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Trend indicator */}
                {forecast.source_state && (
                  <div className="flex items-center gap-2 text-sm">
                    {forecast.source_state.demand_trend === "rising" ? (
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                    ) : forecast.source_state.demand_trend === "falling" ? (
                      <TrendingDown className="w-4 h-4 text-red-400" />
                    ) : (
                      <Activity className="w-4 h-4 text-muted-foreground" />
                    )}
                    <span className="text-muted-foreground">Trend:</span>
                    <span className="font-medium capitalize">
                      {forecast.source_state.demand_trend || "stable"}
                    </span>
                  </div>
                )}
              </div>
            ) : hasTwins && hasProducts ? (
              <EmptyState
                title="No Forecast Data"
                description="Run simulations with a twin to generate forecasts"
                ctaLabel="Run Simulation"
                ctaHref={`/form?company_id=${companyId}`}
              />
            ) : !hasProducts ? (
              <EmptyState
                title="No Products"
                description="Import products to enable forecasting"
                ctaLabel="Import Products"
                ctaHref={`/companies/${companyId}`}
              />
            ) : (
              <EmptyState
                title="No Twin"
                description="Create a digital twin first"
                ctaLabel="Create Twin"
                ctaHref={`/companies/${companyId}`}
              />
            )}
          </Section>

          {/* Risk Center */}
          <Section
            title="Top Risks"
            icon={Shield}
            action={
              hasTwins ? (
                <Link href="/intelligence/signals">
                  <Button variant="ghost" size="sm" className="gap-1 text-xs h-7">
                    All Signals <ArrowRight className="w-3 h-3" />
                  </Button>
                </Link>
              ) : null
            }
          >
            {topSignals.length > 0 ? (
              <div className="space-y-2.5">
                {topSignals.map((sig, i) => {
                  const sev = severityLabel(sig.severity);
                  return (
                    <div
                      key={i}
                      className="flex items-center justify-between border border-foreground/10 rounded-lg px-4 py-3"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <Zap className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        <div className="min-w-0">
                          <div className="text-sm font-medium truncate">{sig.name}</div>
                          {twins.length > 1 && (
                            <div className="text-xs text-muted-foreground">{sig.twin_name}</div>
                          )}
                        </div>
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${sev.color}`}
                      >
                        {sev.text}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : hasTwins ? (
              <div className="text-center py-6 text-sm text-muted-foreground">
                No active risk signals
              </div>
            ) : (
              <EmptyState
                title="No Risk Data"
                description="Create a twin and run simulations"
                ctaLabel="Get Started"
                ctaHref={`/companies/${companyId}`}
              />
            )}
          </Section>

          {/* Recent Simulations */}
          <Section
            title="Recent Simulations"
            icon={Activity}
            action={
              <Link href={`/form?company_id=${companyId}`}>
                <Button variant="ghost" size="sm" className="gap-1 text-xs h-7">
                  New <Play className="w-3 h-3" />
                </Button>
              </Link>
            }
          >
            {hasSims ? (
              <div className="space-y-2.5">
                {recentSims.map((sim) => (
                  <Link
                    key={sim.simulation_id}
                    href={`/results?id=${sim.simulation_id}`}
                    className="flex items-center justify-between border border-foreground/10 rounded-lg px-4 py-3 hover:border-foreground/20 transition-colors group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-xs font-mono text-muted-foreground">
                        #{sim.simulation_id}
                      </div>
                      <div>
                        <div className="text-sm font-medium">{sim.product}</div>
                        <div className="text-xs text-muted-foreground">
                          {formatDate(sim.created_at)}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-right">
                      {sim.demand_forecast != null && (
                        <div>
                          <div className="text-sm font-display">
                            {Math.round(sim.demand_forecast)}
                          </div>
                          <div className="text-xs text-muted-foreground">forecast</div>
                        </div>
                      )}
                      <div>
                        <div className={`text-sm font-medium ${riskBadge(sim.risk)}`}>
                          {sim.risk || "—"}
                        </div>
                        <div className="text-xs text-muted-foreground">risk</div>
                      </div>
                      {sim.overall_confidence != null && (
                        <div>
                          <div className="text-sm font-display">
                            {Math.round(sim.overall_confidence)}%
                          </div>
                          <div className="text-xs text-muted-foreground">conf</div>
                        </div>
                      )}
                      <ArrowRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No Simulations"
                description="Run your first simulation to see results here"
                ctaLabel="Run Simulation"
                ctaHref={`/form?company_id=${companyId}`}
              />
            )}
          </Section>
        </div>

        {/* ── Twin Overview (full-width) ── */}
        {hasTwins && (
          <div className="mt-6">
            <Section
              title="Digital Twins"
              icon={Cpu}
              action={
                <Link href="/intelligence/twins">
                  <Button variant="ghost" size="sm" className="gap-1 text-xs h-7">
                    Details <ArrowRight className="w-3 h-3" />
                  </Button>
                </Link>
              }
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {twins.map((twin) => {
                  const h = Math.round(twin.health_score * 100);
                  return (
                    <div
                      key={twin.id}
                      className="border border-foreground/10 rounded-lg p-4"
                    >
                      <div className="flex items-center gap-2.5 mb-3">
                        <div className="w-8 h-8 rounded-lg bg-foreground/5 flex items-center justify-center">
                          <Cpu className="w-4 h-4 text-muted-foreground" />
                        </div>
                        <div className="font-display text-sm">{twin.name}</div>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div>
                          <div className="text-lg font-display">{twin.simulation_count}</div>
                          <div className="text-xs text-muted-foreground">Sims</div>
                        </div>
                        <div>
                          <div className="text-lg font-display">{twin.signal_count}</div>
                          <div className="text-xs text-muted-foreground">Signals</div>
                        </div>
                        <div>
                          <div className={`text-lg font-display ${healthColor(h)}`}>
                            {h}%
                          </div>
                          <div className="text-xs text-muted-foreground">Health</div>
                        </div>
                      </div>
                      <div className="mt-3">
                        <div className="h-1.5 bg-foreground/5 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${healthBg(h)}`}
                            style={{ width: `${Math.min(h, 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Section>
          </div>
        )}

        {/* ── Quick Actions — Mobile ── */}
        <div className="sm:hidden mt-6">
          <Section title="Quick Actions" icon={BarChart3}>
            <div className="grid grid-cols-2 gap-2">
              <Link href={`/form?company_id=${companyId}`}>
                <Button variant="outline" size="sm" className="w-full gap-1.5 h-10">
                  <Play className="w-3.5 h-3.5" /> Simulate
                </Button>
              </Link>
              <Link href={`/companies/${companyId}`}>
                <Button variant="outline" size="sm" className="w-full gap-1.5 h-10">
                  <Upload className="w-3.5 h-3.5" /> Import
                </Button>
              </Link>
              <Link href="/intelligence/forecasts">
                <Button variant="outline" size="sm" className="w-full gap-1.5 h-10">
                  <Eye className="w-3.5 h-3.5" /> Forecasts
                </Button>
              </Link>
              <Link href="/intelligence/signals">
                <Button variant="outline" size="sm" className="w-full gap-1.5 h-10">
                  <Zap className="w-3.5 h-3.5" /> Signals
                </Button>
              </Link>
            </div>
          </Section>
        </div>

        {/* Bottom spacing */}
        <div className="h-12" />
      </main>
    </div>
  );
}
