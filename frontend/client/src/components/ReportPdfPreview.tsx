import { FileBarChart2 } from "lucide-react";
import { StatusBadge } from "@/components/WorkspacePrimitives";

type Value = Record<string, any>;

type Props = {
  report: Value;
  user: Value | null | undefined;
  site: Value | undefined;
  reportType: string;
  reportDate: string;
};

const title = (key: string) => key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const number = (value: unknown) => typeof value === "number" ? value : Number(value || 0);
const summaryDefinitions = [
  { key: "attendance_summary", label: "Attendance summary", tone: "bg-[#F0F7F4]", fields: ["total", "present", "late", "absent", "sick", "leave", "permission", "off", "attendance_rate"] },
  { key: "store_summary", label: "Store summary", tone: "bg-[#F8F5EC]", fields: ["movements", "received", "issued", "damaged_lost", "low_stock_items"] },
  { key: "inspection_summary", label: "Inspection summary", tone: "bg-[#EFF4FA]", fields: ["total", "passed", "failed", "needs_attention", "average_score"] },
  { key: "trainee_summary", label: "Trainee summary", tone: "bg-[#F6F0FA]", fields: ["in_training", "extended", "passed", "failed", "dropped", "active_today"] },
  { key: "issues_summary", label: "Issues summary", tone: "bg-[#FFF2DF]", fields: ["raised_today", "open", "escalated", "urgent"] },
] as const;

function SummaryCard({ label, summary, tone, fields }: { label: string; summary: Value; tone: string; fields: readonly string[] }) {
  return <section className={`rounded-xl border border-[#E5DED3] p-4 ${tone}`}><div className="flex items-center justify-between gap-3"><h4 className="font-semibold capitalize text-[#315156]">{label}</h4><span className="ledger-label text-[#71807A]">Evidence</span></div><div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">{fields.map((field) => <div key={field} className="min-w-0"><p className="text-[11px] font-medium uppercase tracking-[.08em] text-[#71807A]">{title(field)}</p><p className="mt-1 truncate text-lg font-semibold text-[#21464A]">{field === "attendance_rate" || field === "average_score" ? `${number(summary[field])}${field === "attendance_rate" ? "%" : " / 100"}` : number(summary[field])}</p></div>)}</div></section>;
}

function DailyEvidence({ data }: { data: Value }) {
  return <div className="grid gap-4 md:grid-cols-2">{summaryDefinitions.map((definition) => <SummaryCard key={definition.key} label={definition.label} summary={data[definition.key] || {}} tone={definition.tone} fields={definition.fields} />)}<section className="rounded-xl border border-[#E5DED3] bg-white p-4 md:col-span-2"><h4 className="font-semibold text-[#315156]">General comments</h4><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#596D67]">{String(data.general_comments || "No general comments recorded.")}</p></section></div>;
}

export default function ReportPdfPreview({ report, user, site, reportType, reportDate }: Props) {
  const weekly = reportType === "weekly";
  return <div className="report-print-sheet mt-5 min-w-0 rounded-xl border border-[#C9DAD4] bg-white p-4 text-[#21464A] shadow-[0_12px_30px_rgba(18,55,53,.08)] sm:p-6"><header className="flex flex-col gap-4 border-b-2 border-[#0F7667] pb-5 sm:flex-row sm:items-start sm:justify-between"><div className="min-w-0"><p className="ledger-label text-[#0F7667]">WHITE BIRD ZANZIBAR · OPERATIONS CONTROL</p><h3 className="mt-2 font-serif text-3xl tracking-[-.04em]">{weekly ? "Weekly site report" : "Daily site report"}</h3><p className="mt-2 text-sm text-[#63746E]">{site?.name || report.site_name || `Site ${report.site_id}`} · {weekly ? `${report.week_start} to ${report.week_end}` : reportDate}</p></div><div className="text-left text-xs leading-5 text-[#64746F] sm:text-right"><p><strong>Reporter:</strong> {user?.full_name || user?.email || "Authenticated supervisor"}</p><p><strong>Role:</strong> {String(user?.role || "operations")}</p><p><strong>Generated:</strong> {new Date().toLocaleString()}</p><p><strong>Review status:</strong> Prepared for review</p></div></header><div className="mt-5 grid gap-3 sm:grid-cols-3"><div className="rounded-lg bg-[#F0F7F4] p-3"><p className="ledger-label text-[#0F7667]">Evidence window</p><p className="mt-1 text-sm font-semibold">{weekly ? "Monday–Friday operational evidence" : "One completed operational day"}</p></div><div className="rounded-lg bg-[#F8F5EC] p-3"><p className="ledger-label text-[#687874]">Scope</p><p className="mt-1 text-sm font-semibold">{site?.zone_name || "Authorised site scope"}</p></div><div className="rounded-lg bg-[#FFF2DF] p-3"><p className="ledger-label text-[#9A5A22]">Integrity</p><p className="mt-1 text-sm font-semibold">Source data only · no fabricated results</p></div></div>{weekly ? <div className="mt-6 space-y-5"><div className="flex items-center gap-2"><FileBarChart2 size={16} className="text-[#0F7667]" /><h4 className="font-semibold">Daily evidence ledger</h4></div>{(report.days || []).map((day: Value) => <section key={day.report_date} className="rounded-xl border border-[#DDE8E2] bg-[#FAFDFC] p-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold text-[#315156]">{day.report_date}</p><StatusBadge status={day.status} /></div><div className="mt-4"><DailyEvidence data={day.data || {}} /></div></section>)}</div> : <div className="mt-6"><DailyEvidence data={report} /></div>}<footer className="mt-6 border-t border-[#E5DED3] pt-4 text-xs leading-5 text-[#687874]"><p><strong>Handover:</strong> This report is a review-ready operational snapshot. Exceptions, corrective actions, and unresolved items must continue through their existing audited workflows.</p><div className="mt-5 grid gap-5 sm:grid-cols-2"><p>Prepared by: ____________________</p><p>Reviewed by: ____________________</p></div></footer></div>;
}
