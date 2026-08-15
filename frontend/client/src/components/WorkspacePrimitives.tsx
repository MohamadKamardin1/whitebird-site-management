/** Coastal Ledger workspace primitives: safe API display, readable status, permission, loading, error, and data-table patterns. */
import { ReactNode } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, CircleAlert, FileWarning, RefreshCw, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApiError } from "@/lib/api";

const LABEL_KEYS = ["name", "label", "title", "full_name", "site_name", "zone_name", "store_name", "cleaner_name", "shift_name", "value", "code", "id"];

export function formatDisplayValue(value: unknown, fallback = "—"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : fallback;
  if (typeof value === "string") return value.replaceAll("_", " ");
  if (value instanceof Date) return value.toLocaleString();
  if (Array.isArray(value)) return value.length ? `${value.length} items` : "None";
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const labelKey = LABEL_KEYS.find((key) => record[key] !== undefined && record[key] !== null && record[key] !== "");
    if (labelKey) return formatDisplayValue(record[labelKey], fallback);
    const compact = Object.entries(record)
      .filter(([key]) => !["id", "created_at", "updated_at"].includes(key))
      .slice(0, 2)
      .map(([key, nested]) => `${key.replaceAll("_", " ")}: ${formatDisplayValue(nested)}`)
      .join(" · ");
    return compact || fallback;
  }
  return String(value);
}

export function formatDateValue(value: unknown, fallback = "—") {
  if (!value) return fallback;
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? formatDisplayValue(value, fallback) : date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

export function formatTimeValue(value: unknown, fallback = "") {
  if (!value) return fallback;
  const raw = String(value);
  return raw.length >= 5 ? raw.slice(0, 5) : raw;
}

export function WorkspaceHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="mb-7 border-b border-[#D7D1C4] pb-5"><div className="flex flex-col justify-between gap-4 md:flex-row md:items-end"><div className="max-w-3xl"><p className="ledger-label text-[#0F7667]">{eyebrow}</p><h2 className="mt-1 font-serif text-3xl leading-tight tracking-[-0.03em] text-[#16373A] sm:text-4xl">{title}</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-[#5B6B68] sm:text-[15px]">{description}</p></div>{actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}</div></div>;
}

export function StatusBadge({ status }: { status?: unknown }) {
  const value = formatDisplayValue(status, "Not set");
  const normalized = value.toLowerCase();
  const tone = normalized.includes("complete") || normalized.includes("active") || normalized.includes("verified") || normalized.includes("passed") || normalized.includes("reviewed") || normalized.includes("present") ? "bg-[#DDF0E9] text-[#0A6558] border-[#BCE1D5]" : normalized.includes("overdue") || normalized.includes("urgent") || normalized.includes("reject") || normalized.includes("fail") || normalized.includes("absent") ? "bg-[#FBE4DD] text-[#A13E26] border-[#F3C2B6]" : normalized.includes("draft") || normalized.includes("pending") || normalized.includes("attention") || normalized.includes("return") || normalized.includes("scheduled") ? "bg-[#FBEDD7] text-[#9A5B12] border-[#F0D7AD]" : "bg-[#E7ECE8] text-[#48605C] border-[#D5DED9]";
  return <Badge variant="outline" className={`capitalize whitespace-nowrap border px-2 py-0.5 text-[11px] font-bold ${tone}`}>{value}</Badge>;
}

export function LoadingPanel({ label = "Loading your workspace" }: { label?: string }) {
  return <div className="flex min-h-[280px] flex-col items-center justify-center rounded-2xl border border-dashed border-[#D5CFC2] bg-[#FCFAF5] text-center"><span className="mb-4 h-9 w-9 animate-spin rounded-full border-[3px] border-[#C7DED9] border-t-[#0F7667]" /><h3 className="font-serif text-xl text-[#234347]">{label}</h3><p className="mt-1 text-sm text-[#6B7773]">Checking the latest operational state.</p></div>;
}

export function ApiErrorPanel({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const known = error instanceof ApiError ? error : null;
  const accessProblem = known?.status === 403;
  return <div className="rounded-2xl border border-[#E9C8BC] bg-[#FFF7F3] p-6 sm:p-8"><div className="flex flex-col gap-4 sm:flex-row sm:items-start"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#FBE0D7] text-[#A2482E]">{accessProblem ? <ShieldAlert size={20} /> : <CircleAlert size={20} />}</div><div className="min-w-0 flex-1"><p className="ledger-label text-[#A2482E]">{accessProblem ? "Access context" : "Service response"}</p><h3 className="mt-1 font-serif text-2xl text-[#74301F]">{accessProblem ? "This action is outside your current scope" : "This workspace needs attention"}</h3><p className="mt-2 max-w-2xl text-sm leading-6 text-[#6C493E]">{known?.message || "We could not load the requested operational data. Your work has not been changed."}</p>{known?.traceId && <p className="mt-3 font-mono text-xs text-[#8A6255]">Support trace: {known.traceId}</p>}</div>{onRetry && <Button variant="outline" className="border-[#D9AB9D] bg-white text-[#833B28] hover:bg-[#FFF1EC]" onClick={onRetry}><RefreshCw size={15} /> Retry</Button>}</div></div>;
}

export function EmptyPanel({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="relative overflow-hidden rounded-2xl border border-dashed border-[#D7D0C1] bg-[#FFFDF8] px-6 py-12 text-center"><div className="pointer-events-none absolute inset-0 opacity-[0.035] [background-image:linear-gradient(135deg,#0F7667_1px,transparent)] [background-size:24px_24px]" /><div className="relative mx-auto max-w-md"><span className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-[#E2EFEA] text-[#0F7667]"><FileWarning size={21} /></span><h3 className="mt-4 font-serif text-2xl text-[#234347]">{title}</h3><p className="mt-2 text-sm leading-6 text-[#667570]">{description}</p>{action && <div className="mt-5">{action}</div>}</div></div>;
}

export function DataTable({ rows, onOpen }: { rows: Record<string, unknown>[]; onOpen?: (row: Record<string, unknown>) => void }) {
  if (rows.length === 0) return <EmptyPanel title="Nothing is waiting here" description="When the service returns records for this scope, they will appear in this operational list." />;
  const preferred = ["site_name", "zone_name", "full_name", "cleaner_name", "title", "job_title", "store_name", "report_date", "attendance_date", "status", "priority", "updated_at", "created_at"];
  const keys = [...preferred.filter((key) => rows.some((row) => key in row)), ...Object.keys(rows[0]).filter((key) => !preferred.includes(key) && !["id", "description", "snapshot"].includes(key))].slice(0, 6);
  return <div className="overflow-hidden rounded-2xl border border-[#D9D3C6] bg-[#FFFDF9] shadow-[0_10px_25px_rgba(29,54,50,.04)]"><div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left"><thead><tr className="border-b border-[#E6E0D5] bg-[#F5F2E9]">{keys.map((key) => <th key={key} className="px-5 py-3 text-[11px] font-extrabold uppercase tracking-[.12em] text-[#60706C]">{key.replaceAll("_", " ")}</th>)}<th className="px-5 py-3"><span className="sr-only">Open</span></th></tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id || index)} className="group border-b border-[#EEE9DE] last:border-0 transition-colors hover:bg-[#FAF8F2]">{keys.map((key) => <td key={key} className="max-w-[220px] px-5 py-4 text-sm text-[#365055]">{key === "status" || key === "priority" || key === "review_status" ? <StatusBadge status={row[key]} /> : <span className={key.includes("name") || key.includes("title") ? "font-semibold text-[#193D41]" : ""}>{key.endsWith("_date") ? formatDateValue(row[key]) : formatDisplayValue(row[key])}</span>}</td>)}<td className="px-5 py-4 text-right"><Button variant="ghost" size="sm" className="text-[#0F7667] opacity-70 transition-opacity group-hover:opacity-100" onClick={() => onOpen?.(row)}>Open <ArrowRight size={15} /></Button></td></tr>)}</tbody></table></div></div>;
}

export function WorkflowNotice({ children }: { children: ReactNode }) { return <div className="flex items-start gap-3 rounded-xl border border-[#C9E2D9] bg-[#F0F8F4] px-4 py-3 text-sm leading-6 text-[#28564E]"><CheckCircle2 className="mt-0.5 shrink-0 text-[#0F7667]" size={18} /> <span>{children}</span></div>; }
export function AttentionNotice({ children }: { children: ReactNode }) { return <div className="flex items-start gap-3 rounded-xl border border-[#ECD7AB] bg-[#FFF8E8] px-4 py-3 text-sm leading-6 text-[#805718]"><AlertTriangle className="mt-0.5 shrink-0 text-[#B87413]" size={18} /> <span>{children}</span></div>; }
