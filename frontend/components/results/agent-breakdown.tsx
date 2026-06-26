"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, BarChart3, ShieldAlert, Cpu, Truck, Brain, Clock, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import type { AgentBreakdownItem } from "@/lib/types";

interface AgentBreakdownProps {
  agents: AgentBreakdownItem[];
}

// ---------------------------------------------------------------------------
// Helpers — all values come from backend AgentBreakdownItem, no arithmetic here
// ---------------------------------------------------------------------------

function confidenceColor(score: number): string {
  // score is 0–1 from backend
  if (score >= 0.9) return "text-emerald-500 bg-emerald-500/10 border-emerald-500/20";
  if (score >= 0.75) return "text-amber-500 bg-amber-500/10 border-amber-500/20";
  return "text-rose-500 bg-rose-500/10 border-rose-500/20";
}

function confidenceProgressColor(score: number): string {
  if (score >= 0.9) return "bg-emerald-500";
  if (score >= 0.75) return "bg-amber-500";
  return "bg-rose-500";
}

function agentIcon(name: string) {
  switch (name) {
    case "DemandAgent":    return <BarChart3 className="w-5 h-5 text-muted-foreground" />;
    case "InventoryAgent": return <Cpu className="w-5 h-5 text-muted-foreground" />;
    case "LogisticsAgent": return <Truck className="w-5 h-5 text-muted-foreground" />;
    case "RiskAgent":      return <ShieldAlert className="w-5 h-5 text-muted-foreground" />;
    default:               return <Brain className="w-5 h-5 text-muted-foreground" />;
  }
}

function agentTitle(name: string): string {
  switch (name) {
    case "DemandAgent":    return "DEMAND AGENT";
    case "InventoryAgent": return "INVENTORY AGENT";
    case "LogisticsAgent": return "LOGISTICS AGENT";
    case "RiskAgent":      return "RISK AGENT";
    default:               return name.replace("Agent", " AGENT").toUpperCase();
  }
}

function statusIcon(status: string) {
  switch (status) {
    case "success": return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
    case "warning": return <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />;
    case "failed":  return <XCircle className="w-3.5 h-3.5 text-red-500" />;
    default:        return <CheckCircle2 className="w-3.5 h-3.5 text-muted-foreground" />;
  }
}

function formatValue(val: unknown): string {
  if (typeof val === "number") {
    return Number.isInteger(val)
      ? val.toLocaleString()
      : val.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  if (typeof val === "object" && val !== null) return JSON.stringify(val);
  return String(val);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentBreakdown({ agents }: AgentBreakdownProps) {
  const [expandedId, setExpandedId] = useState<string | null>(
    agents.length > 0 ? agents[0].agent_name : null
  );

  return (
    <div className="border border-foreground/10 rounded-lg overflow-hidden bg-card">
      <div className="px-6 py-5 border-b border-foreground/10 flex items-center justify-between">
        <h3 className="text-lg font-display">Multi-Agent Pipeline Details</h3>
        <span className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          {agents.length} AGENTS ACTIVE
        </span>
      </div>

      <div className="divide-y divide-foreground/10">
        {agents.map((agent) => {
          const isExpanded = expandedId === agent.agent_name;
          // confidence comes from backend as 0–1 float
          const pct = Math.round(agent.confidence * 100);

          return (
            <div key={agent.agent_name} className="transition-colors hover:bg-foreground/1">
              <button
                type="button"
                onClick={() => setExpandedId(isExpanded ? null : agent.agent_name)}
                className="w-full px-6 py-5 flex items-center justify-between text-left"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded border border-foreground/10 flex items-center justify-center bg-background/50">
                    {agentIcon(agent.agent_name)}
                  </div>
                  <div>
                    <span className="block text-xs font-mono text-muted-foreground tracking-wider">
                      {agentTitle(agent.agent_name)}
                    </span>
                    <h4 className="text-base font-display font-medium mt-0.5">
                      {agent.agent_name.replace("Agent", " Agent")}
                    </h4>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className="hidden sm:flex items-center gap-3">
                    <span className="text-sm font-mono text-muted-foreground">Confidence</span>
                    <span className={`text-xs font-mono px-2 py-0.5 rounded border ${confidenceColor(agent.confidence)}`}>
                      {pct}%
                    </span>
                  </div>
                  <motion.div
                    animate={{ rotate: isExpanded ? 180 : 0 }}
                    transition={{ duration: 0.3, ease: "easeInOut" }}
                  >
                    <ChevronDown className="w-5 h-5 text-muted-foreground" />
                  </motion.div>
                </div>
              </button>

              <AnimatePresence initial={false}>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                    className="overflow-hidden"
                  >
                    <div className="px-6 pb-6 pt-2 border-t border-foreground/5 space-y-6">

                      {/* Execution metadata */}
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        {statusIcon(agent.status)}
                        <span>{agent.status}</span>
                        <span className="text-foreground/20">·</span>
                        <Clock className="w-3 h-3" />
                        <span>{agent.execution_ms.toFixed(1)}ms</span>
                      </div>

                      {/* Confidence bar */}
                      <div className="border border-foreground/5 rounded p-4 bg-background/30">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-mono text-muted-foreground">DECISION CONFIDENCE</span>
                          <span className="text-sm font-mono font-medium">{pct}%</span>
                        </div>
                        <div className="h-1.5 w-full bg-background rounded-full overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${pct}%` }}
                            transition={{ duration: 0.8, delay: 0.1, ease: "easeOut" }}
                            className={`h-full ${confidenceProgressColor(agent.confidence)}`}
                          />
                        </div>
                      </div>

                      {/* Input / Output grid */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <span className="block text-xs font-mono text-muted-foreground mb-2">INPUT PARAMETERS</span>
                          <div className="space-y-1">
                            {Object.entries(agent.input_summary).map(([k, v]) => (
                              <div key={k} className="text-sm">
                                <span className="text-muted-foreground">{k.replace(/_/g, " ")}:</span>{" "}
                                <span className="font-medium">{formatValue(v)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <span className="block text-xs font-mono text-muted-foreground mb-2">OUTPUT DATA</span>
                          <div className="space-y-1">
                            {Object.entries(agent.output_data)
                              .filter(([k]) => k !== "warehouse_scores")
                              .map(([k, v]) => (
                                <div key={k} className="text-sm">
                                  <span className="text-muted-foreground">{k.replace(/_/g, " ")}:</span>{" "}
                                  <span className="font-display font-medium">{formatValue(v)}</span>
                                </div>
                              ))}
                          </div>
                        </div>
                      </div>

                      {/* Explanation */}
                      <div>
                        <span className="block text-xs font-mono text-muted-foreground mb-2">EXPLANATORY REASONING</span>
                        <p className="text-muted-foreground leading-relaxed text-sm">
                          {agent.explanation}
                        </p>
                      </div>

                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}
