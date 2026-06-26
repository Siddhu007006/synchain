"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  AlertCircle,
  RefreshCw,
  Brain,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  TrendingUp,
  Package,
  Truck,
  Zap,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { getSimulationResult, getScenarioComparison } from "@/lib/api";
import { AgentBreakdown } from "@/components/results/agent-breakdown";
import { ScenarioPanel } from "@/components/results/scenario-panel";
import type {
  SimulationDetailResponse,
  AgentBreakdownItem,
  ScenarioResponse,
  ScenarioComparison,
} from "@/lib/types";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  Cell,
} from "recharts";

// ---------------------------------------------------------------------------
// Metric Card
// ---------------------------------------------------------------------------
const MetricCard = ({
  label,
  value,
  unit,
}: {
  label: string;
  value: string | number;
  unit?: string;
}) => (
  <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
    <div className="text-sm font-mono text-muted-foreground mb-2">{label}</div>
    <div className="text-3xl lg:text-4xl font-display">
      {value}
      {unit && <span className="text-xl ml-2 text-muted-foreground">{unit}</span>}
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------
const ResultsSkeleton = () => (
  <div className="animate-pulse space-y-16">
    <div>
      <div className="h-8 w-48 bg-muted rounded mb-8" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="border border-foreground/10 rounded-lg p-6 lg:p-8">
            <div className="h-4 w-24 bg-muted rounded mb-4" />
            <div className="h-10 w-32 bg-muted rounded" />
          </div>
        ))}
      </div>
    </div>
    <div>
      <div className="h-8 w-64 bg-muted rounded mb-6" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="border border-foreground/10 rounded-lg p-6 h-48" />
        ))}
      </div>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Error State
// ---------------------------------------------------------------------------
const ErrorState = ({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) => (
  <div className="flex flex-col items-center justify-center py-24 text-center">
    <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-6">
      <AlertCircle className="w-8 h-8 text-destructive" />
    </div>
    <h2 className="text-2xl font-display mb-2">Failed to Load Results</h2>
    <p className="text-muted-foreground mb-8 max-w-md">{message}</p>
    <div className="flex gap-4">
      {onRetry && (
        <Button onClick={onRetry} variant="outline" className="gap-2">
          <RefreshCw className="w-4 h-4" /> Retry
        </Button>
      )}
      <Link href="/form">
        <Button className="bg-foreground hover:bg-foreground/90 text-background gap-2">
          <ArrowLeft className="w-4 h-4" /> New Simulation
        </Button>
      </Link>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function riskColor(risk: string): string {
  switch (risk) {
    case "High":   return "text-red-500";
    case "Medium": return "text-amber-500";
    case "Low":    return "text-emerald-500";
    default:       return "text-foreground";
  }
}

function confidenceBg(c: number): string {
  if (c >= 0.8) return "bg-emerald-500";
  if (c >= 0.6) return "bg-amber-500";
  return "bg-red-500";
}

function confidenceText(c: number): string {
  if (c >= 0.8) return "text-emerald-500";
  if (c >= 0.6) return "text-amber-500";
  return "text-red-500";
}

function deltaIcon(val: number) {
  if (val > 0) return <ArrowUpRight className="w-4 h-4 text-amber-500" />;
  if (val < 0) return <ArrowDownRight className="w-4 h-4 text-emerald-500" />;
  return <Minus className="w-4 h-4 text-muted-foreground" />;
}

function scenarioIcon(name: string) {
  switch (name) {
    case "Demand Surge":       return <TrendingUp className="w-5 h-5 text-amber-500" />;
    case "Supplier Shutdown":  return <XCircle className="w-5 h-5 text-red-500" />;
    case "Inventory Shortage": return <Package className="w-5 h-5 text-orange-500" />;
    case "Transport Delay":    return <Truck className="w-5 h-5 text-blue-500" />;
    default:                   return <Zap className="w-5 h-5" />;
  }
}

// ---------------------------------------------------------------------------
// Overall Confidence Bar
// ---------------------------------------------------------------------------
const OverallConfidenceBar = ({ confidence }: { confidence: number }) => {
  const pct = Math.round(confidence * 100);
  return (
    <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm font-mono text-muted-foreground">OVERALL CONFIDENCE</div>
        <div className={`text-2xl font-display ${confidenceText(confidence)}`}>{pct}%</div>
      </div>
      <div className="w-full h-3 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ease-out ${confidenceBg(confidence)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        Weighted average — RiskAgent 40%, DemandAgent 25%, InventoryAgent 20%, LogisticsAgent 15%
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Scenario Card — shows backend-computed scenario comparison
// ---------------------------------------------------------------------------
const ScenarioCard = ({ scenario }: { scenario: ScenarioComparison }) => {
  const { impact } = scenario;
  const hasChanges = impact.recommendation_changed;

  return (
    <div className={`border rounded-lg p-6 transition-colors ${
      hasChanges ? "border-amber-500/30 bg-amber-500/5" : "border-foreground/10"
    }`}>
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-foreground/5 flex items-center justify-center">
          {scenarioIcon(scenario.scenario_name)}
        </div>
        <div>
          <div className="font-display text-lg">{scenario.scenario_name}</div>
          <div className="text-xs text-muted-foreground">{scenario.scenario_description}</div>
        </div>
        {hasChanges && (
          <div className="ml-auto">
            <span className="text-xs font-mono px-2 py-1 rounded bg-amber-500/20 text-amber-500">
              RECOMMENDATION CHANGED
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <div>
          <div className="text-xs font-mono text-muted-foreground mb-1">DEMAND Δ</div>
          <div className="flex items-center gap-1">
            {deltaIcon(impact.demand_change)}
            <span className="font-display text-lg">
              {impact.demand_change > 0 ? "+" : ""}{impact.demand_change.toLocaleString()}
            </span>
          </div>
        </div>
        <div>
          <div className="text-xs font-mono text-muted-foreground mb-1">INVENTORY Δ</div>
          <div className="flex items-center gap-1">
            {deltaIcon(impact.inventory_change)}
            <span className="font-display text-lg">
              {impact.inventory_change > 0 ? "+" : ""}{impact.inventory_change.toLocaleString()}
            </span>
          </div>
        </div>
        <div>
          <div className="text-xs font-mono text-muted-foreground mb-1">RISK</div>
          <div className={`text-sm font-medium ${riskColor(scenario.result.risk)}`}>
            {impact.risk_change}
          </div>
        </div>
        <div>
          <div className="text-xs font-mono text-muted-foreground mb-1">CONFIDENCE Δ</div>
          <div className="flex items-center gap-1">
            {deltaIcon(impact.confidence_change)}
            <span className={`font-display text-lg ${
              impact.confidence_change < 0 ? "text-red-500" :
              impact.confidence_change > 0 ? "text-emerald-500" : ""
            }`}>
              {impact.confidence_change > 0 ? "+" : ""}{Math.round(impact.confidence_change * 100)}%
            </span>
          </div>
        </div>
      </div>

      <div className="pt-3 border-t border-foreground/5 grid grid-cols-3 gap-4 text-sm">
        <div>
          <span className="text-muted-foreground">Warehouse: </span>
          <span className={`font-medium ${impact.warehouse_changed ? "text-amber-500" : ""}`}>
            {scenario.result.selected_warehouse}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground">Route: </span>
          <span className={`font-medium ${impact.route_changed ? "text-amber-500" : ""}`}>
            {scenario.result.route}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground">Risk: </span>
          <span className={`font-medium ${riskColor(scenario.result.risk)}`}>
            {scenario.result.risk}
          </span>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------
const CHART_COLORS = ["#22c55e", "#f59e0b", "#ef4444", "#f97316", "#3b82f6"];

const ScenarioBarChart = ({
  baseResult,
  scenarios,
}: {
  baseResult: ScenarioResponse["base_result"];
  scenarios: ScenarioComparison[];
}) => {
  const data = [
    { name: "Base", demand: baseResult.demand_forecast, inventory: baseResult.recommended_inventory },
    ...scenarios.map((s) => ({
      name: s.scenario_name.split(" ")[0],
      demand: s.result.demand_forecast,
      inventory: s.result.recommended_inventory,
    })),
  ];

  return (
    <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
      <div className="text-sm font-mono text-muted-foreground mb-4">DEMAND & INVENTORY COMPARISON</div>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
          <XAxis dataKey="name" tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} axisLine={{ stroke: "var(--muted-foreground)", strokeOpacity: 0.2 }} />
          <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} axisLine={{ stroke: "var(--muted-foreground)", strokeOpacity: 0.2 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
          <Tooltip contentStyle={{ backgroundColor: "var(--background)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--foreground)" }} formatter={(value: number) => value.toLocaleString()} />
          <Legend wrapperStyle={{ color: "var(--muted-foreground)", fontSize: 12 }} />
          <Bar dataKey="demand" name="Demand Forecast" radius={[4, 4, 0, 0]}>
            {data.map((_, i) => <Cell key={i} fill={i === 0 ? "#22c55e" : CHART_COLORS[i] ?? "#6b7280"} fillOpacity={0.8} />)}
          </Bar>
          <Bar dataKey="inventory" name="Inventory Rec." radius={[4, 4, 0, 0]}>
            {data.map((_, i) => <Cell key={i} fill={i === 0 ? "#22c55e" : CHART_COLORS[i] ?? "#6b7280"} fillOpacity={0.4} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

const ConfidenceRadar = ({ agents }: { agents: AgentBreakdownItem[] }) => {
  const data = agents.map((a) => ({
    agent: a.agent_name.replace("Agent", ""),
    confidence: Math.round(a.confidence * 100),
    fullMark: 100,
  }));

  return (
    <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
      <div className="text-sm font-mono text-muted-foreground mb-4">AGENT CONFIDENCE RADAR</div>
      <ResponsiveContainer width="100%" height={320}>
        <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
          <PolarGrid stroke="var(--muted-foreground)" strokeOpacity={0.15} />
          <PolarAngleAxis dataKey="agent" tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} tickFormatter={(v: number) => `${v}%`} />
          <Radar name="Confidence" dataKey="confidence" stroke="#22c55e" fill="#22c55e" fillOpacity={0.25} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Inner content
// ---------------------------------------------------------------------------
function ResultsContent() {
  const searchParams = useSearchParams();
  const simulationId = searchParams.get("id");

  const [data, setData]               = useState<SimulationDetailResponse | null>(null);
  const [scenarioData, setScenarioData] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading]         = useState(true);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [error, setError]             = useState<string | null>(null);

  const fetchResult = async () => {
    if (!simulationId) {
      setError("No simulation ID provided. Please run a simulation first.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getSimulationResult(Number(simulationId));
      setData(result);
      setScenarioLoading(true);
      try {
        const scenarios = await getScenarioComparison(Number(simulationId));
        setScenarioData(scenarios);
      } catch {
        console.warn("Scenario comparison failed");
      } finally {
        setScenarioLoading(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load simulation results.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResult();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simulationId]);

  if (loading) return <ResultsSkeleton />;
  if (error || !data) return <ErrorState message={error ?? "Unknown error"} onRetry={fetchResult} />;

  const { input, result } = data;
  const inventoryDelta = result.recommended_inventory - input.stock;
  const deltaLabel =
    inventoryDelta > 0  ? `+${inventoryDelta.toLocaleString()} units needed`  :
    inventoryDelta < 0  ? `${inventoryDelta.toLocaleString()} units surplus`   :
                          "Inventory at optimal level";

  return (
    <>
      {/* V2.4 — Company / Product context banner */}
      {(data.company_name || data.product_name) && (
        <div className="mb-8 flex flex-wrap items-center gap-3 text-sm border border-foreground/10 rounded-lg px-5 py-3 bg-foreground/2">
          <span className="text-xs font-mono text-muted-foreground">CONTEXT</span>
          {data.company_name && (
            <span className="flex items-center gap-1.5">
              <span className="text-muted-foreground">Company:</span>
              <Link href={`/companies/${data.company_id}`} className="font-display hover:underline">
                {data.company_name}
              </Link>
            </span>
          )}
          {data.company_name && data.product_name && (
            <span className="text-foreground/20">·</span>
          )}
          {data.product_name && (
            <span className="flex items-center gap-1.5">
              <span className="text-muted-foreground">Product:</span>
              <Link
                href={data.company_id ? `/companies/${data.company_id}` : "#"}
                className="font-display hover:underline"
              >
                {data.product_name}
              </Link>
            </span>
          )}
        </div>
      )}
      {/* Overall Confidence */}
      <div className="mb-16">
        <OverallConfidenceBar confidence={result.overall_confidence} />
      </div>

      {/* Key Metrics */}
      <div className="mb-16">
        <h2 className="text-2xl font-display mb-8">Key Metrics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="Demand Forecast" value={result.demand_forecast.toLocaleString()} unit="units" />
          <MetricCard label="Inventory Recommendation" value={result.recommended_inventory.toLocaleString()} unit="units" />
          <MetricCard label="Optimal Warehouse" value={result.selected_warehouse} />
          <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
            <div className="text-sm font-mono text-muted-foreground mb-2">Risk Level</div>
            <div className={`text-3xl lg:text-4xl font-display ${riskColor(result.risk)}`}>{result.risk}</div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="mb-16">
        <h2 className="text-2xl font-display mb-6">Visualizations</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ConfidenceRadar agents={result.agent_breakdown} />
          {scenarioData && (
            <ScenarioBarChart baseResult={scenarioData.base_result} scenarios={scenarioData.scenarios} />
          )}
          {scenarioLoading && (
            <div className="border border-foreground/10 rounded-lg p-6 lg:p-8 flex items-center justify-center">
              <div className="animate-pulse text-muted-foreground">Loading scenario chart…</div>
            </div>
          )}
        </div>
      </div>

      {/* ExplanationAgent Narrative */}
      {result.explanation && (
        <div className="mb-16">
          <h2 className="text-2xl font-display mb-6">Decision Explanation</h2>
          <div className="border border-foreground/10 rounded-lg p-8 lg:p-12 bg-background/50">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-foreground/5 flex items-center justify-center shrink-0 mt-1">
                <Brain className="w-5 h-5" />
              </div>
              <div>
                <div className="text-xs font-mono text-muted-foreground mb-3">EXPLANATION AGENT NARRATIVE</div>
                <p className="text-lg leading-relaxed">{result.explanation}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Agent Breakdown — real backend confidence, no frontend arithmetic */}
      {result.agent_breakdown.length > 0 && (
        <div className="mb-16">
          <h2 className="text-2xl font-display mb-2">Agent Breakdown</h2>
          <p className="text-muted-foreground mb-8">
            Per-agent confidence scores and reasoning from the backend pipeline.
          </p>
          <AgentBreakdown agents={result.agent_breakdown} />
        </div>
      )}

      {/* Pre-computed Scenario Analysis — 4 fixed disruption scenarios from backend */}
      {scenarioData && scenarioData.scenarios.length > 0 && (
        <div className="mb-16">
          <h2 className="text-2xl font-display mb-2">Scenario Analysis</h2>
          <p className="text-muted-foreground mb-8">
            4 disruption scenarios run by the backend agent pipeline. Impact deltas vs base simulation.
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {scenarioData.scenarios.map((scenario) => (
              <ScenarioCard key={scenario.scenario_name} scenario={scenario} />
            ))}
          </div>
        </div>
      )}

      {/* What-If Sandbox — live POST /simulate calls, not JS approximations */}
      <div className="mb-16">
        <h2 className="text-2xl font-display mb-2">What-If Sandbox</h2>
        <p className="text-muted-foreground mb-8">
          Adjust parameters and run the full agent pipeline live. Every result comes directly from the backend.
        </p>
        <ScenarioPanel input={input} result={result} />
      </div>

      {/* Strategy */}
      <div className="mb-16">
        <h2 className="text-2xl font-display mb-6">Strategy Recommendation</h2>
        <div className="border border-foreground/10 rounded-lg p-8 lg:p-12 bg-background/50">
          <div className="space-y-6">
            <div>
              <div className="text-sm font-mono text-muted-foreground mb-3">RECOMMENDATION</div>
              <p className="text-2xl font-display leading-relaxed">{result.strategy}</p>
            </div>
            <div className="grid lg:grid-cols-3 gap-6 pt-6 border-t border-foreground/10">
              <div>
                <div className="text-sm font-mono text-muted-foreground mb-2">ROUTE</div>
                <div className="text-3xl font-display">{result.route}</div>
              </div>
              <div>
                <div className="text-sm font-mono text-muted-foreground mb-2">INVENTORY DELTA</div>
                <div className="text-3xl font-display">{Math.abs(inventoryDelta).toLocaleString()}</div>
                <div className="text-sm text-muted-foreground mt-1">{deltaLabel}</div>
              </div>
              <div>
                <div className="text-sm font-mono text-muted-foreground mb-2">CURRENT STOCK</div>
                <div className="text-3xl font-display">{input.stock.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground mt-1">units</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Simulation Input */}
      <div className="mb-16">
        <h2 className="text-2xl font-display mb-6">Simulation Input</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Product",        value: input.product },
            { label: "Warehouse",      value: input.warehouse },
            { label: "Demand",         value: `${input.demand.toLocaleString()} units` },
            { label: "Stock",          value: `${input.stock.toLocaleString()} units` },
            { label: "Supplier Delay", value: `${input.supplier_delay} days` },
            { label: "Market Trend",   value: input.market_trend },
            { label: "Supply Status",  value: input.supply_status },
            { label: "Season",         value: input.season },
          ].map((item) => (
            <div key={item.label} className="border border-foreground/10 rounded-lg p-4">
              <div className="text-xs font-mono text-muted-foreground mb-1">{item.label.toUpperCase()}</div>
              <div className="text-lg font-display">{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer nav */}
      <div className="flex justify-center">
        <Link href="/form">
          <Button size="lg" className="bg-foreground hover:bg-foreground/90 text-background px-8 h-14 text-base rounded-full">
            New Simulation
          </Button>
        </Link>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function ResultsPage() {
  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <section className="relative py-32">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
          <div className="mb-16">
            <Link href="/form">
              <Button variant="outline" className="mb-6 border-foreground/20 hover:bg-foreground/5">
                <ArrowLeft className="w-4 h-4 mr-2" /> Back to Form
              </Button>
            </Link>
            <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
              <span className="w-8 h-px bg-foreground/30" />
              Results
            </span>
            <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-4">Supply Chain Analysis</h1>
          </div>
          <Suspense fallback={<ResultsSkeleton />}>
            <ResultsContent />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
