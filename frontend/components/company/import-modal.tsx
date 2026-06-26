"use client";

import { useState, useRef, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Upload,
  FileText,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Download,
  ArrowRight,
  RotateCcw,
} from "lucide-react";
import { previewImport, executeImport, downloadTemplate } from "@/lib/api";
import type {
  ImportPreviewResponse,
  ImportResultResponse,
  ImportEntityType,
} from "@/lib/types";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ImportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyId: number;
  companyName: string;
  entityType: ImportEntityType;
  onComplete: () => void;
}

// ---------------------------------------------------------------------------
// Entity display config
// ---------------------------------------------------------------------------

const ENTITY_LABELS: Record<ImportEntityType, string> = {
  products: "Products",
  suppliers: "Suppliers",
  warehouses: "Warehouses",
};

const ENTITY_COLUMNS: Record<ImportEntityType, string[]> = {
  products: ["name", "category", "stock", "demand"],
  suppliers: ["name", "lead_time", "reliability", "status"],
  warehouses: ["name", "location", "capacity", "warehouse_id"],
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type ModalStage = "upload" | "preview" | "importing" | "result";

export function ImportModal({
  open,
  onOpenChange,
  companyId,
  companyName,
  entityType,
  onComplete,
}: ImportModalProps) {
  const [stage, setStage] = useState<ModalStage>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportResultResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const label = ENTITY_LABELS[entityType];
  const columns = ENTITY_COLUMNS[entityType];

  const reset = useCallback(() => {
    setStage("upload");
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setLoading(false);
    setDragOver(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleClose = (isOpen: boolean) => {
    if (!isOpen) reset();
    onOpenChange(isOpen);
  };

  const handleFileSelect = (f: File) => {
    if (!f.name.endsWith(".csv")) {
      toast.error("Please select a CSV file");
      return;
    }
    if (f.size > 1024 * 1024) {
      toast.error("File too large (max 1MB)");
      return;
    }
    setFile(f);
    setError(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFileSelect(f);
  };

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await previewImport(companyId, entityType, file);
      setPreview(data);
      setStage("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (!file) return;
    setStage("importing");
    setError(null);
    try {
      const data = await executeImport(companyId, entityType, file);
      setResult(data);
      setStage("result");
      onComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
      setStage("preview");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-display text-xl">
            <Upload className="w-5 h-5" />
            Import {label}
          </DialogTitle>
        </DialogHeader>

        {/* ───────── STAGE 1: UPLOAD ───────── */}
        {stage === "upload" && (
          <div className="space-y-6">
            {/* Drop zone */}
            <div
              className={`
                border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
                ${dragOver
                  ? "border-foreground/40 bg-foreground/5"
                  : file
                    ? "border-emerald-500/30 bg-emerald-500/5"
                    : "border-foreground/15 hover:border-foreground/25"
                }
              `}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFileSelect(f);
                }}
              />

              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <FileText className="w-8 h-8 text-emerald-500" />
                  <div className="text-left">
                    <div className="font-medium">{file.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {(file.size / 1024).toFixed(1)} KB
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <Upload className="w-10 h-10 mx-auto text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground">
                    Drop a CSV file here, or click to browse
                  </p>
                  <p className="text-xs text-muted-foreground/60 mt-1">
                    Maximum 1MB · UTF-8 encoded
                  </p>
                </>
              )}
            </div>

            {/* Template download */}
            <div className="flex items-center justify-between border border-foreground/10 rounded-lg px-4 py-3">
              <div>
                <div className="text-sm font-medium">Need a template?</div>
                <div className="text-xs text-muted-foreground">
                  Download a CSV template with example {label.toLowerCase()}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="border-foreground/20 gap-2"
                onClick={() => downloadTemplate(entityType)}
              >
                <Download className="w-3.5 h-3.5" />
                Template
              </Button>
            </div>

            {/* Expected format */}
            <div className="border border-foreground/10 rounded-lg p-4">
              <div className="text-xs font-mono text-muted-foreground mb-2">
                EXPECTED CSV FORMAT
              </div>
              <code className="text-xs bg-muted/50 block px-3 py-2 rounded font-mono">
                {columns.join(",")}
              </code>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-4 py-3">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => handleClose(false)}
                className="border-foreground/20"
              >
                Cancel
              </Button>
              <Button
                onClick={handlePreview}
                disabled={!file || loading}
                className="bg-foreground hover:bg-foreground/90 text-background gap-2"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowRight className="w-4 h-4" />
                )}
                Preview
              </Button>
            </div>
          </div>
        )}

        {/* ───────── STAGE 2: PREVIEW ───────── */}
        {stage === "preview" && preview && (
          <div className="space-y-5">
            {/* Summary strip */}
            <div className="grid grid-cols-3 gap-3">
              <div className="border border-foreground/10 rounded-lg p-3 text-center">
                <div className="text-xs font-mono text-muted-foreground">TOTAL</div>
                <div className="text-2xl font-display">{preview.total_rows}</div>
              </div>
              <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-lg p-3 text-center">
                <div className="text-xs font-mono text-emerald-600">VALID</div>
                <div className="text-2xl font-display text-emerald-500">
                  {preview.valid_rows}
                </div>
              </div>
              <div className={`border rounded-lg p-3 text-center ${
                preview.invalid_rows > 0
                  ? "border-red-500/20 bg-red-500/5"
                  : "border-foreground/10"
              }`}>
                <div className={`text-xs font-mono ${
                  preview.invalid_rows > 0 ? "text-red-600" : "text-muted-foreground"
                }`}>INVALID</div>
                <div className={`text-2xl font-display ${
                  preview.invalid_rows > 0 ? "text-red-500" : ""
                }`}>
                  {preview.invalid_rows}
                </div>
              </div>
            </div>

            {/* Preview table */}
            <div className="border border-foreground/10 rounded-lg overflow-hidden">
              <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/30 sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left font-mono text-xs text-muted-foreground w-8">#</th>
                      <th className="px-3 py-2 text-left font-mono text-xs text-muted-foreground w-8"></th>
                      {columns.map((col) => (
                        <th key={col} className="px-3 py-2 text-left font-mono text-xs text-muted-foreground">
                          {col.toUpperCase()}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview.map((row) => (
                      <tr
                        key={row.row}
                        className={`border-t border-foreground/5 ${
                          !row.valid ? "bg-red-500/5" : ""
                        }`}
                      >
                        <td className="px-3 py-2 text-xs text-muted-foreground">{row.row}</td>
                        <td className="px-3 py-2">
                          {row.valid ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                          ) : (
                            <XCircle className="w-4 h-4 text-red-500" />
                          )}
                        </td>
                        {columns.map((col) => (
                          <td key={col} className="px-3 py-2 text-sm">
                            {String(row.data[col] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Error details for invalid rows */}
            {preview.invalid_rows > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-mono text-muted-foreground">VALIDATION ERRORS</div>
                {preview.preview
                  .filter((r) => !r.valid)
                  .map((r) => (
                    <div
                      key={r.row}
                      className="flex items-start gap-2 text-sm border border-red-500/15 bg-red-500/5 rounded-lg px-3 py-2"
                    >
                      <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-mono text-xs text-red-500">Row {r.row}:</span>{" "}
                        {r.errors.join("; ")}
                      </div>
                    </div>
                  ))}
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-4 py-3">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <div className="flex justify-between">
              <Button
                variant="outline"
                onClick={reset}
                className="border-foreground/20 gap-2"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Back
              </Button>
              <Button
                onClick={handleImport}
                disabled={preview.valid_rows === 0}
                className="bg-foreground hover:bg-foreground/90 text-background gap-2"
              >
                Import {preview.valid_rows} {label}
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {/* ───────── STAGE 2.5: IMPORTING ───────── */}
        {stage === "importing" && (
          <div className="flex flex-col items-center justify-center py-12 gap-4">
            <Loader2 className="w-10 h-10 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Importing {label.toLowerCase()} into {companyName}...
            </p>
          </div>
        )}

        {/* ───────── STAGE 3: RESULT ───────── */}
        {stage === "result" && result && (
          <div className="space-y-5">
            {/* Success banner */}
            <div className="flex items-center gap-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-5">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 shrink-0" />
              <div>
                <div className="font-display text-lg">Import Complete</div>
                <div className="text-sm text-muted-foreground mt-0.5">
                  {result.success} {label.toLowerCase()} processed successfully
                </div>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "TOTAL", value: result.total_rows },
                { label: "SUCCESS", value: result.success, color: "text-emerald-500" },
                { label: "CREATED", value: result.created, color: "text-blue-500" },
                { label: "UPDATED", value: result.updated, color: "text-amber-500" },
              ].map(({ label: l, value, color }) => (
                <div key={l} className="border border-foreground/10 rounded-lg p-3 text-center">
                  <div className="text-xs font-mono text-muted-foreground">{l}</div>
                  <div className={`text-xl font-display ${color || ""}`}>{value}</div>
                </div>
              ))}
            </div>

            {/* Errors */}
            {result.failed > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-mono text-muted-foreground">
                  {result.failed} ROW{result.failed !== 1 ? "S" : ""} FAILED
                </div>
                {result.errors.map((err, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-sm border border-red-500/15 bg-red-500/5 rounded-lg px-3 py-2"
                  >
                    <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-mono text-xs text-red-500">Row {err.row}:</span>{" "}
                      {err.message}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-between pt-2 border-t border-foreground/5">
              <Button
                variant="outline"
                onClick={() => handleClose(false)}
                className="border-foreground/20"
              >
                Done
              </Button>
              <Button
                onClick={() => {
                  handleClose(false);
                  window.location.href = "/form";
                }}
                className="bg-foreground hover:bg-foreground/90 text-background gap-2"
              >
                Run Simulation
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
