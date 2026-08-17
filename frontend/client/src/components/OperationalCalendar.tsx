import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, ClipboardList, Loader2, PackageCheck, UsersRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/WorkspacePrimitives";
import { api, asPaginated } from "@/lib/api";
import { calendarDate, tanzaniaDate } from "@/lib/dates";
import { useLanguage } from "@/contexts/LanguageContext";

type Inspection = { id: number; inspection_date: string; area_name?: string; template_name?: string; status?: string; overall_status?: string; results?: Array<{ id: number; item_label?: string; value_text?: string; passed?: boolean | null }>; };
type DailyReport = { id: number; site_id: number; site_name?: string; status?: string; attendance_summary?: Record<string, unknown>; store_summary?: Record<string, unknown>; trainee_summary?: Record<string, unknown>; issues_summary?: Record<string, unknown>; challenges?: string[]; };
type Issue = { id: number; title?: string; status?: string; priority?: string; created_at?: string; site_name?: string; };

const monthTitle = (value: Date, language: string) => value.toLocaleDateString(language === "sw" ? "sw-TZ" : "en-GB", { month: "long", year: "numeric" });
const count = (summary: Record<string, unknown> | undefined, key: string) => Number(summary?.[key] || 0);

export function OperationalCalendar() {
  const { t, language } = useLanguage();
  const today = useMemo(() => tanzaniaDate(), []);
  const [month, setMonth] = useState(() => { const value = calendarDate(today); return new Date(value.getFullYear(), value.getMonth(), 1); });
  const [selectedDate, setSelectedDate] = useState(today);
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.allSettled([
      api.get(`/inspections?page_size=100&date_from=${selectedDate}&date_to=${selectedDate}`),
      api.get(`/reports/site?page_size=100&report_date=${selectedDate}`),
      api.get("/issues?page_size=100"),
    ]).then(([inspectionResult, reportResult, issueResult]) => {
      if (!active) return;
      setInspections(inspectionResult.status === "fulfilled" ? asPaginated(inspectionResult.value).results as Inspection[] : []);
      setReports(reportResult.status === "fulfilled" ? asPaginated(reportResult.value).results as DailyReport[] : []);
      const dailyIssues = issueResult.status === "fulfilled" ? asPaginated(issueResult.value).results as Issue[] : [];
      setIssues(dailyIssues.filter((issue) => String(issue.created_at || "").slice(0, 10) === selectedDate));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedDate]);

  const days = useMemo(() => {
    const start = new Date(month.getFullYear(), month.getMonth(), 1);
    const offset = (start.getDay() + 6) % 7;
    const cells = Array.from({ length: offset }, () => null as Date | null);
    const dayCount = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    for (let day = 1; day <= dayCount; day += 1) cells.push(new Date(month.getFullYear(), month.getMonth(), day));
    return cells;
  }, [month]);

  const weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const selectedDisplay = calendarDate(selectedDate).toLocaleDateString(language === "sw" ? "sw-TZ" : "en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const totalAttendance = reports.reduce((total, report) => total + count(report.attendance_summary, "total"), 0);
  const totalPresent = reports.reduce((total, report) => total + count(report.attendance_summary, "present") + count(report.attendance_summary, "late"), 0);
  const totalTrainees = reports.reduce((total, report) => total + count(report.trainee_summary, "active_today"), 0);
  const totalLowStock = reports.reduce((total, report) => total + count(report.store_summary, "low_stock_items"), 0);

  return <section className="overflow-hidden rounded-[28px] border border-[#E7DED4] bg-[#FFFDFC] shadow-[0_18px_44px_rgba(44,41,35,.07)]">
    <div className="flex flex-col gap-4 border-b border-[#EEE7E0] bg-[linear-gradient(135deg,#FFF7F3,#F5FBF8)] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6"><div><p className="ledger-label text-[#C45232]">{t("Daily survey calendar")}</p><h3 className="mt-1 font-serif text-2xl text-[#263F42]">{t("Choose a day to review site surveys")}</h3></div><div className="flex items-center gap-2 rounded-full border border-[#E6DCD3] bg-white p-1 shadow-sm"><Button variant="ghost" size="icon" aria-label={t("Previous month")} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft size={17} /></Button><span className="min-w-36 px-2 text-center text-sm font-bold text-[#375356]">{monthTitle(month, language)}</span><Button variant="ghost" size="icon" aria-label={t("Next month")} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight size={17} /></Button></div></div>
    <div className="p-5 sm:p-6"><div className="rounded-2xl border border-[#ECE4DC] bg-white p-3 sm:p-4"><div className="grid grid-cols-7 gap-1 text-center text-[11px] font-bold uppercase tracking-[.08em] text-[#8A817A]">{weekday.map((name, index) => <span key={`${name}-${index}`}>{name}</span>)}</div><div className="mt-2 grid grid-cols-7 gap-1.5">{days.map((day, index) => { if (!day) return <span key={`blank-${index}`} />; const value = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`; const isToday = value === today; const selected = value === selectedDate; return <button key={value} onClick={() => setSelectedDate(value)} className={`group relative aspect-square min-h-10 rounded-xl text-sm font-bold transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-[#D86143] ${selected ? "bg-[#D86143] text-white shadow-[0_8px_18px_rgba(216,97,67,.28)]" : "bg-[#FAF7F4] text-[#3B5456] hover:bg-[#FBE9E3]"}`}><span>{day.getDate()}</span>{isToday ? <span className={`absolute bottom-1 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full ${selected ? "bg-white" : "bg-[#D86143]"}`} /> : null}</button>; })}</div></div></div>
    <div className="border-t border-[#EEE7E0] bg-[#173F43] p-5 text-white sm:p-6"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-[#AEE0D3]"><CalendarDays size={20} /></span><div><p className="text-xs font-bold uppercase tracking-[.1em] text-[#AEE0D3]">{t("Selected day")}</p><h4 className="mt-1 font-serif text-xl capitalize">{selectedDisplay}</h4></div></div><span className="rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold text-[#D7E8E4]">{reports.length} {t("site reports")}</span></div>{loading ? <div className="mt-5 flex items-center gap-2 rounded-xl bg-white/10 p-4 text-sm text-[#D7E8E4]"><Loader2 className="animate-spin" size={16} /> {t("Loading daily surveys")}</div> : <><div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Summary icon={CheckCircle2} label={t("Attendance")} value={`${totalPresent} / ${totalAttendance}`} detail={t("present cleaners")} /><Summary icon={UsersRound} label={t("Trainees")} value={String(totalTrainees)} detail={t("active today")} /><Summary icon={PackageCheck} label={t("Low-stock items")} value={String(totalLowStock)} detail={t("need attention")} /><Summary icon={AlertTriangle} label={t("Open issues")} value={String(issues.length)} detail={t("raised this day")} /></div><div className="mt-5 grid gap-4 xl:grid-cols-2"><section className="rounded-2xl bg-white/[.08] p-4"><div className="flex items-center gap-2"><ClipboardList size={17} className="text-[#AEE0D3]" /><h5 className="font-semibold">{t("Daily cleanliness")}</h5></div>{inspections.length ? <div className="mt-3 space-y-2">{inspections.map((inspection) => <div key={inspection.id} className="rounded-xl bg-white/[.08] p-3"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="font-semibold">{inspection.area_name || t("Operational area")}</p><p className="mt-1 text-xs text-[#C8DEDA]">{inspection.template_name || t("Daily survey")}</p></div><StatusBadge status={inspection.status || "draft"} /></div><p className="mt-2 text-xs text-[#B3D1CB]">{inspection.results?.length || 0} {t("answers recorded")}</p></div>)}</div> : <p className="mt-3 text-sm leading-6 text-[#C8DEDA]">{t("No survey is open for this day")}</p>}</section><section className="rounded-2xl bg-white/[.08] p-4"><div className="flex items-center gap-2"><AlertTriangle size={17} className="text-[#F3C2A7]" /><h5 className="font-semibold">{t("Issues & jobs")}</h5></div>{issues.length ? <div className="mt-3 space-y-2">{issues.map((issue) => <div key={issue.id} className="rounded-xl bg-white/[.08] p-3"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{issue.title || t("Operational issue")}</p><p className="mt-1 text-xs text-[#C8DEDA]">{issue.site_name || t("Assigned site")}</p></div><StatusBadge status={issue.status || issue.priority || "open"} /></div></div>)}</div> : <p className="mt-3 text-sm leading-6 text-[#C8DEDA]">{t("No issues were raised on this day.")}</p>}</section></div>{reports.length ? <div className="mt-4 grid gap-3 xl:grid-cols-2">{reports.map((report) => <section key={report.id} className="rounded-2xl bg-white/[.08] p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{report.site_name || `${t("Site")} ${report.site_id}`}</p><p className="mt-1 text-xs text-[#C8DEDA]">{count(report.attendance_summary, "total")} {t("scheduled cleaners")} · {count(report.store_summary, "movements")} {t("stock movements")}</p></div><StatusBadge status={report.status || "draft"} /></div>{report.challenges?.filter(Boolean).length ? <div className="mt-3 rounded-lg bg-white/[.08] p-3"><p className="text-xs font-bold uppercase tracking-[.08em] text-[#AEE0D3]">{t("MENGINEYO / CHANGAMOTO ZILIZOJITOKEZA")}</p><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[#E1F0EC]">{report.challenges.filter(Boolean).map((challenge, index) => <li key={`${report.id}-${index}`}>{challenge}</li>)}</ul></div> : null}</section>)}</div> : null}</>}</div>
  </section>;
}

function Summary({ icon: Icon, label, value, detail }: { icon: typeof CheckCircle2; label: string; value: string; detail: string }) {
  return <div className="rounded-2xl bg-white/[.09] p-4"><div className="flex items-center gap-2 text-[#AEE0D3]"><Icon size={16} /><p className="text-xs font-bold uppercase tracking-[.08em]">{label}</p></div><p className="mt-3 font-serif text-3xl text-white">{value}</p><p className="mt-1 text-xs text-[#C8DEDA]">{detail}</p></div>;
}
