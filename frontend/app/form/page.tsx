"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowRight, Loader2, Cpu, RefreshCw, Plus,
  AlertCircle, CheckCircle2, Building2, Package, Zap,
} from "lucide-react";
import { simulationSchema, type SimulationFormData } from "@/lib/validations";
import {
  runSimulation,
  listTwins,
  listCompanies,
  listCompanyProducts,
  listCompanySuppliers,
  listCompanyWarehouses,
  createTwin,
} from "@/lib/api";
import type { TwinSummary, Company, Product, Supplier, CompanyWarehouse } from "@/lib/types";
import { toast } from "sonner";

export default function FormPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ---------------------------------------------------------------------------
  // V2.4 — Company + Product selector (top of form, drives auto-fill)
  // ---------------------------------------------------------------------------
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);

  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);

  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [suppliersLoading, setSuppliersLoading] = useState(false);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null);

  const [companyWarehouses, setCompanyWarehouses] = useState<CompanyWarehouse[]>([]);
  const [warehousesLoading, setWarehousesLoading] = useState(false);
  const [selectedWarehouseDbId, setSelectedWarehouseDbId] = useState<number | null>(null);

  // ---------------------------------------------------------------------------
  // Intelligence Integration — Digital Twin (bottom of form)
  // ---------------------------------------------------------------------------
  const [twinEnabled, setTwinEnabled] = useState(false);
  const [selectedTwinId, setSelectedTwinId] = useState<number | null>(null);
  const [twins, setTwins] = useState<TwinSummary[]>([]);
  const [twinsLoading, setTwinsLoading] = useState(false);
  const [twinsError, setTwinsError] = useState<string | null>(null);
  const [isCreatingTwin, setIsCreatingTwin] = useState(false);

  // ---------------------------------------------------------------------------
  // Form
  // ---------------------------------------------------------------------------
  const {
    register,
    handleSubmit,
    setValue,
    reset,
    watch,
    formState: { errors },
  } = useForm<SimulationFormData>({
    resolver: zodResolver(simulationSchema),
    defaultValues: {
      product: "",
      stock: undefined,
      warehouse: undefined,
      demand: undefined,
      supplier_delay: undefined,
      market_trend: undefined,
      supply_status: undefined,
      season: undefined,
    },
  });

  // ---------------------------------------------------------------------------
  // Load companies on mount — always visible at top of form
  // ---------------------------------------------------------------------------
  useEffect(() => {
    (async () => {
      setCompaniesLoading(true);
      try {
        const data = await listCompanies(50, 0);
        setCompanies(data.companies);
        if (data.companies.length === 1) {
          setSelectedCompanyId(data.companies[0].id);
        }
      } catch {
        // Non-blocking
      } finally {
        setCompaniesLoading(false);
      }
    })();
  }, []);

  // Load products when company changes
  useEffect(() => {
    setSelectedProductId(null);
    setProducts([]);
    setSelectedSupplierId(null);
    setSuppliers([]);
    setSelectedWarehouseDbId(null);
    setCompanyWarehouses([]);
    if (!selectedCompanyId) return;
    (async () => {
      setProductsLoading(true);
      setSuppliersLoading(true);
      setWarehousesLoading(true);
      try {
        const [prodData, suppData, whData] = await Promise.all([
          listCompanyProducts(selectedCompanyId),
          listCompanySuppliers(selectedCompanyId),
          listCompanyWarehouses(selectedCompanyId),
        ]);
        setProducts(prodData.products);
        setSuppliers(suppData.suppliers);
        setCompanyWarehouses(whData.warehouses);
      } catch {
        // Non-blocking
      } finally {
        setProductsLoading(false);
        setSuppliersLoading(false);
        setWarehousesLoading(false);
      }
    })();
  }, [selectedCompanyId]);

  // Auto-fill stock + demand when product is selected
  useEffect(() => {
    if (!selectedProductId) return;
    const product = products.find((p) => p.id === selectedProductId);
    if (!product) return;
    setValue("product", product.name, { shouldValidate: true });
    setValue("stock", product.current_stock, { shouldValidate: true });
    setValue("demand", product.avg_monthly_demand, { shouldValidate: true });
  }, [selectedProductId, products, setValue]);

  // Auto-fill supplier_delay + supply_status when supplier is selected
  useEffect(() => {
    if (!selectedSupplierId) return;
    const supplier = suppliers.find((s) => s.id === selectedSupplierId);
    if (!supplier) return;
    setValue("supplier_delay", supplier.lead_time_days, { shouldValidate: true });
    setValue("supply_status", supplier.supply_status as SimulationFormData["supply_status"], { shouldValidate: true });
  }, [selectedSupplierId, suppliers, setValue]);

  // Auto-fill warehouse when warehouse is selected
  useEffect(() => {
    if (!selectedWarehouseDbId) return;
    const wh = companyWarehouses.find((w) => w.id === selectedWarehouseDbId);
    if (!wh) return;
    setValue("warehouse", wh.warehouse_id as SimulationFormData["warehouse"], { shouldValidate: true });
  }, [selectedWarehouseDbId, companyWarehouses, setValue]);

  // Load twins filtered by selected company
  const loadTwins = async () => {
    setTwinsLoading(true);
    setTwinsError(null);
    try {
      const data = await listTwins(selectedCompanyId ?? undefined);
      setTwins(data);
      if (data.length > 0 && selectedTwinId === null) {
        setSelectedTwinId(data[0].id);
      }
    } catch (e) {
      setTwinsError(e instanceof Error ? e.message : "Failed to load Digital Twins");
    } finally {
      setTwinsLoading(false);
    }
  };

  useEffect(() => {
    if (twinEnabled) {
      setSelectedTwinId(null);
      setTwins([]);
      loadTwins();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [twinEnabled, selectedCompanyId]);

  const handleCreateTwin = async () => {
    const product = watch("product");
    const twinName = product ? `${product} Twin` : "New Supply Chain Twin";
    setIsCreatingTwin(true);
    try {
      const newTwin = await createTwin(twinName, selectedCompanyId ?? null);
      setTwins((prev) => [newTwin, ...prev]);
      setSelectedTwinId(newTwin.id);
      toast.success("Digital Twin Created", {
        description: `"${newTwin.name}" is ready.`,
      });
    } catch (e) {
      toast.error("Failed to create twin", {
        description: e instanceof Error ? e.message : "Unknown error",
      });
    } finally {
      setIsCreatingTwin(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Submit
  // ---------------------------------------------------------------------------
  const onSubmit = async (data: SimulationFormData) => {
    setIsSubmitting(true);
    try {
      const payload = {
        ...data,
        twin_id: twinEnabled && selectedTwinId != null ? selectedTwinId : null,
        product_id: selectedProductId ?? null,
        company_id: selectedCompanyId ?? null,
        supplier_id: selectedSupplierId ?? null,
        warehouse_record_id: selectedWarehouseDbId ?? null,
      };
      const response = await runSimulation(payload);
      router.push(`/results?id=${response.simulation_id}`);
    } catch (err) {
      toast.error("Simulation Failed", {
        description: err instanceof Error ? err.message : "Simulation failed. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    reset();
    setSelectedCompanyId(null);
    setSelectedProductId(null);
    setSelectedSupplierId(null);
    setSelectedWarehouseDbId(null);
    setTwinEnabled(false);
    setSelectedTwinId(null);
    setTwins([]);
  };

  const FieldError = ({ message }: { message?: string }) =>
    message ? <p className="text-sm text-destructive mt-1">{message}</p> : null;

  const selectedTwin = twins.find((t) => t.id === selectedTwinId);
  const selectedProduct = products.find((p) => p.id === selectedProductId);
  const selectedCompany = companies.find((c) => c.id === selectedCompanyId);
  const selectedSupplier = suppliers.find((s) => s.id === selectedSupplierId);
  const selectedWarehouse = companyWarehouses.find((w) => w.id === selectedWarehouseDbId);

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <section className="relative min-h-[calc(100vh-100px)] flex items-center py-32">
        <div className="max-w-[1400px] mx-auto w-full px-6 lg:px-12">
          <div className="max-w-2xl">

            {/* Header */}
            <div className="mb-16">
              <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
                <span className="w-8 h-px bg-foreground/30" />
                Simulation
              </span>
              <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-4">
                Run Simulation
              </h1>
              <p className="text-lg text-muted-foreground">
                Select a company and product to auto-fill stock and demand, or enter values manually.
              </p>
            </div>

            <form
              onSubmit={handleSubmit(onSubmit)}
              className="bg-background border border-foreground/10 rounded-lg p-8 space-y-6"
            >

              {/* ================================================================
                  V2.4 — PRODUCT CONTEXT (top of form, drives auto-fill)
               ================================================================ */}
              <div className="space-y-4 pb-4 border-b border-foreground/10">
                <div className="flex items-center gap-3">
                  <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground">
                    <span className="w-8 h-px bg-foreground/30" />
                    Product Context
                  </span>
                  {selectedProduct && (
                    <span className="ml-auto text-xs text-emerald-500 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      Stock &amp; demand auto-filled
                    </span>
                  )}
                </div>

                {/* Company */}
                <div className="space-y-2">
                  <Label className="text-sm flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5 text-muted-foreground" />
                    Company
                    <span className="text-muted-foreground text-xs font-normal">(optional)</span>
                  </Label>
                  {companiesLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground h-10">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Loading…
                    </div>
                  ) : companies.length === 0 ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground border border-foreground/10 rounded-lg px-3 py-2.5">
                      <Building2 className="w-3.5 h-3.5 opacity-50" />
                      No companies —{" "}
                      <a href="/companies/new" className="underline hover:text-foreground">create one</a>
                      {" "}to enable auto-fill
                    </div>
                  ) : (
                    <Select
                      value={selectedCompanyId?.toString() ?? "none"}
                      onValueChange={(v) => setSelectedCompanyId(v === "none" ? null : Number(v))}
                      disabled={isSubmitting}
                    >
                      <SelectTrigger className="text-sm px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Building2 className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <SelectValue placeholder="Select company" />
                        </div>
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">
                          <span className="text-muted-foreground">No company</span>
                        </SelectItem>
                        {companies.map((c) => (
                          <SelectItem key={c.id} value={c.id.toString()}>
                            <span className="flex items-center gap-2">
                              <span>{c.name}</span>
                              {c.industry && (
                                <span className="text-xs text-muted-foreground font-mono">{c.industry}</span>
                              )}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                {/* Product — only shown when a company is selected */}
                {selectedCompanyId && (
                  <div className="space-y-2">
                    <Label className="text-sm flex items-center gap-1.5">
                      <Package className="w-3.5 h-3.5 text-muted-foreground" />
                      Product
                      <span className="text-muted-foreground text-xs font-normal">
                        — auto-fills stock &amp; demand
                      </span>
                    </Label>
                    {productsLoading ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground h-10">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Loading products…
                      </div>
                    ) : products.length === 0 ? (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground border border-foreground/10 rounded-lg px-3 py-2.5">
                        <Package className="w-3.5 h-3.5 opacity-50" />
                        No products for {selectedCompany?.name} —{" "}
                        <a href={`/companies/${selectedCompanyId}`} className="underline hover:text-foreground">
                          add products
                        </a>
                      </div>
                    ) : (
                      <Select
                        value={selectedProductId?.toString() ?? "none"}
                        onValueChange={(v) => setSelectedProductId(v === "none" ? null : Number(v))}
                        disabled={isSubmitting}
                      >
                        <SelectTrigger className="text-sm px-3 py-2">
                          <div className="flex items-center gap-2">
                            <Package className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                            <SelectValue placeholder="Select product to auto-fill" />
                          </div>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">
                            <span className="text-muted-foreground">Enter manually</span>
                          </SelectItem>
                          {products.map((p) => (
                            <SelectItem key={p.id} value={p.id.toString()}>
                              <span className="flex items-center gap-3">
                                <span>{p.name}</span>
                                <span className="text-xs text-muted-foreground font-mono">
                                  Stock: {p.current_stock.toLocaleString()} · Demand: {p.avg_monthly_demand.toLocaleString()}
                                </span>
                              </span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}

                    {/* Selected product confirmation */}
                    {selectedProduct && (
                      <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-lg px-3 py-2 flex items-center gap-3">
                        <Package className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                        <div className="text-xs">
                          <span className="text-emerald-500 font-medium">{selectedProduct.name}</span>
                          <span className="text-muted-foreground ml-2">
                            Stock: {selectedProduct.current_stock.toLocaleString()} · Demand: {selectedProduct.avg_monthly_demand.toLocaleString()}
                            {selectedProduct.category && ` · ${selectedProduct.category}`}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedProductId(null)}
                          className="ml-auto text-xs text-muted-foreground hover:text-foreground"
                        >
                          Clear
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* ── Supplier selector — shown when company has suppliers ── */}
              {selectedCompanyId && suppliers.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm flex items-center gap-1.5">
                    <span>🚚</span>
                    Supplier
                    <span className="text-muted-foreground text-xs font-normal">— auto-fills lead time &amp; supply status</span>
                  </Label>
                  <Select
                    value={selectedSupplierId?.toString() ?? "none"}
                    onValueChange={(v) => setSelectedSupplierId(v === "none" ? null : Number(v))}
                    disabled={isSubmitting || suppliersLoading}
                  >
                    <SelectTrigger className="text-sm px-3 py-2">
                      <SelectValue placeholder="Select supplier to auto-fill" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">
                        <span className="text-muted-foreground">Enter manually</span>
                      </SelectItem>
                      {suppliers.map((s) => (
                        <SelectItem key={s.id} value={s.id.toString()}>
                          <span className="flex items-center gap-3">
                            <span>{s.name}</span>
                            <span className="text-xs text-muted-foreground font-mono">
                              {s.lead_time_days}d · {s.supply_status} · {s.reliability_pct}%
                            </span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {selectedSupplier && (
                    <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-lg px-3 py-2 flex items-center gap-3">
                      <span className="text-emerald-500 text-xs">🚚</span>
                      <div className="text-xs">
                        <span className="text-emerald-500 font-medium">{selectedSupplier.name}</span>
                        <span className="text-muted-foreground ml-2">
                          Lead time: {selectedSupplier.lead_time_days}d · Status: {selectedSupplier.supply_status} · Reliability: {selectedSupplier.reliability_pct}%
                        </span>
                      </div>
                      <button type="button" onClick={() => setSelectedSupplierId(null)} className="ml-auto text-xs text-muted-foreground hover:text-foreground">Clear</button>
                    </div>
                  )}
                </div>
              )}

              {/* ── Warehouse selector — shown when company has warehouses ── */}
              {selectedCompanyId && companyWarehouses.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm flex items-center gap-1.5">
                    <span>🏭</span>
                    Warehouse
                    <span className="text-muted-foreground text-xs font-normal">— auto-fills warehouse slot</span>
                  </Label>
                  <Select
                    value={selectedWarehouseDbId?.toString() ?? "none"}
                    onValueChange={(v) => setSelectedWarehouseDbId(v === "none" ? null : Number(v))}
                    disabled={isSubmitting || warehousesLoading}
                  >
                    <SelectTrigger className="text-sm px-3 py-2">
                      <SelectValue placeholder="Select warehouse to auto-fill" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">
                        <span className="text-muted-foreground">Enter manually</span>
                      </SelectItem>
                      {companyWarehouses.map((w) => (
                        <SelectItem key={w.id} value={w.id.toString()}>
                          <span className="flex items-center gap-3">
                            <span>{w.name}</span>
                            <span className="text-xs text-muted-foreground font-mono">
                              {w.warehouse_id}{w.location ? ` · ${w.location}` : ""} · {w.capacity.toLocaleString()} cap
                            </span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {selectedWarehouse && (
                    <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-lg px-3 py-2 flex items-center gap-3">
                      <span className="text-emerald-500 text-xs">🏭</span>
                      <div className="text-xs">
                        <span className="text-emerald-500 font-medium">{selectedWarehouse.name}</span>
                        <span className="text-muted-foreground ml-2">
                          Slot: {selectedWarehouse.warehouse_id}{selectedWarehouse.location ? ` · ${selectedWarehouse.location}` : ""} · Capacity: {selectedWarehouse.capacity.toLocaleString()}
                        </span>
                      </div>
                      <button type="button" onClick={() => setSelectedWarehouseDbId(null)} className="ml-auto text-xs text-muted-foreground hover:text-foreground">Clear</button>
                    </div>
                  )}
                </div>
              )}
            

              {/* Product Name */}
              <div className="space-y-2">
                <Label htmlFor="product" className="text-base">
                  Product Name
                  {selectedProduct && (
                    <span className="ml-2 text-xs text-emerald-500 font-normal font-mono">auto-filled</span>
                  )}
                </Label>
                <Input
                  id="product"
                  placeholder="e.g., Electronics, Textiles"
                  {...register("product")}
                  className="text-base px-4 py-3"
                  disabled={isSubmitting}
                />
                <FieldError message={errors.product?.message} />
              </div>

              {/* Stock */}
              <div className="space-y-2">
                <Label htmlFor="stock" className="text-base">
                  Current Stock
                  {selectedProduct && (
                    <span className="ml-2 text-xs text-emerald-500 font-normal font-mono">
                      auto-filled from {selectedProduct.name}
                    </span>
                  )}
                </Label>
                <Input
                  id="stock"
                  type="number"
                  placeholder="e.g., 5000"
                  {...register("stock", { valueAsNumber: true })}
                  className="text-base px-4 py-3"
                  disabled={isSubmitting}
                />
                <FieldError message={errors.stock?.message} />
              </div>

              {/* Warehouse */}
              <div className="space-y-2">
                <Label htmlFor="warehouse" className="text-base">
                  Warehouse
                  {selectedWarehouse && (
                    <span className="ml-2 text-xs text-emerald-500 font-normal font-mono">
                      auto-filled from {selectedWarehouse.name}
                    </span>
                  )}
                </Label>
                <Select
                  value={watch("warehouse") || ""}
                  onValueChange={(v) => setValue("warehouse", v as SimulationFormData["warehouse"], { shouldValidate: true })}
                  disabled={isSubmitting}
                >
                  <SelectTrigger id="warehouse" className="text-base px-4 py-3">
                    <SelectValue placeholder="Select warehouse" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="W1">Warehouse 1 (W1)</SelectItem>
                    <SelectItem value="W2">Warehouse 2 (W2)</SelectItem>
                    <SelectItem value="W3">Warehouse 3 (W3)</SelectItem>
                  </SelectContent>
                </Select>
                <FieldError message={errors.warehouse?.message} />
              </div>

              {/* Demand */}
              <div className="space-y-2">
                <Label htmlFor="demand" className="text-base">
                  Last Week Demand
                  {selectedProduct && (
                    <span className="ml-2 text-xs text-emerald-500 font-normal font-mono">
                      auto-filled from {selectedProduct.name}
                    </span>
                  )}
                </Label>
                <Input
                  id="demand"
                  type="number"
                  placeholder="e.g., 1200"
                  {...register("demand", { valueAsNumber: true })}
                  className="text-base px-4 py-3"
                  disabled={isSubmitting}
                />
                <FieldError message={errors.demand?.message} />
              </div>

              {/* Supplier Delay */}
              <div className="space-y-2">
                <Label htmlFor="supplier_delay" className="text-base">
                  Supplier Delivery Time (days)
                  {selectedSupplier && (
                    <span className="ml-2 text-xs text-emerald-500 font-normal font-mono">
                      auto-filled from {selectedSupplier.name}
                    </span>
                  )}
                </Label>
                <Input
                  id="supplier_delay"
                  type="number"
                  step="0.5"
                  placeholder="e.g., 7"
                  {...register("supplier_delay", { valueAsNumber: true })}
                  className="text-base px-4 py-3"
                  disabled={isSubmitting}
                />
                <FieldError message={errors.supplier_delay?.message} />
              </div>

              {/* Market Context */}
              <div className="pt-4 border-t border-foreground/10">
                <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
                  <span className="w-8 h-px bg-foreground/30" />
                  Market Context
                </span>
              </div>

              {/* Market Trend */}
              <div className="space-y-2">
                <Label htmlFor="marketTrend" className="text-base">Market Trend</Label>
                <Select
                  value={watch("market_trend") || ""}
                  onValueChange={(v) => setValue("market_trend", v as SimulationFormData["market_trend"], { shouldValidate: true })}
                  disabled={isSubmitting}
                >
                  <SelectTrigger id="marketTrend" className="text-base px-4 py-3">
                    <SelectValue placeholder="Select market trend" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Positive">Positive</SelectItem>
                    <SelectItem value="Neutral">Neutral</SelectItem>
                    <SelectItem value="Negative">Negative</SelectItem>
                  </SelectContent>
                </Select>
                <FieldError message={errors.market_trend?.message} />
              </div>

              {/* Supply Status */}
              <div className="space-y-2">
                <Label htmlFor="supplyStatus" className="text-base">
                  Supply Status
                  {selectedSupplier && (
                    <span className="ml-2 text-xs text-emerald-500 font-normal font-mono">
                      auto-filled from {selectedSupplier.name}
                    </span>
                  )}
                </Label>
                <Select
                  value={watch("supply_status") || ""}
                  onValueChange={(v) => setValue("supply_status", v as SimulationFormData["supply_status"], { shouldValidate: true })}
                  disabled={isSubmitting}
                >
                  <SelectTrigger id="supplyStatus" className="text-base px-4 py-3">
                    <SelectValue placeholder="Select supply status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="High">High</SelectItem>
                    <SelectItem value="Medium">Medium</SelectItem>
                    <SelectItem value="Low">Low</SelectItem>
                  </SelectContent>
                </Select>
                <FieldError message={errors.supply_status?.message} />
              </div>

              {/* Season */}
              <div className="space-y-2">
                <Label htmlFor="season" className="text-base">Season</Label>
                <Select
                  value={watch("season") || ""}
                  onValueChange={(v) => setValue("season", v as SimulationFormData["season"], { shouldValidate: true })}
                  disabled={isSubmitting}
                >
                  <SelectTrigger id="season" className="text-base px-4 py-3">
                    <SelectValue placeholder="Select season" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Festival">Festival</SelectItem>
                    <SelectItem value="Normal">Normal</SelectItem>
                    <SelectItem value="Off-season">Off-season</SelectItem>
                  </SelectContent>
                </Select>
                <FieldError message={errors.season?.message} />
              </div>

              {/* Intelligence Integration */}
              <div className="pt-4 border-t border-foreground/10">
                <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
                  <span className="w-8 h-px bg-foreground/30" />
                  Intelligence Integration
                </span>

                {/* Toggle */}
                <div className="flex items-start gap-3 mb-4">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={twinEnabled}
                    onClick={() => { setTwinEnabled((v) => !v); if (twinEnabled) setSelectedTwinId(null); }}
                    disabled={isSubmitting}
                    className={`relative mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                      twinEnabled ? "bg-foreground" : "bg-foreground/20"
                    } ${isSubmitting ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                  >
                    <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-background transition-transform ${twinEnabled ? "translate-x-4.5" : "translate-x-0.5"}`} />
                  </button>
                  <div>
                    <span className="text-base font-medium">Enable Digital Twin</span>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      Links this simulation to a Digital Twin to generate signals, forecasts, and compound intelligence.
                    </p>
                  </div>
                </div>

                {twinEnabled && (
                  <div className="ml-12 space-y-3">
                    {twinsLoading && (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="w-4 h-4 animate-spin" />Loading Digital Twins…
                      </div>
                    )}
                    {!twinsLoading && twinsError && (
                      <div className="border border-destructive/20 bg-destructive/5 rounded-lg p-3 flex items-center gap-3">
                        <AlertCircle className="w-4 h-4 text-destructive shrink-0" />
                        <span className="text-sm text-destructive">{twinsError}</span>
                        <Button type="button" variant="outline" size="sm" onClick={loadTwins} className="ml-auto gap-1 border-destructive/20 text-xs h-7">
                          <RefreshCw className="w-3 h-3" /> Retry
                        </Button>
                      </div>
                    )}
                    {!twinsLoading && !twinsError && twins.length === 0 && (
                      <div className="border border-foreground/10 rounded-lg p-4">
                        <p className="text-sm text-muted-foreground mb-3">
                          No twins {selectedCompanyId ? `for ${selectedCompany?.name}` : "found"}. Create one to link.
                        </p>
                        <Button type="button" variant="outline" size="sm" onClick={handleCreateTwin} disabled={isCreatingTwin} className="gap-2 border-foreground/20 h-9 text-sm">
                          {isCreatingTwin ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                          Create Twin
                        </Button>
                      </div>
                    )}
                    {!twinsLoading && !twinsError && twins.length > 0 && (
                      <div className="space-y-2">
                        <div className="flex gap-2">
                          <Select
                            value={selectedTwinId?.toString() ?? ""}
                            onValueChange={(v) => setSelectedTwinId(Number(v))}
                            disabled={isSubmitting}
                          >
                            <SelectTrigger className="text-sm px-3 py-2 flex-1">
                              <div className="flex items-center gap-2">
                                <Cpu className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                                <SelectValue placeholder="Select a twin" />
                              </div>
                            </SelectTrigger>
                            <SelectContent>
                              {twins.map((t) => (
                                <SelectItem key={t.id} value={t.id.toString()}>
                                  <span className="flex items-center gap-2">
                                    <span>{t.name}</span>
                                    <span className="text-xs text-muted-foreground font-mono">#{t.id} · {t.simulation_count} sims</span>
                                  </span>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <Button type="button" variant="outline" size="sm" onClick={handleCreateTwin} disabled={isCreatingTwin || isSubmitting} className="border-foreground/20 h-10 w-10 p-0 shrink-0" title="Create new twin">
                            {isCreatingTwin ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                          </Button>
                          <Button type="button" variant="outline" size="sm" onClick={loadTwins} disabled={twinsLoading || isSubmitting} className="border-foreground/20 h-10 w-10 p-0 shrink-0" title="Refresh">
                            <RefreshCw className={`w-3.5 h-3.5 ${twinsLoading ? "animate-spin" : ""}`} />
                          </Button>
                        </div>
                        {selectedTwin && (
                          <div className="flex items-center gap-2 text-xs text-emerald-500">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Simulation will update <strong>{selectedTwin.name}</strong> and generate intelligence.</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Payload preview — only when something is linked */}
              {(selectedProductId != null || selectedTwinId != null || selectedSupplierId != null || selectedWarehouseDbId != null) && (
                <div className="border border-foreground/5 rounded-lg p-4 bg-foreground/2">
                  <div className="text-xs font-mono text-muted-foreground mb-2">PAYLOAD PREVIEW</div>
                  <div className="text-xs font-mono space-y-0.5 text-foreground/60">
                    <div><span className="text-foreground/40">product:</span> {watch("product") || "…"}</div>
                    <div><span className="text-foreground/40">stock:</span> {watch("stock") ?? "…"}</div>
                    <div><span className="text-foreground/40">demand:</span> {watch("demand") ?? "…"}</div>
                    <div><span className="text-foreground/40">supplier_delay:</span> {watch("supplier_delay") ?? "…"} days</div>
                    <div><span className="text-foreground/40">supply_status:</span> {watch("supply_status") || "…"}</div>
                    <div><span className="text-foreground/40">warehouse:</span> {watch("warehouse") || "…"}</div>
                    {selectedCompanyId != null && (
                      <div className="text-blue-400/70">
                        <span className="text-foreground/40">company_id:</span> {selectedCompanyId}
                        {selectedCompany && <span className="ml-1 text-foreground/30">({selectedCompany.name})</span>}
                      </div>
                    )}
                    {selectedProductId != null && (
                      <div className="text-emerald-400/80">
                        <span className="text-foreground/40">product_id:</span> {selectedProductId}
                        {selectedProduct && <span className="ml-1 text-foreground/30">({selectedProduct.name})</span>}
                        <span className="ml-2 text-emerald-500/60">← stock &amp; demand</span>
                      </div>
                    )}
                    {selectedSupplierId != null && (
                      <div className="text-emerald-400/80">
                        <span className="text-foreground/40">supplier_id:</span> {selectedSupplierId}
                        {selectedSupplier && <span className="ml-1 text-foreground/30">({selectedSupplier.name})</span>}
                        <span className="ml-2 text-emerald-500/60">← delay &amp; status</span>
                      </div>
                    )}
                    {selectedWarehouseDbId != null && (
                      <div className="text-emerald-400/80">
                        <span className="text-foreground/40">warehouse_record_id:</span> {selectedWarehouseDbId}
                        {selectedWarehouse && <span className="ml-1 text-foreground/30">({selectedWarehouse.name} → {selectedWarehouse.warehouse_id})</span>}
                        <span className="ml-2 text-emerald-500/60">← warehouse slot</span>
                      </div>
                    )}
                    {twinEnabled && selectedTwinId != null && (
                      <div className="text-emerald-500">
                        <span className="text-foreground/40">twin_id:</span> {selectedTwinId}
                        <span className="ml-2 text-emerald-500/60">← intelligence pipeline</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Submit / Reset */}
              <div className="flex flex-col sm:flex-row gap-4 pt-4">
                <Button
                  type="submit"
                  size="lg"
                  disabled={isSubmitting}
                  className="bg-foreground hover:bg-foreground/90 text-background px-8 h-14 text-base rounded-full group flex-1"
                >
                  {isSubmitting ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Running Simulation…</>
                  ) : (
                    <>Run Simulation<ArrowRight className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-1" /></>
                  )}
                </Button>
                <Button
                  type="button"
                  onClick={handleReset}
                  size="lg"
                  variant="outline"
                  disabled={isSubmitting}
                  className="h-14 px-8 text-base rounded-full border-foreground/20 hover:bg-foreground/5 flex-1"
                >
                  Reset
                </Button>
              </div>
            </form>
          </div>
        </div>
      </section>
    </main>
  );
}
