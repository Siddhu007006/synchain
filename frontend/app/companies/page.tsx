"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import {
  Building2,
  Plus,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  Globe,
  Factory,
} from "lucide-react";
import { listCompanies, archiveCompany } from "@/lib/api";
import type { Company } from "@/lib/types";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatDate(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
const PageSkeleton = () => (
  <div className="animate-pulse space-y-3">
    {[...Array(4)].map((_, i) => (
      <div key={i} className="border border-foreground/10 rounded-lg p-6 h-24" />
    ))}
  </div>
);

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
const EmptyState = () => (
  <div className="flex flex-col items-center justify-center py-24 text-center border border-dashed border-foreground/10 rounded-lg">
    <div className="w-16 h-16 rounded-full bg-muted/30 flex items-center justify-center mb-6">
      <Building2 className="w-8 h-8 text-muted-foreground" />
    </div>
    <h3 className="text-xl font-display mb-2">No companies yet</h3>
    <p className="text-muted-foreground mb-8 max-w-sm">
      Create your first company to start managing products, suppliers, and supply chain intelligence.
    </p>
    <Link href="/companies/new">
      <Button className="bg-foreground hover:bg-foreground/90 text-background rounded-full gap-2">
        <Plus className="w-4 h-4" />
        Create Company
      </Button>
    </Link>
  </div>
);

// ---------------------------------------------------------------------------
// Company Card
// ---------------------------------------------------------------------------
const CompanyCard = ({
  company,
  onDelete,
}: {
  company: Company;
  onDelete: (id: number) => void;
}) => (
  <div className="border border-foreground/10 rounded-lg p-6 hover:border-foreground/20 transition-colors group">
    <div className="flex items-start justify-between gap-4">
      <div className="flex items-start gap-4 flex-1 min-w-0">
        <div className="w-10 h-10 rounded-lg bg-foreground/5 flex items-center justify-center shrink-0">
          <Building2 className="w-5 h-5 text-muted-foreground" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-display text-lg truncate">{company.name}</h3>
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
            {!company.industry && !company.country && (
              <span className="text-foreground/30 text-xs font-mono">No details added</span>
            )}
          </div>
          <div className="text-xs font-mono text-foreground/30 mt-2">
            Created {formatDate(company.created_at)}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <Link href={`/companies/${company.id}`}>
          <Button
            variant="outline"
            size="sm"
            className="border-foreground/20 gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            View
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        </Link>
      </div>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCompanies(50, 0);
      setCompanies(data.companies);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load companies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: number) => {
    const company = companies.find((c) => c.id === id);
    if (!company) return;
    if (!window.confirm(`Archive or delete "${company.name}"?`)) return;
    try {
      // Backend returns 409 when company has data, or archives when empty
      await archiveCompany(id);
      setCompanies((prev) => prev.filter((c) => c.id !== id));
      setTotal((t) => t - 1);
      toast.success(`"${company.name}" archived`, {
        description: "No data was deleted. The company is now archived.",
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      // Try to parse a 409 conflict payload — apiFetch serializes detail objects as JSON
      let detail: Record<string, unknown> | null = null;
      try {
        const jsonStart = msg.indexOf("{");
        if (jsonStart !== -1) detail = JSON.parse(msg.slice(jsonStart));
      } catch { /* not parseable */ }

      if (detail && detail.error === "company_has_data") {
        const counts = detail.counts as Record<string, number> | undefined;
        const parts: string[] = [];
        if (counts?.twins)       parts.push(`${counts.twins} twin${counts.twins !== 1 ? "s" : ""}`);
        if (counts?.simulations) parts.push(`${counts.simulations} simulation${counts.simulations !== 1 ? "s" : ""}`);
        if (counts?.products)    parts.push(`${counts.products} product${counts.products !== 1 ? "s" : ""}`);
        if (counts?.suppliers)   parts.push(`${counts.suppliers} supplier${counts.suppliers !== 1 ? "s" : ""}`);
        if (counts?.warehouses)  parts.push(`${counts.warehouses} warehouse${counts.warehouses !== 1 ? "s" : ""}`);
        const summary = parts.join(", ");

        const confirmArchive = window.confirm(
          `"${company.name}" contains ${summary}.\n\nArchive it instead? All data will be preserved and can be restored later.`
        );
        if (confirmArchive) {
          try {
            await archiveCompany(id);
            setCompanies((prev) => prev.filter((c) => c.id !== id));
            setTotal((t) => t - 1);
            toast.success(`"${company.name}" archived`, {
              description: `${summary} preserved. Restore anytime from this page.`,
            });
          } catch (archiveErr) {
            toast.error("Archive failed", {
              description: archiveErr instanceof Error ? archiveErr.message : "Unknown error",
            });
          }
        }
      } else {
        toast.error("Operation failed", { description: msg });
      }
    }
  };

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <section className="relative py-32">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12">

          {/* Header */}
          <div className="mb-12">
            <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
              <span className="w-8 h-px bg-foreground/30" />
              V2
            </span>
            <div className="flex items-end justify-between gap-6">
              <div>
                <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-3">
                  Companies
                </h1>
                <p className="text-muted-foreground text-lg">
                  Manage your business entities. Each company owns its products, suppliers,
                  warehouses, and intelligence pipeline.
                </p>
              </div>
              <Link href="/companies/new">
                <Button className="bg-foreground hover:bg-foreground/90 text-background rounded-full gap-2 shrink-0">
                  <Plus className="w-4 h-4" />
                  New Company
                </Button>
              </Link>
            </div>
          </div>

          {/* Stats bar */}
          {!loading && !error && total > 0 && (
            <div className="mb-8 flex items-center justify-between">
              <span className="text-sm font-mono text-muted-foreground">
                {total} {total === 1 ? "company" : "companies"}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={load}
                className="border-foreground/20 gap-2"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Refresh
              </Button>
            </div>
          )}

          {/* Content */}
          {loading && <PageSkeleton />}

          {!loading && error && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-6">
                <AlertCircle className="w-8 h-8 text-destructive" />
              </div>
              <p className="text-muted-foreground mb-6 max-w-sm">{error}</p>
              <Button onClick={load} variant="outline" className="gap-2">
                <RefreshCw className="w-4 h-4" /> Retry
              </Button>
            </div>
          )}

          {!loading && !error && companies.length === 0 && <EmptyState />}

          {!loading && !error && companies.length > 0 && (
            <div className="space-y-3">
              {companies.map((c) => (
                <CompanyCard key={c.id} company={c} onDelete={handleDelete} />
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
