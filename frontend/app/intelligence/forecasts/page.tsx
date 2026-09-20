"use client";

import { useEffect, useState } from "react";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import {
  AlertCircle,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowLeft,
  Activity,
  BarChart3,
  ShieldAlert,
  Zap,
  Info,
} from "lucide-react";
import Link from "next/link";
import { listTwins, getTwinForecastSummary, getTwinForecast } from "@/lib/api";
import type {
  TwinSummary,
  ForecastSummaryResponse,
  ForecastResponse,
  ForecastPointResponse,
  ActiveSignalEntry,
} from "@/lib/types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function confidenceColor(c: number): string {
  if (c >= 0.8) return "text-emerald-500";
  if (c >= 0.6) return "text-amber-500";
  return "text-red-500";
}

function confidenceBg(c: number): string {
  if (c >= 0.8) return "bg-emerald-500";
  if (c >= 0.6) return "bg-amber-500";
  return "bg-red-500";
}

function riskColor(risk: string): string {
  switch (risk) {
    case "HIGH": return "text-red-500";
    case "MEDIUM": return "text-amber-500";
    case "LOW": return "text-emerald-500";
    default: return "text-muted-foreground";
  }
}

function trendIcon(trend: string) {
  switch (trend) {
    case "Rising": return <TrendingUp className="w-4 h-4 text-emerald-500" />;
    case "Falling": return <TrendingDown className="w-4 h-4 text-red-500" />;
    default: return <Minus className="w-4 h-4 text-muted-foreground" />;
  }
}

function severityColor(severity: number): string {
  if (severity >= 0.7) return "text-red-500 bg-red-500/10 border-red-500/20";
  if (severity >= 0.3) return "text-amber-500 bg-amber-500/10 border-amber-500/20";
  return "text-blue-500 bg-blue-500/10 border-blue-500/20";
}

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const PageSkeleton = () => (
  <div className="animate-pulse space-y-8">
    <div className="h-8 w-64 bg-muted rounded" />
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="border border-foreground/10 rounded-lg p-6 h-32" />
      ))}
    </div>
    <div className="border border-foreground/10 rounded-lg p-6 h-64" />
  </div>
);

const EmptyState = ({ message }: { message: string }) => (
  <div className="flex flex-col items-center justify-center py-24 text-center">
    <div className="w-16 h-16 rounded-full bg-muted/30 flex items-center justify-center mb-6">
      <BarChart3 className="w-8 h-8 text-muted-foreground" />
    </div>
    <p className="text-muted-foreground max-w-sm">{message}</p>
  </div>
);

const ErrorState = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div className="flex flex-col items-center justify-center py-24 text-center">
    <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-6">
      <AlertCircle className="w-8 h-8 text-destructive" />
    </div>
    <p className="text-muted-foreground mb-6 max-w-sm">{message}</p>
    {onRetry && (
      <Button onClick={onRetry} variant="outline" className="gap-2">
        <RefreshCw className="w-4 h-4" /> Retry
      </Button>
    )}
  </div>
);

// Horizon forecast card
const HorizonCard = ({ point }: { point: ForecastPointResponse }) => {
  const pct = Math.round(point.confidence * 100);
  return (
    <div className="border border-foreground/10 rounded-lg p-6 hover:border-foreground/20 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-mono text-muted-foreground">HORIZON {point.horizon}</div>
        <span className={`text-xs font-mono px-2 py-0.5 rounded border ${riskColor(point.supply_risk)} bg-current/5`}
          style={{ borderColor: "currentColor", opacity: 1 }}>
          <span className={riskColor(point.supply_risk)}>SUPPLY {point.supply_risk}</span>
        </span>
      </div>
      <div className="text-3xl font-display mb-1">
        {point.forecast_demand.toLocaleString()}
        <span className="text-base text-muted-foreground ml-2">units</span>
      </div>
      <div className="flex items-center gap-3 mb-4">
        <div className="text-xs text-muted-foreground">
          trend ×{point.trend_factor.toFixed(2)} · season ×{point.season_factor.toFixed(2)}
        </div>
      </div>
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full ${confidenceBg(point.confidence)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className={`text-xs font-mono ${confidenceColor(point.confidence)}`}>
        {pct}% confidence
      </div>
      <div className="mt-4 pt-4 border-t border-foreground/5">
        <div className="text-xs font-mono text-muted-foreground mb-1">EXPLANATION</div>
        <p className="text-xs text-muted-foreground leading-relaxed">{point.explanation}</p>
      </div>
    </div>
  );
};

// Signal pill
const SignalPill = ({ signal }: { signal: ActiveSignalEntry }) => (
  <div className={`border rounded-lg p-3 text-xs ${severityColor(signal.severity)}`}>
    <div className="flex items-center justify-between mb-1">
      <span className="font-mono font-semibold">{signal.source}</span>
      <span className="font-mono">{Math.round(signal.severity * 100)}% severity</span>
    </div>
    <div className="text-muted-foreground">{signal.signal_type} · {formatTs(signal.created_at)}</div>
  </div>
);

// Forecast chart
const ForecastChart = ({
  baseDemand,
  forecasts,
}: {
  baseDemand: number;
  forecasts: ForecastPointResponse[];
}) => {
  const data = forecasts.map((f) => ({
    horizon: `H${f.horizon}`,
    forecast: Math.round(f.forecast_demand),
    confidence: Math.round(f.confidence * 100),
  }));

  return (
    <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
      <div className="text-sm font-mono text-muted-foreground mb-6">DEMAND FORECAST CURVE (E2 FORECAST ENGINE)</div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid stroke="var(--muted-foreground)" strokeOpacity={0.08} />
          <XAxis dataKey="horizon" tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
          <YAxis
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}k`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--background)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              color: "var(--foreground)",
            }}
            formatter={(value: number, name: string) =>
              name === "forecast"
                ? [`${value.toLocaleString()} units`, "Forecast Demand"]
                : [`${value}%`, "Confidence"]
            }
          />
          <ReferenceLine
            y={baseDemand}
            stroke="#6b7280"
            strokeDasharray="4 4"
            strokeOpacity={0.5}
            label={{ value: "Base", fill: "var(--muted-foreground)", fontSize: 11 }}
          />
          <Line
            type="monotone"
            dataKey="forecast"
            stroke="#22c55e"
            strokeWidth={2.5}
            dot={{ fill: "#22c55e", r: 5 }}
            activeDot={{ r: 7 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-2 text-xs text-muted-foreground">
        Dashed line = base EWMA demand. Curve generated by ForecastEngine using twin state, not simulation multipliers.
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function ForecastsPage() {
  const [twins, setTwins] = useState<TwinSummary[]>([]);
  const [selectedTwin, setSelectedTwin] = useState<number | null>(null);
  const [summary, setSummary] = useState<ForecastSummaryResponse | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null);
  const [forecastDetail, setForecastDetail] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTwins = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listTwins();
      setTwins(data);
      if (data.length > 0) {
        setSelectedTwin(data[0].id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load digital twins");
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async (twinId: number) => {
    setLoading(true);
    setError(null);
    setSummary(null);
    setForecastDetail(null);
    setSelectedProduct(null);
    try {
      const data = await getTwinForecastSummary(twinId);
      setSummary(data);
      if (data.products.length > 0) {
        setSelectedProduct(data.products[0].product);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load forecast summary");
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (twinId: number, product: string) => {
    setDetailLoading(true);
    setForecastDetail(null);
    try {
      const data = await getTwinForecast(twinId, product, "1,3,5");
      setForecastDetail(data);
    } catch (e) {
      // Non-blocking — product may have no twin state yet
      console.warn("Forecast detail failed:", e);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => { loadTwins(); }, []);

  useEffect(() => {
    if (selectedTwin != null) loadSummary(selectedTwin);
  }, [selectedTwin]);

  useEffect(() => {
    if (selectedTwin != null && selectedProduct != null) {
      loadDetail(selectedTwin, selectedProduct);
    }
  }, [selectedTwin, selectedProduct]);

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <section className="relative py-32">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12">

          {/* Header */}
          <div className="mb-16">
            <Link href="/form">
              <Button variant="outline" className="mb-6 border-foreground/20 hover:bg-foreground/5">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Simulator
              </Button>
            </Link>
            <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
              <span className="w-8 h-px bg-foreground/30" />
              E2 Forecast Engine
            </span>
            <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-4">
              Forecast Dashboard
            </h1>
            <p className="text-muted-foreground text-lg max-w-2xl">
              Multi-horizon demand forecasts generated by the EWMA ForecastEngine using Digital Twin
              historical state, trend direction, seasonality, and live signal penalties.
              These values are distinct from simulation estimates.
            </p>
          </div>

          {/* Disclaimer banner */}
          <div className="mb-10 border border-amber-500/30 bg-amber-500/5 rounded-lg p-4 flex gap-3">
            <Info className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <div className="text-sm text-amber-200/80">
              <span className="font-semibold text-amber-400">Architecture note:</span>{" "}
              The "Demand Forecast" shown in simulation results comes from{" "}
              <code className="font-mono text-xs bg-foreground/5 px-1 py-0.5 rounded">DemandAgent</code>{" "}
              (fixed multipliers on raw input). This page uses the real{" "}
              <code className="font-mono text-xs bg-foreground/5 px-1 py-0.5 rounded">ForecastEngine</code>{" "}
              which reads EWMA-smoothed historical averages from the Digital Twin state and applies
              signal-adjusted confidence scoring.
            </div>
          </div>

          {loading && <PageSkeleton />}
          {error && <ErrorState message={error} onRetry={loadTwins} />}

          {!loading && !error && twins.length === 0 && (
            <EmptyState message="No Digital Twins found. Run a simulation with a twin_id to create state, then forecasts will be available here." />
          )}

          {!loading && !error && twins.length > 0 && (
            <>
              {/* Twin selector */}
              <div className="mb-8 flex flex-wrap gap-2">
                {twins.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setSelectedTwin(t.id)}
                    className={`px-4 py-2 text-sm font-mono rounded-lg border transition-colors ${
                      selectedTwin === t.id
                        ? "border-foreground/40 bg-foreground/5 text-foreground"
                        : "border-foreground/10 text-muted-foreground hover:border-foreground/25"
                    }`}
                  >
                    {t.name} <span className="text-foreground/40">#{t.id}</span>
                  </button>
                ))}
              </div>

              {/* Summary cards */}
              {summary && summary.products.length > 0 && (
                <div className="mb-10">
                  <h2 className="text-2xl font-display mb-6">Products</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                    {summary.products.map((p) => (
                      <button
                        key={p.product}
                        onClick={() => setSelectedProduct(p.product)}
                        className={`text-left border rounded-lg p-6 transition-colors ${
                          selectedProduct === p.product
                            ? "border-foreground/40 bg-foreground/5"
                            : "border-foreground/10 hover:border-foreground/25"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div className="text-sm font-mono text-muted-foreground">PRODUCT</div>
                          <div className="flex items-center gap-1.5">
                            {trendIcon(p.demand_trend)}
                            <span className="text-xs text-muted-foreground">{p.demand_trend}</span>
                          </div>
                        </div>
                        <div className="text-2xl font-display mb-2">{p.product}</div>
                        <div className="text-sm text-muted-foreground">
                          Avg demand: <span className="text-foreground font-display">{p.avg_demand.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                        </div>
                        {p.latest_forecast && (
                          <div className="mt-3 pt-3 border-t border-foreground/5 flex items-center justify-between">
                            <div className="text-xs text-muted-foreground">
                              H1 forecast:{" "}
                              <span className="text-foreground font-display">
                                {p.latest_forecast.forecast_demand.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                              </span>
                            </div>
                            <div className={`text-xs font-mono ${confidenceColor(p.latest_forecast.confidence)}`}>
                              {Math.round(p.latest_forecast.confidence * 100)}%
                            </div>
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {summary && summary.products.length === 0 && (
                <EmptyState message="No product forecast data yet. Link a Digital Twin to a simulation to generate state." />
              )}

              {/* Detail section */}
              {selectedProduct && (
                <div className="mb-16">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-display">
                      {selectedProduct} — Multi-Horizon Forecast
                    </h2>
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2 border-foreground/20"
                      onClick={() => selectedTwin != null && loadDetail(selectedTwin, selectedProduct)}
                      disabled={detailLoading}
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${detailLoading ? "animate-spin" : ""}`} />
                      Refresh
                    </Button>
                  </div>

                  {detailLoading && (
                    <div className="animate-pulse space-y-4">
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        {[...Array(3)].map((_, i) => (
                          <div key={i} className="border border-foreground/10 rounded-lg p-6 h-48" />
                        ))}
                      </div>
                    </div>
                  )}

                  {!detailLoading && forecastDetail && (
                    <>
                      {/* Source state */}
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
                        {[
                          { label: "AVG DEMAND", value: forecastDetail.source_state.avg_demand.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
                          { label: "TREND", value: forecastDetail.source_state.demand_trend },
                          { label: "SEASON", value: forecastDetail.source_state.season },
                          { label: "RELIABILITY", value: `${forecastDetail.source_state.supplier_reliability.toFixed(1)}%` },
                          { label: "SIM COUNT", value: forecastDetail.source_state.simulation_count.toLocaleString() },
                        ].map((item) => (
                          <div key={item.label} className="border border-foreground/10 rounded-lg p-4">
                            <div className="text-xs font-mono text-muted-foreground mb-1">{item.label}</div>
                            <div className="text-xl font-display">{item.value}</div>
                          </div>
                        ))}
                      </div>

                      {/* Forecast chart */}
                      <div className="mb-8">
                        <ForecastChart
                          baseDemand={forecastDetail.source_state.avg_demand}
                          forecasts={forecastDetail.forecasts}
                        />
                      </div>

                      {/* Horizon cards */}
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-10">
                        {forecastDetail.forecasts.map((f) => (
                          <HorizonCard key={f.horizon} point={f} />
                        ))}
                      </div>

                      {/* Active signals */}
                      {forecastDetail.active_signals.length > 0 && (
                        <div>
                          <div className="flex items-center gap-3 mb-4">
                            <Zap className="w-5 h-5 text-amber-500" />
                            <h3 className="text-lg font-display">
                              Active Signals ({forecastDetail.active_signals.length})
                            </h3>
                            <span className="text-xs font-mono text-muted-foreground">
                              — reducing confidence via severity × weight penalty
                            </span>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {forecastDetail.active_signals.map((s, i) => (
                              <SignalPill key={i} signal={s} />
                            ))}
                          </div>
                        </div>
                      )}

                      {forecastDetail.active_signals.length === 0 && (
                        <div className="flex items-center gap-3 p-4 border border-emerald-500/20 rounded-lg bg-emerald-500/5">
                          <Activity className="w-4 h-4 text-emerald-500" />
                          <span className="text-sm text-emerald-400">No active signals — full confidence, no penalties applied</span>
                        </div>
                      )}
                    </>
                  )}

                  {!detailLoading && !forecastDetail && (
                    <EmptyState message="No forecast available for this product yet. This product needs simulation history in the Digital Twin." />
                  )}
                </div>
              )}
            </>
          )}

          {/* Navigation footer */}
          <div className="flex gap-4 pt-12 border-t border-foreground/10">
            <Link href="/intelligence/twins">
              <Button variant="outline" className="border-foreground/20">Digital Twin →</Button>
            </Link>
            <Link href="/intelligence/signals">
              <Button variant="outline" className="border-foreground/20">Signals →</Button>
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
