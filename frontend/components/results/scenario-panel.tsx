"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Play, TrendingUp, ShieldAlert, Sparkles, RefreshCw, AlertCircle } from "lucide-react";
import { runSimulation, getSimulationResult } from "@/lib/api";
import type { SimulationInput, SimulationResult } from "@/lib/types";

interface ScenarioPanelProps {
  input: SimulationInput;
  result: SimulationResult;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function riskColor(risk: string): string {
  switch (risk) {
    case "High":   return "text-rose-500";
    case "Medium": return "text-amber-500";
    case "Low":    return "text-emerald-500";
    default:       return "text-foreground";
  }
}

function deltaClass(diff: number): string {
  if (diff > 0) return "text-amber-500 font-medium";
  if (diff < 0) return "text-emerald-500 font-medium";
  return "text-muted-foreground";
}

function deltaText(diff: number): string {
  if (diff === 0) return "No change";
  const sign = diff > 0 ? "+" : "";
  return `${sign}${diff.toLocaleString()} units`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ScenarioPanel({ input, result }: ScenarioPanelProps) {
  const [demandMultiplier, setDemandMultiplier] = useState(100);
  const [delayAdder, setDelayAdder]             = useState(0);
  const [stockReduction, setStockReduction]     = useState(0);

  const [activePreset, setActivePreset]   = useState<string | null>(null);
  const [scenarioResult, setScenarioResult] = useState<SimulationResult | null>(null);
  const [isRunning, setIsRunning]          = useState(false);
  const [error, setError]                  = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Core — builds a modified SimulationInput from sliders and calls the
  // real backend pipeline. No arithmetic happens in this file.
  // -------------------------------------------------------------------------
  const executeScenario = async (
    mult: number,
    extraDelay: number,
    stockRed: number,
  ) => {
    setIsRunning(true);
    setError(null);
    setScenarioResult(null);

    // Clamp demand to >= 0, stock to >= 0
    const newDemand  = Math.max(0, Math.round(input.demand * (mult / 100)));
    const newStock   = Math.max(0, Math.round(input.stock * (1 - stockRed / 100)));
    const newDelay   = Math.max(0, input.supplier_delay + extraDelay);

    // Build a modified SimulationInput. Keep product/warehouse/market/season
    // unchanged — only the parameters controlled by the sliders are adjusted.
    const modifiedInput: SimulationInput = {
      product:          input.product,
      stock:            newStock,
      warehouse:        input.warehouse,
      demand:           newDemand,
      supplier_delay:   newDelay,
      market_trend:     input.market_trend,
      supply_status:    input.supply_status,
      season:           input.season,
      // Do not forward twin_id — scenario runs are ephemeral and should not
      // mutate Digital Twin state.
    };

    try {
      // POST /api/v1/simulate → returns simulation_id
      const { simulation_id } = await runSimulation(modifiedInput);
      // GET /api/v1/simulate/{id} → returns full result with agent breakdown
      const detail = await getSimulationResult(simulation_id);
      setScenarioResult(detail.result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scenario run failed");
    } finally {
      setIsRunning(false);
    }
  };

  const applyPreset = (name: string) => {
    setActivePreset(name);
    if (name === "demand_surge") {
      setDemandMultiplier(150); setDelayAdder(0); setStockReduction(0);
      executeScenario(150, 0, 0);
    } else if (name === "supplier_outage") {
      setDemandMultiplier(100); setDelayAdder(4); setStockReduction(0);
      executeScenario(100, 4, 0);
    } else if (name === "stock_shortage") {
      setDemandMultiplier(100); setDelayAdder(0); setStockReduction(50);
      executeScenario(100, 0, 50);
    }
  };

  const handleCustomRun = () => {
    setActivePreset("custom");
    executeScenario(demandMultiplier, delayAdder, stockReduction);
  };

  const reset = () => {
    setActivePreset(null);
    setScenarioResult(null);
    setError(null);
    setDemandMultiplier(100);
    setDelayAdder(0);
    setStockReduction(0);
  };

  return (
    <div className="border border-foreground/10 rounded-lg overflow-hidden bg-card">
      <div className="px-6 py-5 border-b border-foreground/10 flex items-center justify-between">
        <h3 className="text-lg font-display">What-If Scenario Sandbox</h3>
        <span className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-amber-500" />
          LIVE BACKEND SIMULATION
        </span>
      </div>

      <div className="p-6 grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Controls */}
        <div className="lg:col-span-5 space-y-8 border-b lg:border-b-0 lg:border-r border-foreground/10 pb-8 lg:pb-0 lg:pr-8">

          {/* Preset buttons */}
          <div>
            <span className="block text-xs font-mono text-muted-foreground mb-3">SCENARIO PRESETS</span>
            <div className="flex flex-wrap gap-2">
              {[
                { key: "demand_surge",    label: "Demand Surge (+50%)" },
                { key: "supplier_outage", label: "Supplier Delay (+4d)" },
                { key: "stock_shortage",  label: "Stock Cut (-50%)" },
              ].map((p) => (
                <Button
                  key={p.key}
                  variant={activePreset === p.key ? "default" : "outline"}
                  size="sm"
                  className="h-9 px-4 rounded"
                  onClick={() => applyPreset(p.key)}
                  disabled={isRunning}
                >
                  {p.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Sliders */}
          <div className="space-y-6 pt-4 border-t border-foreground/5">
            <span className="block text-xs font-mono text-muted-foreground">CUSTOM PARAMETERS</span>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <span>DEMAND SHIFT</span>
                <span className="text-foreground font-medium">{demandMultiplier}%</span>
              </div>
              <Slider
                value={[demandMultiplier]} min={50} max={200} step={5}
                onValueChange={(v) => { setDemandMultiplier(v[0]); setActivePreset("custom"); }}
                className="py-2"
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <span>EXTRA SUPPLIER DELAY</span>
                <span className="text-foreground font-medium">+{delayAdder} days</span>
              </div>
              <Slider
                value={[delayAdder]} min={0} max={10} step={1}
                onValueChange={(v) => { setDelayAdder(v[0]); setActivePreset("custom"); }}
                className="py-2"
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <span>STOCK AVAILABILITY</span>
                <span className="text-foreground font-medium">-{stockReduction}%</span>
              </div>
              <Slider
                value={[stockReduction]} min={0} max={80} step={5}
                onValueChange={(v) => { setStockReduction(v[0]); setActivePreset("custom"); }}
                className="py-2"
              />
            </div>
          </div>

          {/* Run / Reset */}
          <div className="flex gap-3 pt-2">
            <Button
              onClick={handleCustomRun}
              disabled={isRunning}
              className="bg-foreground hover:bg-foreground/90 text-background px-6 h-11 text-sm rounded flex-1"
            >
              {isRunning ? (
                <><RefreshCw className="w-4 h-4 mr-2 animate-spin" />Running pipeline…</>
              ) : (
                <><Play className="w-3.5 h-3.5 mr-2 fill-current" />Execute Scenario</>
              )}
            </Button>
            {(scenarioResult || error) && (
              <Button variant="outline" onClick={reset} className="h-11 rounded">
                Clear
              </Button>
            )}
          </div>

          {/* Modified input preview */}
          {activePreset && !isRunning && (
            <div className="pt-4 border-t border-foreground/5 space-y-1 text-xs font-mono text-muted-foreground">
              <span className="block mb-1 text-foreground/40">MODIFIED INPUT SENT TO BACKEND</span>
              <div>demand: <span className="text-foreground">{Math.max(0, Math.round(input.demand * (demandMultiplier / 100))).toLocaleString()}</span></div>
              <div>stock: <span className="text-foreground">{Math.max(0, Math.round(input.stock * (1 - stockReduction / 100))).toLocaleString()}</span></div>
              <div>supplier_delay: <span className="text-foreground">{(input.supplier_delay + delayAdder).toFixed(1)} days</span></div>
            </div>
          )}
        </div>

        {/* Results */}
        <div className="lg:col-span-7 flex flex-col justify-center min-h-[300px]">
          <AnimatePresence mode="wait">
            {/* Error */}
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center text-center p-8 border border-red-500/20 rounded-lg bg-red-500/5"
              >
                <AlertCircle className="w-10 h-10 text-red-500 mb-4" />
                <p className="text-sm text-muted-foreground max-w-sm">{error}</p>
              </motion.div>
            )}

            {/* Loading */}
            {isRunning && !error && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center text-center p-8"
              >
                <RefreshCw className="w-8 h-8 text-muted-foreground animate-spin mb-4" />
                <p className="text-sm text-muted-foreground">
                  Running multi-agent pipeline with modified parameters…
                </p>
              </motion.div>
            )}

            {/* Empty state */}
            {!scenarioResult && !isRunning && !error && (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center text-center p-8 border border-dashed border-foreground/10 rounded-lg bg-background/20"
              >
                <TrendingUp className="w-12 h-12 text-muted-foreground mb-4 opacity-40" />
                <h4 className="text-base font-display font-medium mb-1">No Active Scenario</h4>
                <p className="text-sm text-muted-foreground max-w-sm">
                  Apply a preset or adjust parameters and run to compare against your baseline.
                  Results come from the live agent pipeline, not estimates.
                </p>
              </motion.div>
            )}

            {/* Results */}
            {scenarioResult && !isRunning && !error && (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.35, ease: "easeOut" }}
                className="space-y-5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-muted-foreground">COMPARISON TO BASELINE</span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-500">
                    LIVE PIPELINE RESULT
                  </span>
                </div>

                {/* Metric grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-foreground/5 rounded p-4 bg-background/30 flex flex-col justify-between">
                    <span className="block text-xs font-mono text-muted-foreground">DEMAND FORECAST</span>
                    <span className="block text-xl font-display font-medium mt-1">
                      {scenarioResult.demand_forecast.toLocaleString()}
                      <span className="text-xs text-muted-foreground ml-1.5">units</span>
                    </span>
                    <div className="mt-3 pt-2 border-t border-foreground/5 text-xs">
                      <span className="text-muted-foreground">Δ from base: </span>
                      <span className={deltaClass(scenarioResult.demand_forecast - result.demand_forecast)}>
                        {deltaText(Math.round(scenarioResult.demand_forecast - result.demand_forecast))}
                      </span>
                    </div>
                  </div>

                  <div className="border border-foreground/5 rounded p-4 bg-background/30 flex flex-col justify-between">
                    <span className="block text-xs font-mono text-muted-foreground">INVENTORY RECOMMENDATION</span>
                    <span className="block text-xl font-display font-medium mt-1">
                      {scenarioResult.recommended_inventory.toLocaleString()}
                      <span className="text-xs text-muted-foreground ml-1.5">units</span>
                    </span>
                    <div className="mt-3 pt-2 border-t border-foreground/5 text-xs">
                      <span className="text-muted-foreground">Δ from base: </span>
                      <span className={deltaClass(scenarioResult.recommended_inventory - result.recommended_inventory)}>
                        {deltaText(Math.round(scenarioResult.recommended_inventory - result.recommended_inventory))}
                      </span>
                    </div>
                  </div>

                  <div className="border border-foreground/5 rounded p-4 bg-background/30">
                    <span className="block text-xs font-mono text-muted-foreground">WAREHOUSE / ROUTE</span>
                    <span className="block text-lg font-display font-medium mt-1">
                      {scenarioResult.selected_warehouse}
                      {scenarioResult.selected_warehouse !== result.selected_warehouse && (
                        <span className="text-xs text-amber-500 font-mono ml-2">
                          ← was {result.selected_warehouse}
                        </span>
                      )}
                    </span>
                    <span className="text-sm text-muted-foreground">{scenarioResult.route}</span>
                  </div>

                  <div className="border border-foreground/5 rounded p-4 bg-background/30 flex items-center justify-between">
                    <div>
                      <span className="block text-xs font-mono text-muted-foreground">RISK · CONFIDENCE</span>
                      <span className={`block text-lg font-display font-medium mt-1 ${riskColor(scenarioResult.risk)}`}>
                        {scenarioResult.risk}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {Math.round(scenarioResult.overall_confidence * 100)}% confidence
                      </span>
                    </div>
                    {scenarioResult.risk !== result.risk && (
                      <ShieldAlert className={`w-5 h-5 shrink-0 ${scenarioResult.risk === "High" ? "text-rose-500" : "text-amber-500"}`} />
                    )}
                  </div>
                </div>

                {/* Strategy */}
                <div className="border border-foreground/10 rounded-lg p-5 bg-foreground/2">
                  <span className="block text-xs font-mono text-muted-foreground mb-2">STRATEGY RECOMMENDATION</span>
                  <p className="text-sm leading-relaxed text-foreground">
                    {scenarioResult.strategy}
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
