import { z } from "zod";

/**
 * SynChain — Form validation schema.
 *
 * Field names match backend SimulationInput exactly (no mapping needed).
 * Uses `coerce` for numeric fields so HTML string inputs are auto-converted.
 */
export const simulationSchema = z.object({
  product: z
    .string()
    .min(1, "Product name is required")
    .max(100, "Product name must be under 100 characters"),

  stock: z
    .number({ coerce: true, message: "Stock must be a number" })
    .min(0, "Stock cannot be negative"),

  warehouse: z.enum(["W1", "W2", "W3"], {
    message: "Please select a warehouse",
  }),

  demand: z
    .number({ coerce: true, message: "Demand must be a number" })
    .min(1, "Demand must be greater than 0"),

  supplier_delay: z
    .number({ coerce: true, message: "Supplier delay must be a number" })
    .min(0, "Delay cannot be negative")
    .max(365, "Delay seems unrealistic (max 365 days)"),

  market_trend: z.enum(["Positive", "Neutral", "Negative"], {
    message: "Please select a market trend",
  }),

  supply_status: z.enum(["High", "Medium", "Low"], {
    message: "Please select supply status",
  }),

  season: z.enum(["Festival", "Normal", "Off-season"], {
    message: "Please select a season",
  }),
});

export type SimulationFormData = z.infer<typeof simulationSchema>;
