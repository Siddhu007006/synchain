"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
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
  ArrowLeft,
  Building2,
  Globe,
  Factory,
  AlertCircle,
  RefreshCw,
  Pencil,
  Trash2,
  Check,
  X,
  Loader2,
  Calendar,
  ArrowRight,
  Cpu,
  Plus,
  Activity,
  Zap,
  BarChart3,
  Package,
  TrendingUp,
  Truck,
  Warehouse,
  Upload,
  FileText,
  CheckCircle2,
  History,
} from "lucide-react";
import {
  getCompany,
  updateCompany,
  archiveCompany,
  listCompanyTwins,
  createCompanyTwin,
  listCompanyProducts,
  createProduct,
  deleteProduct,
  listCompanySuppliers,
  createSupplier,
  deleteSupplier,
  listCompanyWarehouses,
  createWarehouse,
  deleteWarehouse,
  listImportJobs,
} from "@/lib/api";
import type { Company, CompanyTwinSummary, Product, Supplier, CompanyWarehouse, ImportJob, ImportEntityType } from "@/lib/types";
import { ImportModal } from "@/components/company/import-modal";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatDate(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
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

// ---------------------------------------------------------------------------
// Inline edit field
// ---------------------------------------------------------------------------
const EditField = ({
  label,
  value,
  placeholder,
  editing,
  draft,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  editing: boolean;
  draft: string;
  onChange: (v: string) => void;
}) => (
  <div className="border border-foreground/10 rounded-lg p-5">
    <div className="text-xs font-mono text-muted-foreground mb-2">{label}</div>
    {editing ? (
      <Input
        value={draft}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="text-base"
        autoFocus={label === "COMPANY NAME"}
      />
    ) : (
      <div className="text-xl font-display">
        {value || (
          <span className="text-muted-foreground/40 text-sm font-sans">Not set</span>
        )}
      </div>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// Twin card — shows real intelligence data
// ---------------------------------------------------------------------------
const TwinCard = ({
  twin,
  companyId,
}: {
  twin: CompanyTwinSummary;
  companyId: number;
}) => {
  const health = Math.round(twin.health_score * 100);
  return (
    <div className="border border-foreground/10 rounded-lg p-5 hover:border-foreground/20 transition-colors group">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-foreground/5 flex items-center justify-center shrink-0">
            <Cpu className="w-4 h-4 text-muted-foreground" />
          </div>
          <div>
            <div className="font-display text-base">{twin.name}</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              Updated {formatRelative(twin.updated_at)}
            </div>
          </div>
        </div>
        <Link
          href={`/intelligence/twins`}
          className="opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <Button
            variant="outline"
            size="sm"
            className="border-foreground/20 gap-1.5 h-8 text-xs"
          >
            View
            <ArrowRight className="w-3 h-3" />
          </Button>
        </Link>
      </div>

      {/* Intelligence metrics */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="text-center">
          <div className="text-xs font-mono text-muted-foreground mb-0.5">SIMS</div>
          <div className="text-xl font-display">{twin.simulation_count}</div>
        </div>
        <div className="text-center">
          <div className="text-xs font-mono text-muted-foreground mb-0.5">SIGNALS</div>
          <div className="text-xl font-display flex items-center justify-center gap-1">
            {twin.signal_count > 0 && (
              <Zap className="w-3.5 h-3.5 text-amber-500" />
            )}
            {twin.signal_count}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs font-mono text-muted-foreground mb-0.5">HEALTH</div>
          <div className={`text-xl font-display ${healthColor(twin.health_score)}`}>
            {health}%
          </div>
        </div>
      </div>

      {/* Health bar */}
      <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${healthBg(twin.health_score)}`}
          style={{ width: `${health}%` }}
        />
      </div>

      {/* Quick action links */}
      <div className="flex gap-2 mt-4 pt-3 border-t border-foreground/5">
        <Link href={`/intelligence/forecasts`} className="flex-1">
          <Button
            variant="outline"
            size="sm"
            className="w-full border-foreground/10 gap-1.5 h-7 text-xs text-muted-foreground hover:text-foreground"
          >
            <BarChart3 className="w-3 h-3" />
            Forecasts
          </Button>
        </Link>
        <Link href={`/intelligence/signals`} className="flex-1">
          <Button
            variant="outline"
            size="sm"
            className="w-full border-foreground/10 gap-1.5 h-7 text-xs text-muted-foreground hover:text-foreground"
          >
            <Activity className="w-3 h-3" />
            Signals
          </Button>
        </Link>
        <Link href={`/form`} className="flex-1">
          <Button
            variant="outline"
            size="sm"
            className="w-full border-foreground/10 gap-1.5 h-7 text-xs text-muted-foreground hover:text-foreground"
          >
            <Zap className="w-3 h-3" />
            Simulate
          </Button>
        </Link>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const companyId = Number(params.id);

  const [company, setCompany] = useState<Company | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Twin state
  const [twins, setTwins] = useState<CompanyTwinSummary[]>([]);
  const [twinsLoading, setTwinsLoading] = useState(false);
  const [newTwinName, setNewTwinName] = useState("");
  const [showTwinForm, setShowTwinForm] = useState(false);
  const [creatingTwin, setCreatingTwin] = useState(false);

  // Product state
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [showProductForm, setShowProductForm] = useState(false);
  const [editingProductId, setEditingProductId] = useState<number | null>(null);
  const [newProductName, setNewProductName] = useState("");
  const [newProductCategory, setNewProductCategory] = useState("");
  const [newProductStock, setNewProductStock] = useState("");
  const [newProductDemand, setNewProductDemand] = useState("");
  const [savingProduct, setSavingProduct] = useState(false);

  // Supplier state
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [suppliersLoading, setSuppliersLoading] = useState(false);
  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [newSupplierName, setNewSupplierName] = useState("");
  const [newSupplierDelay, setNewSupplierDelay] = useState("");
  const [newSupplierStatus, setNewSupplierStatus] = useState<"High" | "Medium" | "Low">("Medium");
  const [newSupplierReliability, setNewSupplierReliability] = useState("");
  const [savingSupplier, setSavingSupplier] = useState(false);

  // Warehouse state
  const [warehouses, setWarehouses] = useState<CompanyWarehouse[]>([]);
  const [warehousesLoading, setWarehousesLoading] = useState(false);
  const [showWarehouseForm, setShowWarehouseForm] = useState(false);
  const [newWarehouseName, setNewWarehouseName] = useState("");
  const [newWarehouseId, setNewWarehouseId] = useState<"W1" | "W2" | "W3">("W1");
  const [newWarehouseLocation, setNewWarehouseLocation] = useState("");
  const [newWarehouseCapacity, setNewWarehouseCapacity] = useState("");
  const [savingWarehouse, setSavingWarehouse] = useState(false);

  // Edit state
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [draftIndustry, setDraftIndustry] = useState("");
  const [draftCountry, setDraftCountry] = useState("");
  const [saving, setSaving] = useState(false);

  // Delete state
  const [deleting, setDeleting] = useState(false);

  // V2.6: Import state
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importEntityType, setImportEntityType] = useState<ImportEntityType>("products");
  const [importHistory, setImportHistory] = useState<ImportJob[]>([]);
  const [importHistoryLoading, setImportHistoryLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCompany(companyId);
      setCompany(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load company");
    } finally {
      setLoading(false);
    }
  };

  const loadTwins = async () => {
    setTwinsLoading(true);
    try {
      const data = await listCompanyTwins(companyId);
      setTwins(data);
    } catch {
      // Non-blocking — twins section degrades gracefully
    } finally {
      setTwinsLoading(false);
    }
  };

  const loadProducts = async () => {
    setProductsLoading(true);
    try {
      const data = await listCompanyProducts(companyId);
      setProducts(data.products);
    } catch {
      // Non-blocking
    } finally {
      setProductsLoading(false);
    }
  };

  const loadSuppliers = async () => {
    setSuppliersLoading(true);
    try {
      const data = await listCompanySuppliers(companyId);
      setSuppliers(data.suppliers);
    } catch {
      // Non-blocking
    } finally {
      setSuppliersLoading(false);
    }
  };

  const loadWarehouses = async () => {
    setWarehousesLoading(true);
    try {
      const data = await listCompanyWarehouses(companyId);
      setWarehouses(data.warehouses);
    } catch {
      // Non-blocking
    } finally {
      setWarehousesLoading(false);
    }
  };

  const loadImportHistory = async () => {
    setImportHistoryLoading(true);
    try {
      const data = await listImportJobs(companyId);
      setImportHistory(data.imports);
    } catch {
      // Non-blocking
    } finally {
      setImportHistoryLoading(false);
    }
  };

  const openImportModal = (type: ImportEntityType) => {
    setImportEntityType(type);
    setImportModalOpen(true);
  };

  const handleImportComplete = () => {
    // Refresh entity lists + import history after successful import
    if (importEntityType === "products") loadProducts();
    if (importEntityType === "suppliers") loadSuppliers();
    if (importEntityType === "warehouses") loadWarehouses();
    loadImportHistory();
  };

  useEffect(() => {
    load();
    loadTwins();
    loadProducts();
    loadSuppliers();
    loadWarehouses();
    loadImportHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  const startEdit = () => {
    if (!company) return;
    setDraftName(company.name);
    setDraftIndustry(company.industry);
    setDraftCountry(company.country);
    setEditing(true);
  };

  const cancelEdit = () => setEditing(false);

  const saveEdit = async () => {
    if (!company || !draftName.trim()) {
      toast.error("Company name is required");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateCompany(companyId, {
        name: draftName.trim(),
        industry: draftIndustry.trim(),
        country: draftCountry.trim(),
      });
      setCompany(updated);
      setEditing(false);
      toast.success("Company updated");
    } catch (e) {
      toast.error("Update failed", {
        description: e instanceof Error ? e.message : "Unknown error",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!company) return;
    if (!window.confirm(`Archive "${company.name}"? All data will be preserved.`)) return;
    setDeleting(true);
    try {
      await archiveCompany(companyId);
      toast.success(`"${company.name}" archived`, {
        description: "No data was deleted. The company is now archived.",
      });
      router.push("/companies");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      // Try to parse a 409 conflict response — apiFetch serializes detail objects as JSON
      let detail: Record<string, unknown> | null = null;
      try {
        const jsonStart = msg.indexOf("{");
        if (jsonStart !== -1) detail = JSON.parse(msg.slice(jsonStart));
      } catch { /* not parseable */ }

      if (detail && (detail as Record<string, unknown>).error === "company_has_data") {
        const counts = (detail as Record<string, unknown>).counts as Record<string, number> | undefined;
        const parts: string[] = [];
        if (counts?.twins)       parts.push(`${counts.twins} twin${counts.twins !== 1 ? "s" : ""}`);
        if (counts?.simulations) parts.push(`${counts.simulations} simulation${counts.simulations !== 1 ? "s" : ""}`);
        if (counts?.products)    parts.push(`${counts.products} product${counts.products !== 1 ? "s" : ""}`);
        if (counts?.suppliers)   parts.push(`${counts.suppliers} supplier${counts.suppliers !== 1 ? "s" : ""}`);
        if (counts?.warehouses)  parts.push(`${counts.warehouses} warehouse${counts.warehouses !== 1 ? "s" : ""}`);
        const summary = parts.join(", ");

        // Offer archive as the recommended action
        const confirmArchive = window.confirm(
          `"${company.name}" contains ${summary}.\n\nArchive it instead? All data will be preserved and can be restored later.`
        );
        if (confirmArchive) {
          try {
            await archiveCompany(companyId);
            toast.success(`"${company.name}" archived`, {
              description: `${summary} preserved. Restore anytime from the companies list.`,
            });
            router.push("/companies");
          } catch (archiveErr) {
            toast.error("Archive failed", {
              description: archiveErr instanceof Error ? archiveErr.message : "Unknown error",
            });
          }
        }
      } else {
        toast.error("Operation failed", { description: msg });
      }
      setDeleting(false);
    }
  };

  const handleCreateTwin = async () => {
    const name = newTwinName.trim() || `${company?.name ?? "Company"} Twin`;
    setCreatingTwin(true);
    try {
      const twin = await createCompanyTwin(companyId, name);
      setTwins((prev) => [twin, ...prev]);
      setNewTwinName("");
      setShowTwinForm(false);
      toast.success("Digital Twin created", {
        description: `"${twin.name}" is linked to ${company?.name}.`,
      });
    } catch (e) {
      toast.error("Failed to create twin", {
        description: e instanceof Error ? e.message : "Unknown error",
      });
    } finally {
      setCreatingTwin(false);
    }
  };

  const resetProductForm = () => {
    setNewProductName("");
    setNewProductCategory("");
    setNewProductStock("");
    setNewProductDemand("");
    setShowProductForm(false);
    setEditingProductId(null);
  };

  const handleCreateProduct = async () => {
    if (!newProductName.trim()) {
      toast.error("Product name is required");
      return;
    }
    setSavingProduct(true);
    try {
      const product = await createProduct(companyId, {
        name: newProductName.trim(),
        category: newProductCategory.trim(),
        current_stock: parseFloat(newProductStock) || 0,
        avg_monthly_demand: parseFloat(newProductDemand) || 0,
      });
      setProducts((prev) => [...prev, product].sort((a, b) => a.name.localeCompare(b.name)));
      resetProductForm();
      toast.success("Product added", { description: `"${product.name}" added to ${company?.name}.` });
    } catch (e) {
      toast.error("Failed to create product", {
        description: e instanceof Error ? e.message : "Unknown error",
      });
    } finally {
      setSavingProduct(false);
    }
  };

  const handleDeleteProduct = async (productId: number, productName: string) => {
    if (!window.confirm(`Delete "${productName}"?`)) return;
    try {
      await deleteProduct(companyId, productId);
      setProducts((prev) => prev.filter((p) => p.id !== productId));
      toast.success("Product deleted");
    } catch (e) {
      toast.error("Delete failed", {
        description: e instanceof Error ? e.message : "Unknown error",
      });
    }
  };

  const resetSupplierForm = () => {
    setNewSupplierName(""); setNewSupplierDelay(""); setNewSupplierStatus("Medium");
    setNewSupplierReliability(""); setShowSupplierForm(false);
  };

  const handleCreateSupplier = async () => {
    if (!newSupplierName.trim()) { toast.error("Supplier name is required"); return; }
    setSavingSupplier(true);
    try {
      const s = await createSupplier(companyId, {
        name: newSupplierName.trim(),
        lead_time_days: parseFloat(newSupplierDelay) || 0,
        supply_status: newSupplierStatus,
        reliability_pct: parseFloat(newSupplierReliability) || 100,
      });
      setSuppliers((prev) => [...prev, s].sort((a, b) => a.name.localeCompare(b.name)));
      resetSupplierForm();
      toast.success("Supplier added");
    } catch (e) {
      toast.error("Failed to create supplier", { description: e instanceof Error ? e.message : "Unknown error" });
    } finally { setSavingSupplier(false); }
  };

  const handleDeleteSupplier = async (id: number, name: string) => {
    if (!window.confirm(`Delete "${name}"?`)) return;
    try {
      await deleteSupplier(companyId, id);
      setSuppliers((prev) => prev.filter((s) => s.id !== id));
      toast.success("Supplier deleted");
    } catch (e) { toast.error("Delete failed", { description: e instanceof Error ? e.message : "Unknown error" }); }
  };

  const resetWarehouseForm = () => {
    setNewWarehouseName(""); setNewWarehouseId("W1");
    setNewWarehouseLocation(""); setNewWarehouseCapacity(""); setShowWarehouseForm(false);
  };

  const handleCreateWarehouse = async () => {
    if (!newWarehouseName.trim()) { toast.error("Warehouse name is required"); return; }
    setSavingWarehouse(true);
    try {
      const w = await createWarehouse(companyId, {
        name: newWarehouseName.trim(),
        warehouse_id: newWarehouseId,
        location: newWarehouseLocation.trim(),
        capacity: parseFloat(newWarehouseCapacity) || 10000,
      });
      setWarehouses((prev) => [...prev, w].sort((a, b) => a.name.localeCompare(b.name)));
      resetWarehouseForm();
      toast.success("Warehouse added");
    } catch (e) {
      toast.error("Failed to create warehouse", { description: e instanceof Error ? e.message : "Unknown error" });
    } finally { setSavingWarehouse(false); }
  };

  const handleDeleteWarehouse = async (id: number, name: string) => {
    if (!window.confirm(`Delete "${name}"?`)) return;
    try {
      await deleteWarehouse(companyId, id);
      setWarehouses((prev) => prev.filter((w) => w.id !== id));
      toast.success("Warehouse deleted");
    } catch (e) { toast.error("Delete failed", { description: e instanceof Error ? e.message : "Unknown error" }); }
  };

  // ---------------------------------------------------------------------------
  // Loading / error states
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <main className="relative min-h-screen overflow-x-hidden noise-overlay">
        <Navigation />
        <section className="relative py-32">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
            <div className="animate-pulse space-y-6 max-w-3xl">
              <div className="h-8 w-48 bg-muted rounded" />
              <div className="h-12 w-80 bg-muted rounded" />
              <div className="grid grid-cols-3 gap-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="border border-foreground/10 rounded-lg h-24" />
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>
    );
  }

  if (error || !company) {
    return (
      <main className="relative min-h-screen overflow-x-hidden noise-overlay">
        <Navigation />
        <section className="relative py-32">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-12 flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-6">
              <AlertCircle className="w-8 h-8 text-destructive" />
            </div>
            <p className="text-muted-foreground mb-6 max-w-sm">{error ?? "Company not found"}</p>
            <div className="flex gap-3">
              <Button onClick={load} variant="outline" className="gap-2">
                <RefreshCw className="w-4 h-4" /> Retry
              </Button>
              <Link href="/companies">
                <Button variant="outline">← Back to Companies</Button>
              </Link>
            </div>
          </div>
        </section>
      </main>
    );
  }

  // Total signals across all twins
  const totalSignals = twins.reduce((sum, t) => sum + t.signal_count, 0);
  const totalSims = twins.reduce((sum, t) => sum + t.simulation_count, 0);
  const avgHealth =
    twins.length > 0
      ? Math.round(
          (twins.reduce((sum, t) => sum + t.health_score, 0) / twins.length) * 100
        )
      : null;

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <section className="relative py-32">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
          <div className="max-w-3xl">

            {/* Breadcrumb */}
            <Link href="/companies">
              <Button variant="outline" className="mb-6 border-foreground/20 hover:bg-foreground/5">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Companies
              </Button>
            </Link>

            {/* Header */}
            <div className="flex items-start justify-between gap-6 mb-10">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-xl bg-foreground/5 flex items-center justify-center shrink-0">
                  <Building2 className="w-7 h-7 text-muted-foreground" />
                </div>
                <div>
                  <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-1">
                    <span className="w-8 h-px bg-foreground/30" />
                    Company #{company.id}
                  </span>
                  <h1 className="text-3xl lg:text-4xl font-display tracking-tight">
                    {company.name}
                  </h1>
                  <div className="flex flex-wrap gap-3 mt-1 text-sm text-muted-foreground">
                    {company.industry && (
                      <span className="flex items-center gap-1">
                        <Factory className="w-3.5 h-3.5" />
                        {company.industry}
                      </span>
                    )}
                    {company.country && (
                      <span className="flex items-center gap-1">
                        <Globe className="w-3.5 h-3.5" />
                        {company.country}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {!editing && (
                <div className="flex items-center gap-2 shrink-0">
                  <Link href={`/companies/${companyId}/dashboard`}>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-foreground/20 gap-2"
                    >
                      <BarChart3 className="w-3.5 h-3.5" />
                      Dashboard
                    </Button>
                  </Link>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={startEdit}
                    className="border-foreground/20 gap-2"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDelete}
                    disabled={deleting}
                    className="border-red-500/20 text-red-500 hover:bg-red-500/5 gap-2"
                  >
                    {deleting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
                    Delete
                  </Button>
                </div>
              )}
            </div>

            {/* Intelligence summary strip — only shows when twins or products exist */}
            {(twins.length > 0 || products.length > 0 || suppliers.length > 0 || warehouses.length > 0) && (
              <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-8">
                {[
                  { label: "PRODUCTS",    value: products.length },
                  { label: "SUPPLIERS",   value: suppliers.length },
                  { label: "WAREHOUSES",  value: warehouses.length },
                  { label: "TWINS",       value: twins.length },
                  { label: "SIMULATIONS", value: totalSims },
                  { label: "SIGNALS",     value: totalSignals, highlight: totalSignals > 0 },
                ].map(({ label, value, highlight }) => (
                  <div key={label} className={`border rounded-lg p-3 text-center ${highlight ? "border-amber-500/25 bg-amber-500/5" : "border-foreground/10"}`}>
                    <div className="text-xs font-mono text-muted-foreground mb-1">{label}</div>
                    <div className={`text-xl font-display ${highlight ? "text-amber-500" : ""}`}>{value}</div>
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-6">

              {/* Company details card */}
              <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
                <div className="flex items-center justify-between mb-6">
                  <div className="text-sm font-mono text-muted-foreground">COMPANY DETAILS</div>
                  {editing && (
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={saveEdit}
                        disabled={saving || !draftName.trim()}
                        className="bg-foreground hover:bg-foreground/90 text-background gap-2 h-8"
                      >
                        {saving ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Check className="w-3.5 h-3.5" />
                        )}
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={cancelEdit}
                        disabled={saving}
                        className="border-foreground/20 gap-2 h-8"
                      >
                        <X className="w-3.5 h-3.5" />
                        Cancel
                      </Button>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <EditField
                    label="COMPANY NAME"
                    value={company.name}
                    placeholder="Company name"
                    editing={editing}
                    draft={draftName}
                    onChange={setDraftName}
                  />
                  <EditField
                    label="INDUSTRY"
                    value={company.industry}
                    placeholder="e.g., Consumer Electronics"
                    editing={editing}
                    draft={draftIndustry}
                    onChange={setDraftIndustry}
                  />
                  <EditField
                    label="COUNTRY"
                    value={company.country}
                    placeholder="e.g., India"
                    editing={editing}
                    draft={draftCountry}
                    onChange={setDraftCountry}
                  />
                </div>
              </div>

              {/* ================================================================
                  V2.6: IMPORT DATA SECTION
               ================================================================ */}
              <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Upload className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm font-mono text-muted-foreground">IMPORT DATA</div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        Bulk onboard entities from CSV files
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
                  {([
                    { type: "products" as ImportEntityType, icon: Package, label: "Import Products", desc: "name, category, stock, demand" },
                    { type: "suppliers" as ImportEntityType, icon: Truck, label: "Import Suppliers", desc: "name, lead_time, reliability, status" },
                    { type: "warehouses" as ImportEntityType, icon: Warehouse, label: "Import Warehouses", desc: "name, location, capacity, warehouse_id" },
                  ]).map(({ type, icon: Icon, label, desc }) => (
                    <button
                      key={type}
                      onClick={() => openImportModal(type)}
                      className="border border-foreground/10 rounded-lg p-4 text-left hover:border-foreground/25 hover:bg-foreground/[0.02] transition-colors group"
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <div className="w-8 h-8 rounded-lg bg-foreground/5 flex items-center justify-center group-hover:bg-foreground/10 transition-colors">
                          <Icon className="w-4 h-4 text-muted-foreground" />
                        </div>
                        <div className="font-medium text-sm">{label}</div>
                      </div>
                      <div className="text-xs text-muted-foreground font-mono">{desc}</div>
                    </button>
                  ))}
                </div>

                {/* Import History */}
                {importHistory.length > 0 && (
                  <div className="border-t border-foreground/5 pt-4">
                    <div className="flex items-center gap-2 mb-3">
                      <History className="w-3.5 h-3.5 text-muted-foreground" />
                      <div className="text-xs font-mono text-muted-foreground">IMPORT HISTORY</div>
                    </div>
                    <div className="space-y-2">
                      {importHistory.slice(0, 5).map((job) => (
                        <div
                          key={job.id}
                          className="flex items-center justify-between text-sm border border-foreground/5 rounded-lg px-3 py-2"
                        >
                          <div className="flex items-center gap-3">
                            <div className={`w-6 h-6 rounded flex items-center justify-center text-xs font-mono ${
                              job.rows_failed === 0
                                ? "bg-emerald-500/10 text-emerald-500"
                                : "bg-amber-500/10 text-amber-500"
                            }`}>
                              {job.rows_failed === 0 ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                            </div>
                            <div>
                              <div className="font-medium capitalize">{job.entity_type}</div>
                              <div className="text-xs text-muted-foreground">
                                {job.file_name}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs">
                              <span className="text-emerald-500">{job.rows_success} ok</span>
                              {job.rows_failed > 0 && (
                                <span className="text-red-500 ml-2">{job.rows_failed} failed</span>
                              )}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {job.created_at ? new Date(job.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Import Modal */}
              <ImportModal
                open={importModalOpen}
                onOpenChange={setImportModalOpen}
                companyId={companyId}
                companyName={company.name}
                entityType={importEntityType}
                onComplete={handleImportComplete}
              />

              {/* ================================================================
                  DIGITAL TWINS SECTION — real data, company-scoped
               ================================================================ */}
              <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Cpu className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm font-mono text-muted-foreground">DIGITAL TWINS</div>
                      {twins.length > 0 && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {twins.length} twin{twins.length !== 1 ? "s" : ""} · intelligence pipeline active
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={loadTwins}
                      disabled={twinsLoading}
                      className="border-foreground/20 h-8 w-8 p-0"
                      title="Refresh"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${twinsLoading ? "animate-spin" : ""}`} />
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => setShowTwinForm((v) => !v)}
                      className="bg-foreground hover:bg-foreground/90 text-background gap-2 h-8"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Create Twin
                    </Button>
                  </div>
                </div>

                {/* Inline create-twin form */}
                {showTwinForm && (
                  <div className="border border-foreground/10 rounded-lg p-4 mb-5 bg-foreground/2">
                    <Label className="text-xs font-mono text-muted-foreground mb-2 block">
                      TWIN NAME
                    </Label>
                    <div className="flex gap-2">
                      <Input
                        value={newTwinName}
                        onChange={(e) => setNewTwinName(e.target.value)}
                        placeholder={`${company.name} Twin`}
                        className="text-sm flex-1"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleCreateTwin();
                          if (e.key === "Escape") setShowTwinForm(false);
                        }}
                        autoFocus
                        disabled={creatingTwin}
                      />
                      <Button
                        onClick={handleCreateTwin}
                        disabled={creatingTwin}
                        size="sm"
                        className="bg-foreground hover:bg-foreground/90 text-background gap-2 shrink-0"
                      >
                        {creatingTwin ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Check className="w-3.5 h-3.5" />
                        )}
                        Create
                      </Button>
                      <Button
                        onClick={() => setShowTwinForm(false)}
                        disabled={creatingTwin}
                        size="sm"
                        variant="outline"
                        className="border-foreground/20 shrink-0"
                      >
                        <X className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      The twin will be linked to {company.name} and will accumulate
                      state from simulations run with its ID.
                    </p>
                  </div>
                )}

                {/* Loading */}
                {twinsLoading && (
                  <div className="animate-pulse space-y-3">
                    {[...Array(2)].map((_, i) => (
                      <div key={i} className="border border-foreground/10 rounded-lg h-40" />
                    ))}
                  </div>
                )}

                {/* Empty state */}
                {!twinsLoading && twins.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-10 text-center border border-dashed border-foreground/10 rounded-lg">
                    <Cpu className="w-8 h-8 text-muted-foreground mb-3 opacity-50" />
                    <p className="text-sm text-muted-foreground mb-1">
                      No Digital Twins yet
                    </p>
                    <p className="text-xs text-muted-foreground/60 max-w-xs">
                      Create a twin to start accumulating supply chain state, generating
                      signals, and producing forecasts under this company.
                    </p>
                  </div>
                )}

                {/* Twin cards */}
                {!twinsLoading && twins.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {twins.map((twin) => (
                      <TwinCard key={twin.id} twin={twin} companyId={companyId} />
                    ))}
                  </div>
                )}
              </div>

              {/* ================================================================
                  PRODUCTS SECTION — V2.3 business data
               ================================================================ */}
              <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Package className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm font-mono text-muted-foreground">PRODUCTS</div>
                      {products.length > 0 && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {products.length} product{products.length !== 1 ? "s" : ""} ·
                          stock and demand ready for simulation prefill
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={loadProducts}
                      disabled={productsLoading}
                      className="border-foreground/20 h-8 w-8 p-0"
                      title="Refresh"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${productsLoading ? "animate-spin" : ""}`} />
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => { setShowProductForm((v) => !v); setEditingProductId(null); }}
                      className="bg-foreground hover:bg-foreground/90 text-background gap-2 h-8"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add Product
                    </Button>
                  </div>
                </div>

                {/* Inline create-product form */}
                {showProductForm && (
                  <div className="border border-foreground/10 rounded-lg p-4 mb-5 bg-foreground/2 space-y-3">
                    <div className="text-xs font-mono text-muted-foreground">NEW PRODUCT</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">NAME *</Label>
                        <Input
                          value={newProductName}
                          onChange={(e) => setNewProductName(e.target.value)}
                          placeholder="e.g., Laptop"
                          className="text-sm"
                          autoFocus
                          disabled={savingProduct}
                          onKeyDown={(e) => e.key === "Escape" && resetProductForm()}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">CATEGORY</Label>
                        <Input
                          value={newProductCategory}
                          onChange={(e) => setNewProductCategory(e.target.value)}
                          placeholder="e.g., Electronics"
                          className="text-sm"
                          disabled={savingProduct}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                          CURRENT STOCK
                          <span className="text-foreground/30 font-normal">→ prefills simulation</span>
                        </Label>
                        <Input
                          type="number"
                          value={newProductStock}
                          onChange={(e) => setNewProductStock(e.target.value)}
                          placeholder="e.g., 500"
                          className="text-sm"
                          min={0}
                          disabled={savingProduct}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                          AVG MONTHLY DEMAND
                          <span className="text-foreground/30 font-normal">→ prefills simulation</span>
                        </Label>
                        <Input
                          type="number"
                          value={newProductDemand}
                          onChange={(e) => setNewProductDemand(e.target.value)}
                          placeholder="e.g., 700"
                          className="text-sm"
                          min={0}
                          disabled={savingProduct}
                        />
                      </div>
                    </div>
                    <div className="flex gap-2 pt-1">
                      <Button
                        onClick={handleCreateProduct}
                        disabled={savingProduct || !newProductName.trim()}
                        size="sm"
                        className="bg-foreground hover:bg-foreground/90 text-background gap-2"
                      >
                        {savingProduct ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Check className="w-3.5 h-3.5" />
                        )}
                        Save Product
                      </Button>
                      <Button
                        onClick={resetProductForm}
                        disabled={savingProduct}
                        size="sm"
                        variant="outline"
                        className="border-foreground/20"
                      >
                        <X className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>
                )}

                {/* Loading */}
                {productsLoading && (
                  <div className="animate-pulse space-y-2">
                    {[...Array(3)].map((_, i) => (
                      <div key={i} className="border border-foreground/10 rounded-lg h-14" />
                    ))}
                  </div>
                )}

                {/* Empty state */}
                {!productsLoading && products.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-10 text-center border border-dashed border-foreground/10 rounded-lg">
                    <Package className="w-8 h-8 text-muted-foreground mb-3 opacity-50" />
                    <p className="text-sm text-muted-foreground mb-1">No products yet</p>
                    <p className="text-xs text-muted-foreground/60 max-w-xs">
                      Add products with stock and demand figures. In V2.4 the simulation
                      form will auto-populate from these values when you select a product.
                    </p>
                  </div>
                )}

                {/* Product rows */}
                {!productsLoading && products.length > 0 && (
                  <div className="space-y-2">
                    {/* Header */}
                    <div className="grid grid-cols-12 gap-3 px-3 py-2 text-xs font-mono text-muted-foreground border-b border-foreground/5">
                      <div className="col-span-4">PRODUCT</div>
                      <div className="col-span-2">CATEGORY</div>
                      <div className="col-span-2 text-right">STOCK</div>
                      <div className="col-span-3 text-right">AVG DEMAND/MO</div>
                      <div className="col-span-1" />
                    </div>

                    {products.map((product) => (
                      <div
                        key={product.id}
                        className="grid grid-cols-12 gap-3 px-3 py-3 rounded-lg border border-foreground/5 hover:border-foreground/10 transition-colors items-center group"
                      >
                        <div className="col-span-4 flex items-center gap-2">
                          <Package className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="font-display text-sm truncate">{product.name}</span>
                        </div>
                        <div className="col-span-2">
                          {product.category ? (
                            <span className="text-xs font-mono text-muted-foreground px-1.5 py-0.5 rounded bg-foreground/5">
                              {product.category}
                            </span>
                          ) : (
                            <span className="text-xs text-foreground/20">—</span>
                          )}
                        </div>
                        <div className="col-span-2 text-right">
                          <span className="font-display text-sm">
                            {product.current_stock.toLocaleString()}
                          </span>
                          <span className="text-xs text-muted-foreground ml-1">units</span>
                        </div>
                        <div className="col-span-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <TrendingUp className="w-3 h-3 text-muted-foreground" />
                            <span className="font-display text-sm">
                              {product.avg_monthly_demand.toLocaleString()}
                            </span>
                            <span className="text-xs text-muted-foreground">/mo</span>
                          </div>
                        </div>
                        <div className="col-span-1 flex justify-end">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDeleteProduct(product.id, product.name)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity border-red-500/20 text-red-500 hover:bg-red-500/5 h-7 w-7 p-0"
                            title="Delete product"
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>
                    ))}

                    {/* V2.4 callout */}
                    <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground/60 px-1">
                      <Zap className="w-3 h-3" />
                      V2.4: Select a product in the simulation form to auto-fill stock and demand from these values.
                    </div>
                  </div>
                )}
              </div>

              {/* ================================================================
                  SUPPLIERS SECTION — V2.5
               ================================================================ */}
              <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Truck className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm font-mono text-muted-foreground">SUPPLIERS</div>
                      {suppliers.length > 0 && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {suppliers.length} supplier{suppliers.length !== 1 ? "s" : ""} · lead time &amp; status auto-fill simulation
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={loadSuppliers} disabled={suppliersLoading} className="border-foreground/20 h-8 w-8 p-0">
                      <RefreshCw className={`w-3.5 h-3.5 ${suppliersLoading ? "animate-spin" : ""}`} />
                    </Button>
                    <Button size="sm" onClick={() => setShowSupplierForm((v) => !v)} className="bg-foreground hover:bg-foreground/90 text-background gap-2 h-8">
                      <Plus className="w-3.5 h-3.5" />Add Supplier
                    </Button>
                  </div>
                </div>

                {showSupplierForm && (
                  <div className="border border-foreground/10 rounded-lg p-4 mb-5 bg-foreground/2 space-y-3">
                    <div className="text-xs font-mono text-muted-foreground">NEW SUPPLIER</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">NAME *</Label>
                        <Input value={newSupplierName} onChange={(e) => setNewSupplierName(e.target.value)} placeholder="e.g., Supplier A" className="text-sm" autoFocus disabled={savingSupplier} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                          LEAD TIME (days) <span className="text-foreground/30 font-normal">→ supplier_delay</span>
                        </Label>
                        <Input type="number" step="0.5" value={newSupplierDelay} onChange={(e) => setNewSupplierDelay(e.target.value)} placeholder="e.g., 8" className="text-sm" min={0} disabled={savingSupplier} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                          SUPPLY STATUS <span className="text-foreground/30 font-normal">→ supply_status</span>
                        </Label>
                        <Select value={newSupplierStatus} onValueChange={(v) => setNewSupplierStatus(v as "High" | "Medium" | "Low")} disabled={savingSupplier}>
                          <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="High">High</SelectItem>
                            <SelectItem value="Medium">Medium</SelectItem>
                            <SelectItem value="Low">Low</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">RELIABILITY (%)</Label>
                        <Input type="number" value={newSupplierReliability} onChange={(e) => setNewSupplierReliability(e.target.value)} placeholder="e.g., 85" className="text-sm" min={0} max={100} disabled={savingSupplier} />
                      </div>
                    </div>
                    <div className="flex gap-2 pt-1">
                      <Button onClick={handleCreateSupplier} disabled={savingSupplier || !newSupplierName.trim()} size="sm" className="bg-foreground hover:bg-foreground/90 text-background gap-2">
                        {savingSupplier ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                        Save Supplier
                      </Button>
                      <Button onClick={resetSupplierForm} disabled={savingSupplier} size="sm" variant="outline" className="border-foreground/20"><X className="w-3.5 h-3.5" /></Button>
                    </div>
                  </div>
                )}

                {suppliersLoading && (
                  <div className="animate-pulse space-y-2">{[...Array(2)].map((_, i) => <div key={i} className="border border-foreground/10 rounded-lg h-12" />)}</div>
                )}

                {!suppliersLoading && suppliers.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-8 text-center border border-dashed border-foreground/10 rounded-lg">
                    <Truck className="w-7 h-7 text-muted-foreground mb-2 opacity-50" />
                    <p className="text-sm text-muted-foreground">No suppliers yet</p>
                    <p className="text-xs text-muted-foreground/60 max-w-xs mt-1">Add suppliers with lead time and supply status. These auto-fill the simulation form.</p>
                  </div>
                )}

                {!suppliersLoading && suppliers.length > 0 && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-12 gap-3 px-3 py-2 text-xs font-mono text-muted-foreground border-b border-foreground/5">
                      <div className="col-span-4">SUPPLIER</div>
                      <div className="col-span-2 text-right">LEAD TIME</div>
                      <div className="col-span-3">STATUS</div>
                      <div className="col-span-2 text-right">RELIABILITY</div>
                      <div className="col-span-1" />
                    </div>
                    {suppliers.map((s) => (
                      <div key={s.id} className="grid grid-cols-12 gap-3 px-3 py-3 rounded-lg border border-foreground/5 hover:border-foreground/10 transition-colors items-center group">
                        <div className="col-span-4 flex items-center gap-2">
                          <Truck className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="font-display text-sm truncate">{s.name}</span>
                        </div>
                        <div className="col-span-2 text-right">
                          <span className="font-display text-sm">{s.lead_time_days}</span>
                          <span className="text-xs text-muted-foreground ml-1">days</span>
                        </div>
                        <div className="col-span-3">
                          <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                            s.supply_status === "Low" ? "bg-red-500/10 text-red-500" :
                            s.supply_status === "High" ? "bg-emerald-500/10 text-emerald-500" :
                            "bg-amber-500/10 text-amber-500"
                          }`}>{s.supply_status}</span>
                        </div>
                        <div className="col-span-2 text-right">
                          <span className={`font-display text-sm ${s.reliability_pct >= 80 ? "text-emerald-500" : s.reliability_pct >= 50 ? "text-amber-500" : "text-red-500"}`}>{s.reliability_pct}%</span>
                        </div>
                        <div className="col-span-1 flex justify-end">
                          <Button variant="outline" size="sm" onClick={() => handleDeleteSupplier(s.id, s.name)} className="opacity-0 group-hover:opacity-100 transition-opacity border-red-500/20 text-red-500 hover:bg-red-500/5 h-7 w-7 p-0"><Trash2 className="w-3 h-3" /></Button>
                        </div>
                      </div>
                    ))}
                    <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground/60 px-1">
                      <Zap className="w-3 h-3" />
                      V2.5: Select a supplier in the simulation form to auto-fill lead time and supply status.
                    </div>
                  </div>
                )}
              </div>

              {/* ================================================================
                  WAREHOUSES SECTION — V2.5
               ================================================================ */}
              <div className="border border-foreground/10 rounded-lg p-6 lg:p-8">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Warehouse className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm font-mono text-muted-foreground">WAREHOUSES</div>
                      {warehouses.length > 0 && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {warehouses.length} warehouse{warehouses.length !== 1 ? "s" : ""} · warehouse selection auto-fills simulation
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={loadWarehouses} disabled={warehousesLoading} className="border-foreground/20 h-8 w-8 p-0">
                      <RefreshCw className={`w-3.5 h-3.5 ${warehousesLoading ? "animate-spin" : ""}`} />
                    </Button>
                    <Button size="sm" onClick={() => setShowWarehouseForm((v) => !v)} className="bg-foreground hover:bg-foreground/90 text-background gap-2 h-8">
                      <Plus className="w-3.5 h-3.5" />Add Warehouse
                    </Button>
                  </div>
                </div>

                {showWarehouseForm && (
                  <div className="border border-foreground/10 rounded-lg p-4 mb-5 bg-foreground/2 space-y-3">
                    <div className="text-xs font-mono text-muted-foreground">NEW WAREHOUSE</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">NAME *</Label>
                        <Input value={newWarehouseName} onChange={(e) => setNewWarehouseName(e.target.value)} placeholder="e.g., Mumbai Hub" className="text-sm" autoFocus disabled={savingWarehouse} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                          WAREHOUSE SLOT <span className="text-foreground/30 font-normal">→ warehouse</span>
                        </Label>
                        <Select value={newWarehouseId} onValueChange={(v) => setNewWarehouseId(v as "W1" | "W2" | "W3")} disabled={savingWarehouse}>
                          <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="W1">W1 — Standard (10,000 cap)</SelectItem>
                            <SelectItem value="W2">W2 — Premium (15,000 cap)</SelectItem>
                            <SelectItem value="W3">W3 — Budget (8,000 cap)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">LOCATION</Label>
                        <Input value={newWarehouseLocation} onChange={(e) => setNewWarehouseLocation(e.target.value)} placeholder="e.g., Mumbai" className="text-sm" disabled={savingWarehouse} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">CAPACITY (units)</Label>
                        <Input type="number" value={newWarehouseCapacity} onChange={(e) => setNewWarehouseCapacity(e.target.value)} placeholder="e.g., 10000" className="text-sm" min={0} disabled={savingWarehouse} />
                      </div>
                    </div>
                    <div className="flex gap-2 pt-1">
                      <Button onClick={handleCreateWarehouse} disabled={savingWarehouse || !newWarehouseName.trim()} size="sm" className="bg-foreground hover:bg-foreground/90 text-background gap-2">
                        {savingWarehouse ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                        Save Warehouse
                      </Button>
                      <Button onClick={resetWarehouseForm} disabled={savingWarehouse} size="sm" variant="outline" className="border-foreground/20"><X className="w-3.5 h-3.5" /></Button>
                    </div>
                  </div>
                )}

                {warehousesLoading && (
                  <div className="animate-pulse space-y-2">{[...Array(2)].map((_, i) => <div key={i} className="border border-foreground/10 rounded-lg h-12" />)}</div>
                )}

                {!warehousesLoading && warehouses.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-8 text-center border border-dashed border-foreground/10 rounded-lg">
                    <Warehouse className="w-7 h-7 text-muted-foreground mb-2 opacity-50" />
                    <p className="text-sm text-muted-foreground">No warehouses yet</p>
                    <p className="text-xs text-muted-foreground/60 max-w-xs mt-1">Add warehouses mapped to W1/W2/W3 slots. The simulation form will show your warehouse names.</p>
                  </div>
                )}

                {!warehousesLoading && warehouses.length > 0 && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-12 gap-3 px-3 py-2 text-xs font-mono text-muted-foreground border-b border-foreground/5">
                      <div className="col-span-4">WAREHOUSE</div>
                      <div className="col-span-2">SLOT</div>
                      <div className="col-span-3">LOCATION</div>
                      <div className="col-span-2 text-right">CAPACITY</div>
                      <div className="col-span-1" />
                    </div>
                    {warehouses.map((w) => (
                      <div key={w.id} className="grid grid-cols-12 gap-3 px-3 py-3 rounded-lg border border-foreground/5 hover:border-foreground/10 transition-colors items-center group">
                        <div className="col-span-4 flex items-center gap-2">
                          <Warehouse className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="font-display text-sm truncate">{w.name}</span>
                        </div>
                        <div className="col-span-2">
                          <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-foreground/5 text-foreground">{w.warehouse_id}</span>
                        </div>
                        <div className="col-span-3 text-sm text-muted-foreground truncate">{w.location || "—"}</div>
                        <div className="col-span-2 text-right">
                          <span className="font-display text-sm">{w.capacity.toLocaleString()}</span>
                        </div>
                        <div className="col-span-1 flex justify-end">
                          <Button variant="outline" size="sm" onClick={() => handleDeleteWarehouse(w.id, w.name)} className="opacity-0 group-hover:opacity-100 transition-opacity border-red-500/20 text-red-500 hover:bg-red-500/5 h-7 w-7 p-0"><Trash2 className="w-3 h-3" /></Button>
                        </div>
                      </div>
                    ))}
                    <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground/60 px-1">
                      <Zap className="w-3 h-3" />
                      V2.5: Select a warehouse in the simulation form to auto-fill the warehouse slot.
                    </div>
                  </div>
                )}
              </div>

              {/* Timestamps */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="border border-foreground/10 rounded-lg p-5">
                  <div className="text-xs font-mono text-muted-foreground mb-1">CREATED</div>
                  <div className="flex items-center gap-2 text-sm">
                    <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
                    {formatDate(company.created_at)}
                  </div>
                </div>
                <div className="border border-foreground/10 rounded-lg p-5">
                  <div className="text-xs font-mono text-muted-foreground mb-1">LAST UPDATED</div>
                  <div className="flex items-center gap-2 text-sm">
                    <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
                    {formatDate(company.updated_at)}
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
