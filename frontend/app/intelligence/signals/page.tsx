"use client";

import { useEffect, useState } from "react";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import {
  AlertCircle,
  RefreshCw,
  ArrowLeft,
  Zap,
  Activity,
  ShieldAlert,
  TrendingUp,
  Package,
  Globe,
  Layers,
  Clock,
  Filter,
} from "lucide-react";
import Link from "next/link";
import { listTwins, getTwinSignals, getTwinSignalSummary } from "@/lib/api";
import type {
  TwinSummary,
  SignalListResponse,
  SignalSummaryResponse,
  SignalEventEntry,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function severityLabel(s: number): "critical" | "warning" | "info" {
  if (s >= 0.7) return "critical";
  if (s >= 0.3) return "warning";
  return "info";
}

function severityBadgeClass(label: string): string {
  switch (label) {
    case "critical": return "bg-red-500/10 text-red-500 border-red-500/25";
    case "warning": return "bg-amber-500/10 text-amber-500 border-amber-500/25";
    default: return "bg-blue-500/10 text-blue-500 border-blue-500/25";
  }
}

function typeIcon(type: string) {
  switch (type) {
    case "demand": return <TrendingUp className="w-4 h-4" />;
    case "supply": return <Package className="w-4 h-4" />;
    case "risk": return <ShieldAlert className="w-4 h-4" />;
    case "market": return <Activity className="w-4 h-4" />;
    case "external": return <Globe className="w-4 h-4" />;
    case "compound": return <Layers className="w-4 h-4" />;
    default: return <Zap className="w-4 h-4" />;
  }
}

function typeColor(type: string): string {
  switch (type) {
    case "demand": return "text-emerald-500";
    case "supply": return "text-orange-500";
    case "risk": return "text-red-500";
    case "market": return "text-blue-500";
    case "external": return "text-purple-500";
    case "compound": return "text-amber-500";
    default: return "text-foreground";
  }
}

function healthColor(score: number): string {
  if (score >= 0.8) return "text-emerald-500";
  if (score >= 0.5) return "text-amber-500";
  return "text-red-500";
}

function healthBg(score: number): string {
  if (score >= 0.8) return "bg-emerald-500";
  if (score >= 0.5) return "bg-amber-500";
  return "bg-red-500";
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

// Signal type tab options
const SIGNAL_TYPES = [
  { key: "", label: "All", icon: <Zap className="w-3.5 h-3.5" /> },
  { key: "demand", label: "Demand", icon: <TrendingUp className="w-3.5 h-3.5" /> },
  { key: "supply", label: "Supply", icon: <Package className="w-3.5 h-3.5" /> },
  { key: "risk", label: "Risk", icon: <ShieldAlert className="w-3.5 h-3.5" /> },
  { key: "market", label: "Market", icon: <Activity className="w-3.5 h-3.5" /> },
  { key: "external", label: "External (E5)", icon: <Globe className="w-3.5 h-3.5" /> },
  { key: "compound", label: "Compound (E6)", icon: <Layers className="w-3.5 h-3.5" /> },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const PageSkeleton = () => (
  <div className="animate-pulse space-y-4">
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[...Array(4)].map((_, i) => <div key={i} className="border border-foreground/10 rounded-lg h-24" />)}
    </div>
    <div className="space-y-2">
      {[...Array(6)].map((_, i) => <div key={i} className="border border-foreground/10 rounded-lg h-16" />)}
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

const SignalCard = ({ signal }: { signal: SignalEventEntry }) => {
  const label = signal.severity_label || severityLabel(signal.severity);
  const isCompound = signal.signal_type === "compound";

  return (
    <div className={`border rounded-lg p-5 transition-colors hover:border-foreground/20 ${
      isCompound ? "border-amber-500/30 bg-amber-500/3" : "border-foreground/10"
    }`}>
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-2">
          <div className={typeColor(signal.signal_type)}>
            {typeIcon(signal.signal_type)}
          </div>
          <span className="font-display text-lg">{signal.source}</span>
          {isCompound && (
            <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-500">
              COMPOUND
            </span>
          )}
        </div>
        <div className={`text-xs font-mono px-2 py-1 rounded border ${severityBadgeClass(label)}`}>
          {label.toUpperCase()} · {Math.round(signal.severity * 100)}%
        </div>
      </div>

      <div className="flex flex-wrap gap-4 text-sm mb-3">
        <div>
          <span className="text-muted-foreground">type: </span>
          <span className={`font-mono ${typeColor(signal.signal_type)}`}>{signal.signal_type}</span>
        </div>
        <div>
          <span className="text-muted-foreground">id: </span>
          <span className="font-mono text-xs">{signal.id}</span>
        </div>
      </div>

      {/* Payload */}
      {Object.keys(signal.payload).length > 0 && (
        <div className="mt-3 pt-3 border-t border-foreground/5">
          <div className="text-xs font-mono text-muted-foreground mb-2">PAYLOAD</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(signal.payload).map(([k, v]) => (
              <div key={k} className="text-xs bg-foreground/5 rounded px-2 py-1">
                <span className="text-muted-foreground">{k}: </span>
                <span className="font-mono">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <Clock className="w-3 h-3" />
        {formatTs(signal.created_at)}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function SignalsPage() {
  const [twins, setTwins] = useState<TwinSummary[]>([]);
  const [selectedTwin, setSelectedTwin] = useState<number | null>(null);
  const [summary, setSummary] = useState<SignalSummaryResponse | null>(null);
  const [signals, setSignals] = useState<SignalListResponse | null>(null);
  const [activeType, setActiveType] = useState("");
  const [loading, setLoading] = useState(true);
  const [signalsLoading, setSignalsLoading] = useState(false);
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

  const loadSignals = async (twinId: number, type: string) => {
    setSignalsLoading(true);
    try {
      const [sumData, sigData] = await Promise.all([
        getTwinSignalSummary(twinId),
        getTwinSignals(twinId, { signal_type: type || undefined, limit: 100 }),
      ]);
      setSummary(sumData);
      setSignals(sigData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load signals");
    } finally {
      setSignalsLoading(false);
    }
  };

  useEffect(() => { loadTwins(); }, []);

  useEffect(() => {
    if (selectedTwin != null) loadSignals(selectedTwin, activeType);
  }, [selectedTwin, activeType]);

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
              E3 + E5 + E6 Signal Intelligence
            </span>
            <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-4">
              Signals Center
            </h1>
            <p className="text-muted-foreground text-lg max-w-2xl">
              Real-time signal events from internal detectors (E3), external data providers (E5),
              and compound pattern matching (E6). Signals reduce forecast confidence via
              severity-weighted penalties.
            </p>
          </div>

          {loading && <PageSkeleton />}
          {error && <ErrorState message={error} onRetry={loadTwins} />}

          {!loading && !error && twins.length === 0 && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="w-16 h-16 rounded-full bg-muted/30 flex items-center justify-center mb-6">
                <Zap className="w-8 h-8 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground max-w-sm">
                No Digital Twins found. Signals are generated when simulations run with a linked twin.
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
                    onClick={() => loadSignals(selectedTwin, activeType)}
                    disabled={signalsLoading}
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${signalsLoading ? "animate-spin" : ""}`} />
                    Refresh
                  </Button>
                )}
              </div>

              {signalsLoading && <PageSkeleton />}

              {!signalsLoading && summary && (
                <>
                  {/* Health score + summary */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <div className="border border-foreground/10 rounded-lg p-5">
                      <div className="text-xs font-mono text-muted-foreground mb-1">HEALTH SCORE</div>
                      <div className={`text-3xl font-display ${healthColor(summary.health_score)}`}>
                        {Math.round(summary.health_score * 100)}%
                      </div>
                      <div className="w-full h-1.5 bg-muted rounded-full mt-2 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${healthBg(summary.health_score)}`}
                          style={{ width: `${summary.health_score * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="border border-foreground/10 rounded-lg p-5">
                      <div className="text-xs font-mono text-muted-foreground mb-1">TOTAL SIGNALS</div>
                      <div className="text-3xl font-display">{summary.total_signals}</div>
                    </div>
                    <div className="border border-foreground/10 rounded-lg p-5">
                      <div className="text-xs font-mono text-muted-foreground mb-2">BY SEVERITY</div>
                      <div className="space-y-0.5 text-sm">
                        <div className="flex justify-between">
                          <span className="text-red-500">Critical</span>
                          <span className="font-mono">{summary.by_severity.critical}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-amber-500">Warning</span>
                          <span className="font-mono">{summary.by_severity.warning}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-blue-500">Info</span>
                          <span className="font-mono">{summary.by_severity.info}</span>
                        </div>
                      </div>
                    </div>
                    <div className="border border-foreground/10 rounded-lg p-5">
                      <div className="text-xs font-mono text-muted-foreground mb-2">BY TYPE</div>
                      <div className="space-y-0.5 text-sm">
                        {[
                          ["demand", summary.by_type.demand],
                          ["supply", summary.by_type.supply],
                          ["external", summary.by_type.external],
                          ["compound", summary.by_type.compound],
                        ].map(([t, c]) => (
                          <div key={String(t)} className="flex justify-between">
                            <span className={typeColor(String(t))}>{String(t)}</span>
                            <span className="font-mono">{String(c)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Latest critical */}
                  {summary.latest_critical && (
                    <div className="mb-8 border border-red-500/30 bg-red-500/5 rounded-lg p-5">
                      <div className="text-xs font-mono text-red-400 mb-2">LATEST CRITICAL SIGNAL</div>
                      <div className="flex items-center gap-3">
                        <div className="text-red-500">{typeIcon(summary.latest_critical.signal_type)}</div>
                        <div>
                          <span className="font-display text-lg">{summary.latest_critical.source}</span>
                          <span className="text-muted-foreground ml-3 text-sm">
                            severity {Math.round(summary.latest_critical.severity * 100)}%
                            · {formatRelative(summary.latest_critical.created_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Type filter tabs */}
                  <div className="flex flex-wrap gap-2 mb-6">
                    <div className="flex items-center gap-1 text-xs font-mono text-muted-foreground mr-2">
                      <Filter className="w-3.5 h-3.5" /> FILTER
                    </div>
                    {SIGNAL_TYPES.map((tab) => (
                      <button
                        key={tab.key}
                        onClick={() => setActiveType(tab.key)}
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border transition-colors ${
                          activeType === tab.key
                            ? "border-foreground/40 bg-foreground/5 text-foreground"
                            : "border-foreground/10 text-muted-foreground hover:border-foreground/25"
                        }`}
                      >
                        {tab.icon}
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  {/* Signal list */}
                  {signals && signals.signals.length > 0 && (
                    <>
                      <div className="text-xs font-mono text-muted-foreground mb-4">
                        SHOWING {signals.signals.length} SIGNALS
                        {activeType && <span className="ml-1">· filtered: {activeType}</span>}
                      </div>
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {signals.signals.map((s) => (
                          <SignalCard key={s.id} signal={s} />
                        ))}
                      </div>
                    </>
                  )}

                  {signals && signals.signals.length === 0 && (
                    <div className="flex flex-col items-center py-16 text-center">
                      <Activity className="w-8 h-8 text-muted-foreground mb-4" />
                      <p className="text-muted-foreground">
                        {activeType
                          ? `No "${activeType}" signals found for this twin.`
                          : "No signals detected yet. Signals are generated during simulation runs."}
                      </p>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {/* Navigation footer */}
          <div className="flex gap-4 pt-12 border-t border-foreground/10">
            <Link href="/intelligence/twins">
              <Button variant="outline" className="border-foreground/20">← Digital Twin</Button>
            </Link>
            <Link href="/intelligence/compound">
              <Button variant="outline" className="border-foreground/20">Compound Intelligence →</Button>
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
