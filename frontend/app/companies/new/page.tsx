"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Navigation } from "@/components/landing/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft, ArrowRight, Loader2, Building2 } from "lucide-react";
import { createCompany } from "@/lib/api";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Industry options — common supply chain verticals
// ---------------------------------------------------------------------------
const INDUSTRIES = [
  "Consumer Electronics",
  "Automotive",
  "Pharmaceuticals",
  "Food & Beverage",
  "Apparel & Textiles",
  "Industrial Manufacturing",
  "Retail",
  "Logistics & Freight",
  "Chemicals",
  "Agriculture",
  "Other",
];

const COUNTRIES = [
  "India",
  "China",
  "United States",
  "Germany",
  "Japan",
  "United Kingdom",
  "South Korea",
  "Brazil",
  "Mexico",
  "Singapore",
  "Other",
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function NewCompanyPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [country, setCountry] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nameError = name.trim().length === 0 && name.length > 0
    ? "Company name is required"
    : null;

  const canSubmit = name.trim().length > 0 && !isSubmitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    try {
      const company = await createCompany({
        name: name.trim(),
        industry: industry.trim(),
        country: country.trim(),
      });
      toast.success("Company created", {
        description: `"${company.name}" is ready.`,
      });
      router.push(`/companies/${company.id}`);
    } catch (e) {
      toast.error("Failed to create company", {
        description: e instanceof Error ? e.message : "Unknown error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <section className="relative py-32">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
          <div className="max-w-2xl">

            {/* Header */}
            <div className="mb-12">
              <Link href="/companies">
                <Button variant="outline" className="mb-6 border-foreground/20 hover:bg-foreground/5">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Companies
                </Button>
              </Link>
              <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
                <span className="w-8 h-px bg-foreground/30" />
                New Company
              </span>
              <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-3">
                Create Company
              </h1>
              <p className="text-lg text-muted-foreground">
                Add your business entity. You can link products, suppliers, warehouses,
                and a Digital Twin after creation.
              </p>
            </div>

            {/* Form */}
            <form
              onSubmit={handleSubmit}
              className="bg-background border border-foreground/10 rounded-lg p-8 space-y-6"
            >
              {/* Icon preview */}
              <div className="flex items-center gap-4 pb-4 border-b border-foreground/10">
                <div className="w-14 h-14 rounded-xl bg-foreground/5 flex items-center justify-center">
                  <Building2 className="w-7 h-7 text-muted-foreground" />
                </div>
                <div>
                  <div className="font-display text-xl">
                    {name.trim() || <span className="text-muted-foreground">Company Name</span>}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {[industry, country].filter(Boolean).join(" · ") || "No details yet"}
                  </div>
                </div>
              </div>

              {/* Company Name */}
              <div className="space-y-2">
                <Label htmlFor="name" className="text-base">
                  Company Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="name"
                  placeholder="e.g., ABC Electronics"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="text-base px-4 py-3"
                  disabled={isSubmitting}
                  autoFocus
                />
                {nameError && <p className="text-sm text-destructive">{nameError}</p>}
              </div>

              {/* Industry */}
              <div className="space-y-2">
                <Label htmlFor="industry" className="text-base">
                  Industry
                  <span className="text-muted-foreground text-xs font-normal ml-2">(optional)</span>
                </Label>
                <div className="relative">
                  <Input
                    id="industry"
                    placeholder="e.g., Consumer Electronics"
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="text-base px-4 py-3"
                    disabled={isSubmitting}
                    list="industry-options"
                  />
                  <datalist id="industry-options">
                    {INDUSTRIES.map((i) => <option key={i} value={i} />)}
                  </datalist>
                </div>
                <p className="text-xs text-muted-foreground">
                  Type or pick from common verticals
                </p>
              </div>

              {/* Country */}
              <div className="space-y-2">
                <Label htmlFor="country" className="text-base">
                  Country
                  <span className="text-muted-foreground text-xs font-normal ml-2">(optional)</span>
                </Label>
                <div className="relative">
                  <Input
                    id="country"
                    placeholder="e.g., India"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="text-base px-4 py-3"
                    disabled={isSubmitting}
                    list="country-options"
                  />
                  <datalist id="country-options">
                    {COUNTRIES.map((c) => <option key={c} value={c} />)}
                  </datalist>
                </div>
              </div>

              {/* Submit */}
              <div className="flex gap-4 pt-4">
                <Button
                  type="submit"
                  size="lg"
                  disabled={!canSubmit}
                  className="bg-foreground hover:bg-foreground/90 text-background px-8 h-14 text-base rounded-full group flex-1"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Creating…
                    </>
                  ) : (
                    <>
                      Create Company
                      <ArrowRight className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-1" />
                    </>
                  )}
                </Button>
                <Link href="/companies">
                  <Button
                    type="button"
                    size="lg"
                    variant="outline"
                    disabled={isSubmitting}
                    className="h-14 px-8 text-base rounded-full border-foreground/20 hover:bg-foreground/5"
                  >
                    Cancel
                  </Button>
                </Link>
              </div>
            </form>
          </div>
        </div>
      </section>
    </main>
  );
}
