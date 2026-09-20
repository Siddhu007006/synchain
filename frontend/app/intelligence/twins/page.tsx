"use client";

import { useEffect, useState } from "react";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import {
  AlertCircle,
  RefreshCw,
  ArrowLeft,
  Cpu,
  Package,
  Warehouse,
  Truck,
  TrendingUp,
  TrendingDown,
  Minus,
  Clock,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import Link from "next/link";
import { listTwins, getTwin, getTwinHistory } from "@/lib/api";
import type {
  TwinSummary,
  TwinDetailResponse,
  TwinHistoryResponse,
  StateHistoryEntry,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function trendIcon(trend: string) {
  switch (trend) {
    case "Rising": return <TrendingUp className="w-4 h-4 text-emerald-500" />;
    case "Falling": return <TrendingDown className="w-4 h-4 text-red-500" />;
    default: return <Minus className="w-4 h-4 text-muted-foreground" />;
  }
}

function reliabilityColor(score: number): string {
  if (score >= 80) return "text-emerald-500";
  if (score >= 50) return "text-amber-500";
  return "text-red-500";
}

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

function formatRelative(ts: string | null): string {
  if (!ts) return "—";
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const PageSkeleton = () => (
  <div className="animate-pulse space-y-6">
    <div className="h-8 w-56 bg-muted rounded" />
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="border border-foreground/10 rounded-lg p-6 h-40" />
      ))}
    </div>
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

const EmptyState = ({ message }: { message: string }) => (
  <div className="flex flex-col items-center justify-center py-24 text-center">
    <div className="w-16 h-16 rounded-full bg-muted/30 flex items-center justify-center mb-6">
      <Cpu className="w-8 h-8 text-muted-foreground" />
    </div>
    <p className="text-muted-foreground max-w-sm">{message}</p>
  </div>
);

const SectionLabel = ({ children }: { children: React.ReactNode }) => (
  <div className="text-xs font-mono text-muted-foreground mb-2">{children}</div>
);

// History row
const HistoryRow = ({ entry }: { entry: StateHistoryEntry }) => (
  <div className="grid grid-cols-4 gap-4 py-3 border-b border-foreground/5 text-sm">
    <div className="text-muted-foreground font-mono">{entry.entity_type}/{entry.entity_id}</div>
    <div className="font-mono">{entry.field_name}</div>
    <div className="flex items-center gap-2">
      <span className="text-red-400/70 line-through">{entry.old_value ?? "—"}</span>
      <span className="text-muted-foreground">→</span>
      <span className="text-emerald-400">{entry.new_value}</span>
    </div>
    <div className="text-muted-foreground text-xs">{formatTs(entry.changed_at)}</div>
  </div>
);

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function TwinsPage() {
  const [twins, setTwins] = useState<TwinSummary[]>([]);
  const [selectedTwin, setSelectedTwin] = useState<number | null>(null);
  const [detail, setDetail] = useState<TwinDetailResponse | null>(null);
  const [history, setHistory] = useState<TwinHistoryResponse | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTwins = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listTwins();
      setTwins(data);
      if (data.length > 0) setSelectedTwin(data[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load twins");
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (twinId: number) => {
    setDetailLoading(true);
    setDetail(null);
    setHistory(null);
    setShowHistory(false);
    try {
      const data = await getTwin(twinId);
      setDetail(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load twin detail");
    } finally {
      setDetailLoading(false);
    }
  };

  const loadHistory = async (twinId: number) => {
    setHistoryLoading(true);
    try {
      const data = await getTwinHistory(twinId, 50, 0);
      setHistory(data);
    } catch (e) {
      console.warn("History load failed:", e);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => { loadTwins(); }, []);

  useEffect(() => {
    if (selectedTwin != null) loadDetail(selectedTwin);
  }, [selectedTwin]);

  const toggleHistory = () => {
    if (!showHistory && history == null && selectedTwin != null) {
      loadHistory(selectedTwin);
    }
    setShowHistory((v) => !v);
  };

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
              E1 Digital Twin
            </span>
            <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-4">
              Digital Twin Dashboard
            </h1>
            <p className="text-muted-foreground text-lg max-w-2xl">
              EWMA-smoothed supply chain state tracked across simulations. Each simulation run
              updates product demand averages, warehouse utilization, supplier reliability,
              and market context.
            </p>
          </div>

          {loading && <PageSkeleton />}
          {error && <ErrorState message={error} onRetry={loadTwins} />}

          {!loading && !error && twins.length === 0 && (
            <EmptyState message="No Digital Twins found. Create a twin via the API or run a simulation with a twin_id to auto-create state." />
          )}

          {!loading && !error && twins.length > 0 && (
            <>
              {/* Twin selector */}
              <div className="mb-8 flex flex-wrap gap-2 items-center">
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
                    {t.name}
                    <span className="text-foreground/40 ml-2">#{t.id}</span>
                    <span className="text-foreground/30 ml-2">·</span>
                    <span className="text-foreground/40 ml-2">{t.simulation_count} sims</span>
                  </button>
                ))}
                {selectedTwin != null && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="ml-auto border-foreground/20 gap-2"
                    onClick={() => loadDetail(selectedTwin)}
                    disabled={detailLoading}
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${detailLoading ? "animate-spin" : ""}`} />
                    Refresh
                  </Button>
                )}
              </div>

              {detailLoading && <PageSkeleton />}

              {!detailLoading && detail && (
                <>
                  {/* Twin header */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
                    <div className="border border-foreground/10 rounded-lg p-4">
                      <SectionLabel>TWIN NAME</SectionLabel>
                      <div className="text-xl font-display">{detail.name}</div>
                    </div>
                    <div className="border border-foreground/10 rounded-lg p-4">
                      <SectionLabel>SIMULATIONS</SectionLabel>
                      <div className="text-xl font-display">{detail.simulation_count.toLocaleString()}</div>
                    </div>
                    <div className="border border-foreground/10 rounded-lg p-4">
                      <SectionLabel>CREATED</SectionLabel>
                      <div className="text-sm font-display">{formatTs(detail.created_at)}</div>
                    </div>
                    <div className="border border-foreground/10 rounded-lg p-4">
                      <SectionLabel>LAST UPDATED</SectionLabel>
                      <div className="text-sm font-display">{formatRelative(detail.updated_at)}</div>
                    </div>
                  </div>

                  {/* Product States */}
                  {detail.product_states.length > 0 && (
                    <div className="mb-10">
                      <div className="flex items-center gap-3 mb-5">
                        <Package className="w-5 h-5 text-muted-foreground" />
                        <h2 className="text-2xl font-display">Product States</h2>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {detail.product_states.map((p) => (
                          <div key={p.product_name} className="border border-foreground/10 rounded-lg p-6 hover:border-foreground/20 transition-colors">
                            <div className="flex items-center justify-between mb-4">
                              <div className="font-display text-xl">{p.product_name}</div>
                              <div className="flex items-center gap-1.5">
                                {trendIcon(p.demand_trend)}
                                <span className="text-xs text-muted-foreground">{p.demand_trend}</span>
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <SectionLabel>LATEST DEMAND</SectionLabel>
                                <div className="text-2xl font-display">{p.latest_demand.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                              </div>
                              <div>
                                <SectionLabel>AVG DEMAND (EWMA)</SectionLabel>
                                <div className="text-2xl font-display">{p.avg_demand.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                              </div>
                              <div>
                                <SectionLabel>LATEST STOCK</SectionLabel>
                                <div className="text-lg font-display">{p.latest_stock.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                              </div>
                              <div>
                                <SectionLabel>SIM COUNT</SectionLabel>
                                <div className="text-lg font-display">{p.simulation_count}</div>
                              </div>
                            </div>
                            <div className="mt-3 pt-3 border-t border-foreground/5 flex items-center gap-2">
                              <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                              <span className="text-xs text-muted-foreground">{formatRelative(p.updated_at)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Warehouse States */}
                  {detail.warehouse_states.length > 0 && (
                    <div className="mb-10">
                      <div className="flex items-center gap-3 mb-5">
                        <Warehouse className="w-5 h-5 text-muted-foreground" />
                        <h2 className="text-2xl font-display">Warehouse States</h2>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {detail.warehouse_states.map((w) => (
                          <div key={w.warehouse_id} className="border border-foreground/10 rounded-lg p-6 hover:border-foreground/20 transition-colors">
                            <div className="font-display text-2xl mb-4">{w.warehouse_id}</div>
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <SectionLabel>UTILIZATION</SectionLabel>
                                <div className="text-xl font-display">{(w.utilization_pct * 100).toFixed(1)}%</div>
                              </div>
                              <div>
                                <SectionLabel>SELECTION RATE</SectionLabel>
                                <div className="text-xl font-display">{(w.selection_rate * 100).toFixed(1)}%</div>
                              </div>
                              <div>
                                <SectionLabel>TIMES SELECTED</SectionLabel>
                                <div className="text-xl font-display">{w.times_selected}</div>
                              </div>
                              <div>
                                <SectionLabel>AVG RISK</SectionLabel>
                                <div className="text-xl font-display">{w.avg_risk_score.toFixed(2)}</div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Supplier + Market States */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
                    {/* Supplier */}
                    {detail.supplier_state && (
                      <div>
                        <div className="flex items-center gap-3 mb-5">
                          <Truck className="w-5 h-5 text-muted-foreground" />
                          <h2 className="text-2xl font-display">Supplier State</h2>
                        </div>
                        <div className="border border-foreground/10 rounded-lg p-6">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <SectionLabel>AVG DELAY</SectionLabel>
                              <div className="text-3xl font-display">{detail.supplier_state.avg_delay.toFixed(1)}<span className="text-base text-muted-foreground ml-1">days</span></div>
                            </div>
                            <div>
                              <SectionLabel>MAX DELAY SEEN</SectionLabel>
                              <div className="text-3xl font-display">{detail.supplier_state.max_delay_seen.toFixed(1)}<span className="text-base text-muted-foreground ml-1">days</span></div>
                            </div>
                            <div>
                              <SectionLabel>RELIABILITY SCORE</SectionLabel>
                              <div className={`text-3xl font-display ${reliabilityColor(detail.supplier_state.reliability_score)}`}>
                                {detail.supplier_state.reliability_score.toFixed(1)}%
                              </div>
                            </div>
                            <div>
                              <SectionLabel>SUPPLY STATUS MODE</SectionLabel>
                              <div className="text-2xl font-display">{detail.supplier_state.supply_status_mode}</div>
                            </div>
                          </div>
                          <div className="mt-4 pt-4 border-t border-foreground/5 flex items-center gap-2">
                            <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">{formatRelative(detail.supplier_state.updated_at)}</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Market */}
                    {detail.market_state && (
                      <div>
                        <div className="flex items-center gap-3 mb-5">
                          <TrendingUp className="w-5 h-5 text-muted-foreground" />
                          <h2 className="text-2xl font-display">Market State</h2>
                        </div>
                        <div className="border border-foreground/10 rounded-lg p-6">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <SectionLabel>TREND MODE</SectionLabel>
                              <div className="flex items-center gap-2">
                                {trendIcon(detail.market_state.trend_mode)}
                                <span className="text-2xl font-display">{detail.market_state.trend_mode}</span>
                              </div>
                            </div>
                            <div>
                              <SectionLabel>SEASON MODE</SectionLabel>
                              <div className="text-2xl font-display">{detail.market_state.season_mode}</div>
                            </div>
                            <div>
                              <SectionLabel>AVG CONFIDENCE</SectionLabel>
                              <div className="text-3xl font-display">{Math.round(detail.market_state.avg_confidence * 100)}%</div>
                            </div>
                            <div>
                              <SectionLabel>AVG RISK SCORE</SectionLabel>
                              <div className="text-3xl font-display">{detail.market_state.avg_risk_score.toFixed(2)}</div>
                            </div>
                          </div>
                          <div className="mt-4 pt-4 border-t border-foreground/5 flex items-center gap-2">
                            <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">{formatRelative(detail.market_state.updated_at)}</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* History */}
                  <div className="mb-10">
                    <button
                      onClick={toggleHistory}
                      className="flex items-center gap-3 group w-full text-left"
                    >
                      <Clock className="w-5 h-5 text-muted-foreground" />
                      <h2 className="text-2xl font-display group-hover:text-foreground/80 transition-colors">
                        State History Timeline
                      </h2>
                      {showHistory ? (
                        <ChevronUp className="w-5 h-5 text-muted-foreground ml-auto" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-muted-foreground ml-auto" />
                      )}
                    </button>

                    {showHistory && (
                      <div className="mt-6">
                        {historyLoading && (
                          <div className="animate-pulse space-y-2">
                            {[...Array(5)].map((_, i) => (
                              <div key={i} className="h-10 bg-muted rounded" />
                            ))}
                          </div>
                        )}
                        {!historyLoading && history && history.entries.length > 0 && (
                          <>
                            <div className="grid grid-cols-4 gap-4 py-2 text-xs font-mono text-muted-foreground border-b border-foreground/10">
                              <div>ENTITY</div>
                              <div>FIELD</div>
                              <div>CHANGE</div>
                              <div>TIMESTAMP</div>
                            </div>
                            {history.entries.map((e) => (
                              <HistoryRow key={e.id} entry={e} />
                            ))}
                            <div className="mt-3 text-xs text-muted-foreground">
                              Showing {history.entries.length} of {history.total_entries} entries
                            </div>
                          </>
                        )}
                        {!historyLoading && history && history.entries.length === 0 && (
                          <p className="text-muted-foreground text-sm mt-4">No state history recorded yet.</p>
                        )}
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {/* Navigation footer */}
          <div className="flex gap-4 pt-12 border-t border-foreground/10">
            <Link href="/intelligence/forecasts">
              <Button variant="outline" className="border-foreground/20">← Forecasts</Button>
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
