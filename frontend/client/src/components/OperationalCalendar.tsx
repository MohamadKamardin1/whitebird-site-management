import { useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, ClipboardList, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/WorkspacePrimitives";
import { api, asPaginated } from "@/lib/api";
import { useLanguage } from "@/contexts/LanguageContext";

type Inspection = {
  id: number;
  inspection_date: string;
  area_name?: string;
  template_name?: string;
  status?: string;
  overall_status?: string;
  results?: Array<{ id: number; item_label?: string; value_text?: string; passed?: boolean | null }>;
};

const iso = (value: Date) => value.toISOString().slice(0, 10);
const monthTitle = (value: Date, language: string) => value.toLocaleDateString(language === "sw" ? "sw-TZ" : "en-GB", { month: "long", year: "numeric" });

export function OperationalCalendar() {
  const { t, language } = useLanguage();
  const today = useMemo(() => new Date(), []);
  const [month, setMonth] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [selectedDate, setSelectedDate] = useState(iso(today));
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.get(`/inspections?page_size=100&date_from=${selectedDate}&date_to=${selectedDate}`)
      .then((response) => { if (active) setInspections(asPaginated(response).results as Inspection[]); })
      .catch(() => { if (active) setInspections([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedDate]);

  const days = useMemo(() => {
    const start = new Date(month.getFullYear(), month.getMonth(), 1);
    const offset = (start.getDay() + 6) % 7;
    const cells = Array.from({ length: offset }, () => null as Date | null);
    const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    for (let day = 1; day <= count; day += 1) cells.push(new Date(month.getFullYear(), month.getMonth(), day));
    return cells;
  }, [month]);

  const weekday = language === "sw" ? ["Jtt", "Jnn", "Jtt", "Jtn", "Alh", "Iju", "Jmo"] : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const selectedDisplay = new Date(`${selectedDate}T12:00:00`).toLocaleDateString(language === "sw" ? "sw-TZ" : "en-GB", { weekday: "long", day: "numeric", month: "long" });

  return <section className="overflow-hidden rounded-[28px] border border-[#E7DED4] bg-[#FFFDFC] shadow-[0_18px_44px_rgba(44,41,35,.07)]">
    <div className="flex flex-col gap-4 border-b border-[#EEE7E0] bg-[linear-gradient(135deg,#FFF7F3,#F5FBF8)] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
      <div><p className="ledger-label text-[#C45232]">{t("Daily survey calendar")}</p><h3 className="mt-1 font-serif text-2xl text-[#263F42]">{t("Choose a day to review site surveys")}</h3></div>
      <div className="flex items-center gap-2 rounded-full border border-[#E6DCD3] bg-white p-1 shadow-sm">
        <Button variant="ghost" size="icon" aria-label={t("Previous month")} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft size={17} /></Button>
        <span className="min-w-36 px-2 text-center text-sm font-bold text-[#375356]">{monthTitle(month, language)}</span>
        <Button variant="ghost" size="icon" aria-label={t("Next month")} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight size={17} /></Button>
      </div>
    </div>
    <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(300px,.9fr)] lg:p-6">
      <div className="rounded-2xl border border-[#ECE4DC] bg-white p-3 sm:p-4">
        <div className="grid grid-cols-7 gap-1 text-center text-[11px] font-bold uppercase tracking-[.08em] text-[#8A817A]">{weekday.map((name) => <span key={name}>{name}</span>)}</div>
        <div className="mt-2 grid grid-cols-7 gap-1.5">{days.map((day, index) => {
          if (!day) return <span key={`blank-${index}`} />;
          const value = iso(day); const isToday = value === iso(today); const selected = value === selectedDate;
          return <button key={value} onClick={() => setSelectedDate(value)} className={`group relative aspect-square min-h-10 rounded-xl text-sm font-bold transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-[#D86143] ${selected ? "bg-[#D86143] text-white shadow-[0_8px_18px_rgba(216,97,67,.28)]" : "bg-[#FAF7F4] text-[#3B5456] hover:bg-[#FBE9E3]"}`}><span>{day.getDate()}</span>{isToday && <span className={`absolute bottom-1 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full ${selected ? "bg-white" : "bg-[#D86143]"}`} />}</button>;
        })}</div>
      </div>
      <div className="min-w-0 rounded-2xl bg-[#173F43] p-5 text-white shadow-[0_16px_32px_rgba(23,63,67,.16)]">
        <div className="flex items-start gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-[#AEE0D3]"><CalendarDays size={20} /></span><div><p className="text-xs font-bold uppercase tracking-[.1em] text-[#AEE0D3]">{t("Selected day")}</p><h4 className="mt-1 font-serif text-xl capitalize">{selectedDisplay}</h4></div></div>
        <div className="mt-5 max-h-[315px] space-y-2 overflow-y-auto pr-1">{loading ? <div className="flex items-center gap-2 rounded-xl bg-white/10 p-4 text-sm text-[#D7E8E4]"><Loader2 className="animate-spin" size={16} /> {t("Loading daily surveys")}</div> : inspections.length ? inspections.map((inspection) => <div key={inspection.id} className="rounded-xl bg-white/[.09] p-3 transition-colors hover:bg-white/[.14]"><div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-bold">{inspection.area_name || t("Operational area")}</p><p className="mt-1 truncate text-xs text-[#C8DEDA]">{inspection.template_name || t("Daily survey")}</p></div><StatusBadge status={inspection.status || "draft"} /></div><p className="mt-2 text-xs text-[#B3D1CB]">{inspection.results?.length || 0} {t("answers recorded")}</p></div>) : <div className="rounded-xl border border-dashed border-white/25 p-4"><ClipboardList size={19} className="text-[#AEE0D3]" /><p className="mt-2 text-sm font-semibold">{t("No survey is open for this day")}</p><p className="mt-1 text-xs leading-5 text-[#C8DEDA]">{t("Choose another day or open a daily worksheet to begin.")}</p></div>}</div>
      </div>
    </div>
  </section>;
}
