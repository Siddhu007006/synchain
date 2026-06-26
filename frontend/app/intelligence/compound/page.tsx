"use client";

import React, { useEffect, useState } from "react";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import {
  AlertCircle,
  RefreshCw,
  ArrowLeft,
  Layers,
  Globe,
  Zap,
  TrendingUp,
  Package,
  ShieldAlert,
  Cloud,
  Newspaper,
  DollarSign,
  BarChart2,
  Activity,
} from "lucide-react";
import Link from "next/link";
import { listTwins, getTwinSignals } from "@/lib/api";
import type { TwinSummary, SignalEventEntry } from "@/lib/types";

// ---------------------------------------------------------------------------
// Compound rule metadata (mirrors backend compound.py COMPOUND_RULES)
// ---------------------------------------------------------------------------
const COMPOUND_RULES = [
  {
    name: "SupplyShock",
    triggers: ["DemandSpike", "SupplierDegradation"],
    description: "Demand exceeds supply capacity — supplier can't keep up with demand growth",
    color: "text-red-500",
    borderColor: "border-red-500/25",
    bgColor: "bg-red-500/5",
    icon: <ShieldAlert className="w-5 h-5 text-red-500" />,
    action: "Diversify suppliers immediately. Pre-position inventory. Consider emergency procurement.",
  },
  {
    name: "FulfillmentCrisis",
    triggers: ["WarehouseOverload", "DemandSpike"],
    description: "Warehouses cannot absorb demand — operational bottleneck",
    color: "text-orange-500",
    borderColor: "border-orange-500/25",
    bgColor: "bg-orange-500/5",
    icon: <Package className="w-5 h-5 text-orange-500" />,
    action: "Activate overflow facilities. Divert shipments to alternative warehouses. Reduce inbound velocity.",
  },
  {
    name: "MarketDisruption",
    triggers: ["TrendShift", "SupplierDegradation"],
    description: "Market volatility + unreliable supply — strategic uncertainty",
    color: "text-amber-500",
    borderColor: "border-amber-500/25",
    bgColor: "bg-amber-500/5",
    icon: <TrendingUp className="w-5 h-5 text-amber-500" />,
    action: "Hedge demand with conservative orders. Lock in supply contracts. Monitor trend velocity.",
  },
  {
    name: "PerfectStorm",
    triggers: ["WeatherAlert", "SupplierDegradation", "DemandSpike"],
    description: "Triple threat: physical disruption + supply failure + demand surge",
    color: "text-red-600",
    borderColor: "border-red-600/30",
    bgColor: "bg-red-600/8",
    icon: <Zap className="w-5 h-5 text-red-600" />,
    action: "CRITICAL: Activate emergency response. All supply levers simultaneously. Executive escalation required.",
  },
  {
    name: "CostSqueeze",
    triggers: ["CommodityShock", "EconomicShift"],
    description: "Rising costs + economic pressure — margin erosion",
    color: "text-blue-500",
    borderColor: "border-blue-500/25",
    bgColor: "bg-blue-500/5",
    icon: <DollarSign className="w-5 h-5 text-blue-500" />,
    action: "Review pricing strategy. Renegotiate supplier contracts. Optimize procurement volumes.",
  },
];

// External signal metadata (E5 detector names → UI labels)
const EXTERNAL_SIGNAL_SOURCES: Record<string, { label: string; icon: React.ReactNode; description: string }> = {
  NewsDisruption: {
    label: "News Disruption",
    icon: <Newspaper className="w-4 h-4" />,
    description: "Geopolitical events, trade restrictions, or news-based supply chain disruptions",
  },
  WeatherAlert: {
    label: "Weather Alert",
    icon: <Cloud className="w-4 h-4" />,
    description: "Physical disruptions from weather events affecting logistics or production",
  },
  CommodityShock: {
    label: "Commodity Shock",
    icon: <BarChart2 className="w-4 h-4" />,
    description: "Raw material price volatility affecting procurement costs",
  },
  EconomicShift: {
    label: "Economic Shift",
    icon: <Activity className="w-4 h-4" />,
    description: "Macro-economic indicators affecting demand patterns and supply chain costs",
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function severityBadge(s: number): { label: string; cls: string } {
  if (s >= 0.7) return { label: "CRITICAL", cls: "text-red-500 bg-red-500/10 border-red-500/25" };
  if (s >= 0.3) return { label: "WARNING", cls: "text-amber-500 bg-amber-500/10 border-amber-500/25" };
  return { label: "INFO", cls: "text-blue-500 bg-blue-500/10 border-blue-500/25" };
}

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const PageSkeleton = () => (
  <div className="animate-pulse space-y-4">
    {[...Array(3)].map((_, i) => (
      <div key={i} className="border border-foreground/10 rounded-lg p-6 h-32" />
    ))}
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

// Compound rule card showing real fired signals
const CompoundRuleCard = ({
  rule,
  firedSignals,
}: {
  rule: typeof COMPOUND_RULES[0];
  firedSignals: SignalEventEntry[];
}) => {
  const hasFired = firedSignals.length > 0;
  const latest = firedSignals[0];

  return (
    <div className={`border rounded-lg p-6 transition-colors ${
      hasFired ? `${rule.borderColor} ${rule.bgColor}` : "border-foreground/10"
    }`}>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          {rule.icon}
          <div>
            <div className="font-display text-xl">{rule.name}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{rule.description}</div>
          </div>
        </div>
        {hasFired ? (
          <div className={`text-xs font-mono px-2 py-1 rounded border ${severityBadge(latest.severity).cls} whitespace-nowrap`}>
            ACTIVE · {Math.round(latest.severity * 100)}%
          </div>
        ) : (
          <div className="text-xs font-mono px-2 py-1 rounded border border-foreground/10 text-muted-foreground whitespace-nowrap">
            CLEAR
          </div>
        )}
      </div>

      {/* Trigger conditions */}
      <div className="mb-4">
        <div className="text-xs font-mono text-muted-foreground mb-2">TRIGGER CONDITIONS</div>
        <div className="flex flex-wrap gap-2">
          {rule.triggers.map((t) => (
            <span key={t} className="text-xs font-mono px-2 py-1 rounded bg-foreground/5 border border-foreground/10">
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* Fired instances */}
      {hasFired && (
        <div className="mb-4">
          <div className="text-xs font-mono text-muted-foreground mb-2">
            {firedSignals.length} INSTANCE{firedSignals.length > 1 ? "S" : ""} DETECTED
          </div>
          <div className="space-y-2">
            {firedSignals.slice(0, 3).map((sig) => {
              const badge = severityBadge(sig.severity);
              return (
                <div key={sig.id} className="border border-foreground/5 rounded p-3 bg-foreground/3">
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-xs font-mono px-1.5 py-0.5 rounded border ${badge.cls}`}>{badge.label}</span>
                    <span className="text-xs text-muted-foreground">{formatTs(sig.created_at)}</span>
                  </div>
                  {sig.payload && Object.keys(sig.payload).length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(sig.payload).slice(0, 4).map(([k, v]) => (
                        <span key={k} className="text-xs bg-background/50 rounded px-1.5 py-0.5">
                          <span className="text-muted-foreground">{k}: </span>
                          <span className="font-mono">
                            {typeof v === "object" ? JSON.stringify(v).slice(0, 40) : String(v)}
                          </span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommended action */}
      <div className={`pt-4 border-t ${hasFired ? "border-current/20" : "border-foreground/5"}`}>
        <div className="text-xs font-mono text-muted-foreground mb-1">RECOMMENDED ACTION</div>
        <p className={`text-sm ${hasFired ? rule.color : "text-muted-foreground"}`}>{rule.action}</p>
      </div>
    </div>
  );
};

// External signal card
const ExternalSignalCard = ({ signal }: { signal: SignalEventEntry }) => {
  const meta = EXTERNAL_SIGNAL_SOURCES[signal.source] ?? {
    label: signal.source,
    icon: <Globe className="w-4 h-4" />,
    description: "External intelligence signal",
  };
  const badge = severityBadge(signal.severity);

  return (
    <div className="border border-foreground/10 rounded-lg p-5 hover:border-foreground/20 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-muted-foreground">
          {meta.icon}
          <span className="font-display text-base text-foreground">{meta.label}</span>
        </div>
        <span className={`text-xs font-mono px-2 py-0.5 rounded border ${badge.cls}`}>
          {badge.label} · {Math.round(signal.severity * 100)}%
        </span>
      </div>
      <p className="text-xs text-muted-foreground mb-3">{meta.description}</p>
      {Object.keys(signal.payload).length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(signal.payload).slice(0, 5).map(([k, v]) => (
            <span key={k} className="text-xs bg-foreground/5 rounded px-2 py-1">
              <span className="text-muted-foreground">{k}: </span>
              <span className="font-mono">{typeof v === "object" ? JSON.stringify(v).slice(0, 30) : String(v)}</span>
            </span>
          ))}
        </div>
      )}
      <div className="mt-3 text-xs text-muted-foreground">{formatTs(signal.created_at)}</div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function CompoundPage() {
  const [twins, setTwins] = useState<TwinSummary[]>([]);
  const [selectedTwin, setSelectedTwin] = useState<number | null>(null);
  const [compoundSignals, setCompoundSignals] = useState<SignalEventEntry[]>([]);
  const [externalSignals, setExternalSignals] = useState<SignalEventEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);
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

  const loadData = async (twinId: number) => {
    setDataLoading(true);
    try {
      const [compounds, externals] = await Promise.all([
        getTwinSignals(twinId, { signal_type: "compound", limit: 200 }),
        getTwinSignals(twinId, { signal_type: "external", limit: 200 }),
      ]);
      setCompoundSignals(compounds.signals);
      setExternalSignals(externals.signals);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load signal data");
    } finally {
      setDataLoading(false);
    }
  };

  useEffect(() => { loadTwins(); }, []);
  useEffect(() => {
    if (selectedTwin != null) loadData(selectedTwin);
  }, [selectedTwin]);

  // Group compound signals by source name
  const compoundByName = COMPOUND_RULES.reduce<Record<string, SignalEventEntry[]>>((acc, rule) => {
    acc[rule.name] = compoundSignals.filter((s) => s.source === rule.name);
    return acc;
  }, {});

  const activeCompoundCount = Object.values(compoundByName).filter((arr) => arr.length > 0).length;

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <section className="relative py-32">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12">

          {/* Header */}
          <div className="mb-16">
            <Link href="/intelligence/signals">
              <Button variant="outline" className="mb-6 border-foreground/20 hover:bg-foreground/5">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Signals
              </Button>
            </Link>
            <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
              <span className="w-8 h-px bg-foreground/30" />
              E5 External Intelligence + E6 Compound Intelligence
            </span>
            <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-4">
              Compound Intelligence
            </h1>
            <p className="text-muted-foreground text-lg max-w-2xl">
              Emergent patterns detected when multiple atomic signals co-occur. Compound signals
              represent qualitatively worse situations than individual alerts — carrying additive
              confidence penalties on top of atomic penalties (Design Decision D6).
            </p>
          </div>

          {loading && <PageSkeleton />}
          {error && <ErrorState message={error} onRetry={loadTwins} />}

          {!loading && !error && twins.length === 0 && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="w-16 h-16 rounded-full bg-muted/30 flex items-center justify-center mb-6">
                <Layers className="w-8 h-8 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground max-w-sm">
                No Digital Twins found. Compound signals are generated during simulation runs
                when atomic signal conditions are met simultaneously.
              </p>
            </div>
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
                    {t.name} <span className="text-foreground/40">#{t.id}</span>
                  </button>
                ))}
                {selectedTwin != null && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="ml-auto border-foreground/20 gap-2"
                    onClick={() => loadData(selectedTwin)}
                    disabled={dataLoading}
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${dataLoading ? "animate-spin" : ""}`} />
                    Refresh
                  </Button>
                )}
              </div>

              {dataLoading && <PageSkeleton />}

              {!dataLoading && (
                <>
                  {/* Status bar */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
                    <div className="border border-foreground/10 rounded-lg p-4">
                      <div className="text-xs font-mono text-muted-foreground mb-1">COMPOUND RULES</div>
                      <div className="text-3xl font-display">{COMPOUND_RULES.length}</div>
                    </div>
                    <div className={`border rounded-lg p-4 ${activeCompoundCount > 0 ? "border-amber-500/30 bg-amber-500/5" : "border-foreground/10"}`}>
                      <div className="text-xs font-mono text-muted-foreground mb-1">ACTIVE PATTERNS</div>
                      <div className={`text-3xl font-display ${activeCompoundCount > 0 ? "text-amber-500" : ""}`}>
                        {activeCompoundCount}
                      </div>
                    </div>
                    <div className="border border-foreground/10 rounded-lg p-4">
                      <div className="text-xs font-mono text-muted-foreground mb-1">COMPOUND EVENTS</div>
                      <div className="text-3xl font-display">{compoundSignals.length}</div>
                    </div>
                    <div className="border border-foreground/10 rounded-lg p-4">
                      <div className="text-xs font-mono text-muted-foreground mb-1">EXTERNAL SIGNALS</div>
                      <div className="text-3xl font-display">{externalSignals.length}</div>
                    </div>
                  </div>

                  {/* Compound rules section */}
                  <div className="mb-16">
                    <div className="flex items-center gap-3 mb-6">
                      <Layers className="w-5 h-5 text-amber-500" />
                      <h2 className="text-2xl font-display">Compound Patterns (E6)</h2>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {COMPOUND_RULES.map((rule) => (
                        <CompoundRuleCard
                          key={rule.name}
                          rule={rule}
                          firedSignals={compoundByName[rule.name] ?? []}
                        />
                      ))}
                    </div>
                  </div>

                  {/* External signals section */}
                  <div className="mb-16">
                    <div className="flex items-center gap-3 mb-6">
                      <Globe className="w-5 h-5 text-purple-500" />
                      <h2 className="text-2xl font-display">External Intelligence (E5)</h2>
                      <span className="text-sm text-muted-foreground">
                        — News, Weather, Commodities, Economic indicators
                      </span>
                    </div>

                    {externalSignals.length === 0 && (
                      <div className="flex flex-col items-center py-12 text-center border border-foreground/10 rounded-lg">
                        <Globe className="w-8 h-8 text-muted-foreground mb-3" />
                        <p className="text-muted-foreground text-sm">
                          No external signals detected yet. External detectors run during
                          simulations when a Digital Twin is linked.
                        </p>
                      </div>
                    )}

                    {externalSignals.length > 0 && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {externalSignals.map((s) => (
                          <ExternalSignalCard key={s.id} signal={s} />
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {/* Navigation footer */}
          <div className="flex gap-4 pt-12 border-t border-foreground/10">
            <Link href="/intelligence/signals">
              <Button variant="outline" className="border-foreground/20">← Signals</Button>
            </Link>
            <Link href="/intelligence/forecasts">
              <Button variant="outline" className="border-foreground/20">Forecasts →</Button>
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
