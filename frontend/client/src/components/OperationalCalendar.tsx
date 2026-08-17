import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, ClipboardList, Loader2, PackageCheck, UsersRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/WorkspacePrimitives";
import { api, asPaginated } from "@/lib/api";
import { calendarDate, tanzaniaDate } from "@/lib/dates";
import { useLanguage } from "@/contexts/LanguageContext";
import { preferredCleanlinessTemplates } from "@/lib/cleanlinessTemplates";
import { aggregateDailyAttendance, type AttendanceSummaryRecord } from "@/lib/attendanceSummary";

type Inspection = { id: number; template_id: number; status?: string; results?: Array<{ id: number }>; };
type CleanlinessTemplate = { id: number; template_name: string; area_name?: string; description?: string; is_active?: boolean; };
type DailyReport = { id: number; site_id: number; site_name?: string; status?: string; attendance_summary?: Record<string, unknown>; store_summary?: Record<string, unknown>; trainee_summary?: Record<string, unknown>; issues_summary?: Record<string, unknown>; challenges?: string[]; };
type Issue = { id: number; title?: string; status?: string; priority?: string; created_at?: string; site_name?: string; };
type Site = { id: number; };

const monthTitle = (value: Date, language: string) => value.toLocaleDateString(language === "sw" ? "sw-TZ" : "en-GB", { month: "long", year: "numeric" });
const count = (summary: Record<string, unknown> | undefined, key: string) => Number(summary?.[key] || 0);
const englishAreaName = (name: string) => name.split("/")[0].trim();

export function OperationalCalendar() {
  const { t, language } = useLanguage();
  const today = useMemo(() => tanzaniaDate(), []);
  const [month, setMonth] = useState(() => { const value = calendarDate(today); return new Date(value.getFullYear(), value.getMonth(), 1); });
  const [selectedDate, setSelectedDate] = useState(today);
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [templates, setTemplates] = useState<CleanlinessTemplate[]>([]);
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [attendance, setAttendance] = useState<AttendanceSummaryRecord[]>([]);
  const [hasLiveAttendance, setHasLiveAttendance] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.allSettled([
      api.get(`/inspections?page_size=100&date_from=${selectedDate}&date_to=${selectedDate}`),
      api.get("/inspection-templates?page_size=100&frequency=daily&is_active=true"),
      api.get(`/reports/site?page_size=100&report_date=${selectedDate}`),
      api.get("/issues?page_size=100"),
      api.get("/sites?page_size=100"),
    ]).then(async ([inspectionResult, templateResult, reportResult, issueResult, siteResult]) => {
      if (!active) return;
      const sites = siteResult.status === "fulfilled" ? asPaginated(siteResult.value).results as Site[] : [];
      const dailySheets = await Promise.allSettled(sites.map((site) => api.get<AttendanceSummaryRecord[]>(`/attendance/daily?site_id=${site.id}&date=${selectedDate}`)));
      if (!active) return;
      setInspections(inspectionResult.status === "fulfilled" ? asPaginated(inspectionResult.value).results as Inspection[] : []);
      setTemplates(templateResult.status === "fulfilled" ? asPaginated(templateResult.value).results as CleanlinessTemplate[] : []);
      setReports(reportResult.status === "fulfilled" ? asPaginated(reportResult.value).results as DailyReport[] : []);
      const dailyIssues = issueResult.status === "fulfilled" ? asPaginated(issueResult.value).results as Issue[] : [];
      setIssues(dailyIssues.filter((issue) => String(issue.created_at || "").slice(0, 10) === selectedDate));
      const readableSheets = dailySheets.filter((result): result is PromiseFulfilledResult<AttendanceSummaryRecord[]> => result.status === "fulfilled");
      setAttendance(readableSheets.flatMap((result) => result.value));
      setHasLiveAttendance(sites.length > 0 && readableSheets.length === sites.length);
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedDate]);

  const days = useMemo(() => { const start = new Date(month.getFullYear(), month.getMonth(), 1); const offset = (start.getDay() + 6) % 7; const cells = Array.from({ length: offset }, () => null as Date | null); const dayCount = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate(); for (let day = 1; day <= dayCount; day += 1) cells.push(new Date(month.getFullYear(), month.getMonth(), day)); return cells; }, [month]);
  const dailyTemplates = useMemo(() => preferredCleanlinessTemplates(templates), [templates]);
  const weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const selectedDisplay = calendarDate(selectedDate).toLocaleDateString(language === "sw" ? "sw-TZ" : "en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const liveAttendance = useMemo(() => aggregateDailyAttendance(attendance), [attendance]);
  const totalAttendance = hasLiveAttendance ? liveAttendance.total : reports.reduce((total, report) => total + count(report.attendance_summary, "total"), 0);
  const totalPresent = hasLiveAttendance ? liveAttendance.present : reports.reduce((total, report) => total + count(report.attendance_summary, "present") + count(report.attendance_summary, "late"), 0);
  const totalTrainees = reports.reduce((total, report) => total + count(report.trainee_summary, "active_today"), 0);
  const totalLowStock = reports.reduce((total, report) => total + count(report.store_summary, "low_stock_items"), 0);
  const areaLabel = (template: CleanlinessTemplate) => { const name = template.area_name || template.template_name.replace("Daily Cleanliness Survey ·", "").trim(); return language === "en" ? englishAreaName(name) : t(name); };

  return <section className="overflow-hidden rounded-2xl border border-[#E7DED4] bg-[#FFFDFC] shadow-[0_12px_30px_rgba(44,41,35,.06)]"><div className="flex flex-col gap-3 border-b border-[#EEE7E0] bg-[linear-gradient(135deg,#FFF7F3,#F5FBF8)] p-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="ledger-label text-[#C45232]">{t("Daily survey calendar")}</p><h3 className="mt-0.5 font-serif text-xl text-[#263F42]">{t("Choose a day to review site surveys")}</h3></div><div className="flex items-center gap-1 rounded-full border border-[#E6DCD3] bg-white p-0.5 shadow-sm"><Button variant="ghost" size="icon" className="h-8 w-8" aria-label={t("Previous month")} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft size={16} /></Button><span className="min-w-32 px-1 text-center text-xs font-bold text-[#375356]">{monthTitle(month, language)}</span><Button variant="ghost" size="icon" className="h-8 w-8" aria-label={t("Next month")} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight size={16} /></Button></div></div><div className="p-4"><div className="rounded-xl border border-[#ECE4DC] bg-white p-2.5"><div className="grid grid-cols-7 gap-1 text-center text-[10px] font-bold uppercase tracking-[.08em] text-[#8A817A]">{weekday.map((name) => <span key={name}>{name}</span>)}</div><div className="mt-1.5 grid grid-cols-7 gap-1">{days.map((day, index) => { if (!day) return <span key={`blank-${index}`} />; const value = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`; const isToday = value === today; const selected = value === selectedDate; return <button key={value} onClick={() => setSelectedDate(value)} className={`group relative aspect-square min-h-8 rounded-lg text-xs font-bold transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-[#D86143] ${selected ? "bg-[#D86143] text-white shadow-[0_5px_12px_rgba(216,97,67,.22)]" : "bg-[#FAF7F4] text-[#3B5456] hover:bg-[#FBE9E3]"}`}><span>{day.getDate()}</span>{isToday ? <span className={`absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full ${selected ? "bg-white" : "bg-[#D86143]"}`} /> : null}</button>; })}</div></div></div><div className="border-t border-[#EEE7E0] bg-[#173F43] p-4 text-white"><div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-2.5"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-[#AEE0D3]"><CalendarDays size={17} /></span><div><p className="text-[10px] font-bold uppercase tracking-[.1em] text-[#AEE0D3]">{t("Selected day")}</p><h4 className="mt-0.5 font-serif text-lg capitalize">{selectedDisplay}</h4></div></div><span className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-bold text-[#D7E8E4]">{reports.length} {t("site reports")}</span></div>{loading ? <div className="mt-3 flex items-center gap-2 rounded-lg bg-white/10 p-3 text-sm text-[#D7E8E4]"><Loader2 className="animate-spin" size={15} /> {t("Loading daily surveys")}</div> : <><div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"><Summary icon={CheckCircle2} label={t("Attendance")} value={`${totalPresent} / ${totalAttendance}`} detail={t("present cleaners")} /><Summary icon={UsersRound} label={t("Trainees")} value={String(totalTrainees)} detail={t("active today")} /><Summary icon={PackageCheck} label={t("Low-stock items")} value={String(totalLowStock)} detail={t("need attention")} /><Summary icon={AlertTriangle} label={t("Open issues")} value={String(issues.length)} detail={t("raised this day")} /></div><div className="mt-3 grid gap-3 xl:grid-cols-2"><section className="rounded-xl bg-white/[.08] p-3"><div className="flex items-center gap-2"><ClipboardList size={15} className="text-[#AEE0D3]" /><h5 className="text-sm font-semibold">{t("Daily cleanliness")}</h5><span className="ml-auto text-[11px] text-[#C8DEDA]">{dailyTemplates.length}</span></div>{dailyTemplates.length ? <div className="mt-2 grid gap-1.5 sm:grid-cols-2">{dailyTemplates.map((template) => { const inspection = inspections.find((row) => row.template_id === template.id); return <div key={template.id} className="flex min-w-0 items-center justify-between gap-2 rounded-lg bg-white/[.08] px-2.5 py-2"><div className="min-w-0"><p className="truncate text-xs font-semibold text-white">{areaLabel(template)}</p><p className="mt-0.5 text-[10px] text-[#C8DEDA]">{inspection ? `${inspection.results?.length || 0} ${t("questions saved")}` : t("Not opened")}</p></div><StatusBadge status={inspection?.status || "not_opened"} /></div>; })}</div> : <p className="mt-2 text-xs leading-5 text-[#C8DEDA]">{t("No daily cleanliness templates configured")}</p>}</section><section className="rounded-xl bg-white/[.08] p-3"><div className="flex items-center gap-2"><AlertTriangle size={15} className="text-[#F3C2A7]" /><h5 className="text-sm font-semibold">{t("Issues & jobs")}</h5></div>{issues.length ? <div className="mt-2 space-y-1.5">{issues.slice(0, 4).map((issue) => <div key={issue.id} className="flex items-center justify-between gap-2 rounded-lg bg-white/[.08] px-2.5 py-2"><div className="min-w-0"><p className="truncate text-xs font-semibold">{issue.title || t("Operational issue")}</p><p className="mt-0.5 truncate text-[10px] text-[#C8DEDA]">{issue.site_name || t("Assigned site")}</p></div><StatusBadge status={issue.status || issue.priority || "open"} /></div>)}</div> : <p className="mt-2 text-xs leading-5 text-[#C8DEDA]">{t("No issues were raised on this day.")}</p>}</section></div></>}</div></section>;
}

function Summary({ icon: Icon, label, value, detail }: { icon: typeof CheckCircle2; label: string; value: string; detail: string }) { return <div className="rounded-xl bg-white/[.09] p-3"><div className="flex items-center gap-1.5 text-[#AEE0D3]"><Icon size={14} /><p className="text-[10px] font-bold uppercase tracking-[.07em]">{label}</p></div><p className="mt-1.5 font-serif text-2xl text-white">{value}</p><p className="mt-0.5 text-[10px] text-[#C8DEDA]">{detail}</p></div>; }
