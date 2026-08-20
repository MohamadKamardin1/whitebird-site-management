import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Loader2,
  Plus,
  Power,
  Save,
  Sparkles,
  Trash2,
  UserRoundCheck,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { EmptyPanel, LoadingPanel, WorkspaceHeader } from "@/components/WorkspacePrimitives";
import { api, asPaginated, readableApiError } from "@/lib/api";
import { tanzaniaDate } from "@/lib/dates";

type ScopeRole = "zone_supervisor" | "assistant_general_supervisor";
type ShiftSlot = "asubuhi" | "mchana" | "full_day";

type Zone = { id: number; name: string };
type Site = { id: number; name: string; zone_id: number | null; zone_name?: string };
type Timetable = {
  id: number;
  supervisor_id: number;
  supervisor_name: string;
  supervisor_role: ScopeRole;
  zone_id: number;
  zone_name: string;
  site_id: number;
  site_name: string;
  title: string;
  effective_from: string;
  effective_to?: string | null;
  work_days: string[];
  off_days: string[];
  shift_slot: ShiftSlot;
  notes?: string;
  is_active: boolean;
};
type Assignment = {
  id: number;
  assignment_type: ScopeRole | "site_supervisor";
  user_id: number;
  user_name: string;
  user_role: ScopeRole;
  zone_id?: number | null;
  zone_name?: string;
  all_zones: boolean;
  assigned_from: string;
  assigned_to?: string | null;
  is_active: boolean;
};
type Candidate = { id: number; name: string; allZones: boolean; zoneNames: string[]; zoneIds: number[] };

const WEEKDAYS = [
  ["mon", "Monday"],
  ["tue", "Tuesday"],
  ["wed", "Wednesday"],
  ["thu", "Thursday"],
  ["fri", "Friday"],
  ["sat", "Saturday"],
  ["sun", "Sunday"],
] as const;
const DAY_CODES = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const iso = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
const fromIso = (value: string) => new Date(`${value}T12:00:00`);
const dayCode = (value: string) => DAY_CODES[fromIso(value).getDay()];
const isCurrentAssignment = (assignment: Assignment) => assignment.is_active && assignment.assigned_from <= tanzaniaDate() && (!assignment.assigned_to || assignment.assigned_to >= tanzaniaDate());

function roleLabel(role: ScopeRole, t: (value: string) => string) {
  return t(role === "zone_supervisor" ? "Zone supervisor" : "Assistant general supervisor");
}

function shiftLabel(slot: ShiftSlot, t: (value: string) => string) {
  if (slot === "asubuhi") return t("Morning");
  if (slot === "mchana") return t("Afternoon");
  return t("Full day");
}

function localizedDate(value: string, language: "sw" | "en", options: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) {
  return fromIso(value).toLocaleDateString(language === "sw" ? "sw-TZ" : "en-GB", options);
}

function compactDayLabel(date: Date, language: "sw" | "en", t: (value: string) => string) {
  const weekday = WEEKDAYS[(date.getDay() + 6) % 7][1];
  const translated = t(weekday);
  return language === "sw" ? translated.slice(0, 3) : weekday.slice(0, 3);
}

function ToggleDays({
  label,
  selected,
  onChange,
  tone = "teal",
  t,
}: {
  label: string;
  selected: string[];
  onChange: (next: string[]) => void;
  tone?: "teal" | "amber";
  t: (value: string) => string;
}) {
  const selectedClass = tone === "teal" ? "bg-[#0F7667] text-white" : "bg-[#C77828] text-white";
  return (
    <div>
      <p className="text-xs font-extrabold tracking-[.08em] text-[#315B56]">{label}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {WEEKDAYS.map(([code, labelText]) => {
          const active = selected.includes(code);
          return (
            <button
              type="button"
              key={code}
              onClick={() => onChange(active ? selected.filter((item) => item !== code) : [...selected, code])}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-bold transition-colors ${active ? selectedClass : "bg-[#EEF1EC] text-[#566762] hover:bg-[#E0E8E2]"}`}
            >
              {t(labelText)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function WizardStep({ current, index, label }: { current: number; index: number; label: string }) {
  const active = current === index;
  const complete = current > index;
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-extrabold ${active ? "bg-[#0F7667] text-white" : complete ? "bg-[#DCEEE7] text-[#176358]" : "bg-[#E9E8E1] text-[#687874]"}`}>
        {complete ? <Check size={15} /> : index + 1}
      </span>
      <span className={`text-xs font-bold leading-4 ${active ? "text-[#0F7667]" : "text-[#687874]"}`}>{label}</span>
    </div>
  );
}

function TimetableStatus({ active, t }: { active: boolean; t: (value: string) => string }) {
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${active ? "bg-[#DCF2E8] text-[#176358]" : "bg-[#ECE9E3] text-[#6C625A]"}`}>{t(active ? "Active" : "Inactive")}</span>;
}

function AdminTimetableListSection({
  entries,
  loading,
  onRefresh,
  onNew,
  report,
}: {
  entries: Timetable[];
  loading: boolean;
  onRefresh: () => Promise<void>;
  onNew: () => void;
  report: (message: string, isError?: boolean) => void;
}) {
  const { t } = useLanguage();
  const [busyId, setBusyId] = useState<number | null>(null);

  async function toggle(entry: Timetable) {
    setBusyId(entry.id);
    try {
      await api.patch(`/admin/supervisor-timetables/${entry.id}`, { is_active: !entry.is_active });
      await onRefresh();
    } catch (caught) {
      report(readableApiError(caught).message || t("Unable to complete the timetable action."), true);
    } finally {
      setBusyId(null);
    }
  }

  async function remove(entry: Timetable) {
    setBusyId(entry.id);
    try {
      const result = await api.delete<{ retained_as_inactive: boolean }>(`/admin/supervisor-timetables/${entry.id}`);
      report(t(result.retained_as_inactive ? "The timetable was retained as inactive because checklist history depends on it." : "The timetable was deleted."));
      await onRefresh();
    } catch (caught) {
      report(readableApiError(caught).message || t("Unable to complete the timetable action."), true);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="mt-6 rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ledger-label text-[#0F7667]">{t("Manage supervisor timetables")}</p>
          <h2 className="mt-1 font-serif text-2xl text-[#21464A]">{t("All timetables")}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-[#687874]">{t("Review every timetable, including inactive records retained for audit history.")}</p>
        </div>
        <Button className="bg-[#0F7667] text-white" onClick={onNew}><Plus size={16} /> {t("Add timetable")}</Button>
      </div>
      {loading ? <div className="mt-5"><LoadingPanel label={t("Loading timetable data")} /></div> : entries.length === 0 ? <div className="mt-5"><EmptyPanel title={t("No timetables have been created yet.")} description={t("Add timetable")} /></div> : (
        <div className="mt-5 overflow-x-auto rounded-xl border border-[#E7E1D7]">
          <table className="min-w-[1000px] w-full text-left text-sm">
            <thead className="bg-[#0B3540] text-white">
              <tr>
                {["Supervisor", "Scope", "Zone", "Site", "Schedule", "Shift", "Days", "Status", "Actions"].map((label) => <th key={label} className="px-3 py-3 text-xs font-extrabold tracking-[.06em]">{t(label)}</th>)}
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-t border-[#ECE7DE] bg-white align-top">
                  <td className="px-3 py-3 font-semibold text-[#21464A]">{entry.supervisor_name}</td>
                  <td className="px-3 py-3 text-[#536B66]">{roleLabel(entry.supervisor_role, t)}</td>
                  <td className="px-3 py-3 text-[#536B66]">{entry.zone_name}</td>
                  <td className="px-3 py-3 text-[#536B66]">{entry.site_name}</td>
                  <td className="px-3 py-3"><p className="font-semibold text-[#21464A]">{entry.title || "—"}</p><p className="mt-1 text-xs text-[#687874]">{entry.effective_from}{entry.effective_to ? ` — ${entry.effective_to}` : ` · ${t("Ongoing")}`}</p></td>
                  <td className="px-3 py-3 font-semibold text-[#315B56]">{shiftLabel(entry.shift_slot, t)}</td>
                  <td className="px-3 py-3 text-xs text-[#536B66]">{entry.work_days.map((code) => t(WEEKDAYS.find(([key]) => key === code)?.[1] || code)).join(", ")}</td>
                  <td className="px-3 py-3"><TimetableStatus active={entry.is_active} t={t} /></td>
                  <td className="px-3 py-3"><div className="flex items-center gap-2"><Button size="sm" variant="outline" className="bg-white" disabled={busyId === entry.id} onClick={() => void toggle(entry)}><Power size={14} /> {t(entry.is_active ? "Deactivate" : "Activate")}</Button><Button size="icon" variant="outline" className="bg-white text-[#9D3D28]" aria-label={t("Delete")} disabled={busyId === entry.id} onClick={() => void remove(entry)}>{busyId === entry.id ? <Loader2 className="animate-spin" size={15} /> : <Trash2 size={15} />}</Button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function AdminTimetableWizardPage() {
  const { t, language } = useLanguage();
  const [step, setStep] = useState(0);
  const [zones, setZones] = useState<Zone[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [entries, setEntries] = useState<Timetable[]>([]);
  const [selectedSupervisorIds, setSelectedSupervisorIds] = useState<number[]>([]);
  const [selectedZones, setSelectedZones] = useState<number[]>([]);
  const [selectedSites, setSelectedSites] = useState<number[]>([]);
  const [draft, setDraft] = useState<{ scope_role: ScopeRole; title: string; effective_from: string; effective_to: string; work_days: string[]; off_days: string[]; shift_slot: ShiftSlot; notes: string }>({ scope_role: "zone_supervisor", title: "", effective_from: tanzaniaDate(), effective_to: "", work_days: ["mon", "tue", "wed", "thu", "fri", "sat"], off_days: ["sun"], shift_slot: "asubuhi", notes: "" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [zoneRows, siteRows, assignmentRows, timetableRows] = await Promise.all([
        api.get("/zones?page_size=100"),
        api.get("/sites?page_size=100"),
        api.get<Assignment[]>("/admin/supervisor-assignments"),
        api.get<Timetable[]>("/admin/supervisor-timetables"),
      ]);
      setZones(asPaginated(zoneRows).results as Zone[]);
      setSites(asPaginated(siteRows).results as Site[]);
      setAssignments(assignmentRows);
      setEntries(timetableRows);
    } catch (caught) {
      setError(readableApiError(caught).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const candidates = useMemo(() => {
    const current = assignments.filter((row) => row.assignment_type === draft.scope_role && row.user_role === draft.scope_role && isCurrentAssignment(row));
    const grouped = new Map<number, Candidate>();
    current.forEach((row) => {
      const candidate = grouped.get(row.user_id) || { id: row.user_id, name: row.user_name, allZones: false, zoneNames: [], zoneIds: [] };
      candidate.allZones = candidate.allZones || row.all_zones;
      if (row.zone_id && !candidate.zoneIds.includes(row.zone_id)) candidate.zoneIds.push(row.zone_id);
      if (row.zone_name && !candidate.zoneNames.includes(row.zone_name)) candidate.zoneNames.push(row.zone_name);
      grouped.set(row.user_id, candidate);
    });
    return Array.from(grouped.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [assignments, draft.scope_role]);
  const selectedCandidates = useMemo(() => candidates.filter((candidate) => selectedSupervisorIds.includes(candidate.id)), [candidates, selectedSupervisorIds]);
  const eligibleSites = useMemo(() => sites.filter((site) => site.zone_id !== null && selectedZones.includes(site.zone_id)), [sites, selectedZones]);
  const groupedSites = useMemo(() => selectedZones.map((zoneId) => ({ zone: zones.find((zone) => zone.id === zoneId), sites: eligibleSites.filter((site) => site.zone_id === zoneId) })), [eligibleSites, selectedZones, zones]);

  useEffect(() => { setSelectedSupervisorIds((current) => current.filter((id) => candidates.some((candidate) => candidate.id === id))); }, [candidates]);
  useEffect(() => { setSelectedSites((current) => current.filter((id) => eligibleSites.some((site) => site.id === id))); }, [eligibleSites]);

  const toggle = (id: number, selected: number[], setter: (next: number[]) => void) => setter(selected.includes(id) ? selected.filter((value) => value !== id) : [...selected, id]);
  const canContinue = [true, selectedSupervisorIds.length > 0, selectedZones.length > 0 && (draft.scope_role === "assistant_general_supervisor" || selectedSites.length > 0), Boolean(draft.title.trim() && draft.effective_from && draft.work_days.length), true][step];

  function changeScope(scope_role: ScopeRole) {
    setDraft((current) => ({ ...current, scope_role }));
    setSelectedSupervisorIds([]);
    setSelectedZones([]);
    setSelectedSites([]);
  }

  function newTimetable() {
    setStep(0);
    setError("");
    setSuccess("");
    setSelectedSupervisorIds([]);
    setSelectedZones([]);
    setSelectedSites([]);
    setDraft({ scope_role: "zone_supervisor", title: "", effective_from: tanzaniaDate(), effective_to: "", work_days: ["mon", "tue", "wed", "thu", "fri", "sat"], off_days: ["sun"], shift_slot: "asubuhi", notes: "" });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function save() {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await api.post<{ created_count: number }>("/admin/supervisor-timetables/batch", {
        ...draft,
        supervisor_ids: selectedSupervisorIds,
        zone_ids: selectedZones,
        site_ids: selectedSites,
        effective_to: draft.effective_to || null,
      });
      setSuccess(t("Timetable saved. {count} personal schedule entries were created.").replace("{count}", String(result.created_count)));
      await load();
      setStep(4);
    } catch (caught) {
      setError(readableApiError(caught).message);
    } finally {
      setBusy(false);
    }
  }

  const stepLabels = [t("Choose scope"), t("Choose supervisors"), t("Choose zones and sites"), t("Schedule details"), t("Review")];
  return (
    <AppShell>
      <WorkspaceHeader
        eyebrow={t("System administrator")}
        title={t("Create supervisor timetable")}
        description={t("Create, review, activate, deactivate, or safely remove personal, auditable supervisor schedules.")}
        actions={<Button variant="outline" className="bg-white" onClick={() => void load()}><CalendarDays size={16} /> {t("Refresh")}</Button>}
      />
      <div className="mt-5 grid gap-2 rounded-2xl border border-[#D9E5DF] bg-[#F6FAF7] p-3 sm:grid-cols-2 lg:grid-cols-5">
        {stepLabels.map((label, index) => <WizardStep key={label} current={step} index={index} label={label} />)}
      </div>
      {error ? <p className="mt-4 rounded-xl bg-[#FBE4DD] p-3 text-sm text-[#9D3D28]">{error}</p> : null}
      {success ? <p className="mt-4 rounded-xl bg-[#DCF2E8] p-3 text-sm font-semibold text-[#176358]">{success}</p> : null}
      {loading ? <div className="mt-5"><LoadingPanel label={t("Loading timetable data")} /></div> : <section className="mt-5 rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-4 sm:p-6">
        <div className="min-h-[310px]">
          {step === 0 ? <div className="max-w-3xl"><p className="ledger-label text-[#0F7667]">{t("Step")} 1</p><h2 className="mt-1 font-serif text-3xl text-[#21464A]">{t("Choose scope")}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t("Select whether this timetable is for a Zone Supervisor who visits sites or an Assistant General Supervisor who visits zones.")}</p><div className="mt-6 grid gap-3 md:grid-cols-2">{(["zone_supervisor", "assistant_general_supervisor"] as ScopeRole[]).map((scope) => <button type="button" key={scope} onClick={() => changeScope(scope)} className={`rounded-xl border p-4 text-left transition-colors ${draft.scope_role === scope ? "border-[#0F7667] bg-[#EDF8F4]" : "border-[#E6E0D6] bg-white hover:bg-[#FAF8F2]"}`}><UserRoundCheck className={draft.scope_role === scope ? "text-[#0F7667]" : "text-[#6E8079]"} size={20} /><p className="mt-3 font-serif text-xl text-[#21464A]">{roleLabel(scope, t)}</p><p className="mt-1 text-sm leading-5 text-[#687874]">{scope === "zone_supervisor" ? t("Choose the specific sites visited by the Zone Supervisor.") : t("Optionally select sites to focus an Assistant General Supervisor’s zone visit. Leave all sites unselected to include every active site in the chosen zones.")}</p></button>)}</div></div> : null}
          {step === 1 ? <div><p className="ledger-label text-[#0F7667]">{t("Step")} 2</p><h2 className="mt-1 font-serif text-3xl text-[#21464A]">{t("Select specific supervisors")}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t("Only active assignments are shown. You may choose more than one supervisor when their assignments match the planned visits.")}</p>{candidates.length === 0 ? <div className="mt-5"><EmptyPanel title={t("No active supervisor assignments are available for this scope.")} description={t("Choose scope")} /></div> : <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{candidates.map((candidate) => <label key={candidate.id} className={`flex cursor-pointer gap-3 rounded-xl border p-3 transition-colors ${selectedSupervisorIds.includes(candidate.id) ? "border-[#0F7667] bg-[#EDF8F4]" : "border-[#E6E0D6] bg-white hover:bg-[#FAF8F2]"}`}><input type="checkbox" checked={selectedSupervisorIds.includes(candidate.id)} onChange={() => toggle(candidate.id, selectedSupervisorIds, setSelectedSupervisorIds)} className="mt-1 h-4 w-4 accent-[#0F7667]" /><span><span className="block font-semibold text-[#21464A]">{candidate.name}</span><span className="mt-1 block text-xs leading-5 text-[#687874]">{t("Assigned zones")}: {candidate.allZones ? t("All zones") : candidate.zoneNames.join(", ") || "—"}</span></span></label>)}</div>}</div> : null}
          {step === 2 ? <div><p className="ledger-label text-[#0F7667]">{t("Step")} 3</p><h2 className="mt-1 font-serif text-3xl text-[#21464A]">{t("Choose zones and sites")}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t("Select the zones this timetable covers. Supervisors receive entries only for sites inside their current assignment scope.")}</p><div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{zones.map((zone) => <label key={zone.id} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition-colors ${selectedZones.includes(zone.id) ? "border-[#0F7667] bg-[#EDF8F4]" : "border-[#E6E0D6] bg-white hover:bg-[#FAF8F2]"}`}><input type="checkbox" checked={selectedZones.includes(zone.id)} onChange={() => toggle(zone.id, selectedZones, setSelectedZones)} className="h-4 w-4 accent-[#0F7667]" /><span className="font-semibold text-[#21464A]">{zone.name}</span></label>)}</div>{selectedZones.length ? <div className="mt-6"><h3 className="font-serif text-xl text-[#21464A]">{t("Select sites")}</h3><p className="mt-1 text-sm leading-6 text-[#687874]">{draft.scope_role === "zone_supervisor" ? t("Choose the specific sites visited by the Zone Supervisor.") : t("Optionally select sites to focus an Assistant General Supervisor’s zone visit. Leave all sites unselected to include every active site in the chosen zones.")}</p><div className="mt-4 space-y-4">{groupedSites.map(({ zone, sites: zoneSites }) => <div key={zone?.id} className="rounded-xl border border-[#E4E0D6] bg-white p-4"><p className="font-bold text-[#0F7667]">{zone?.name}</p>{zoneSites.length ? <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{zoneSites.map((site) => <label key={site.id} className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 ${selectedSites.includes(site.id) ? "border-[#0F7667] bg-[#EDF8F4]" : "border-[#E9E4DA]"}`}><input type="checkbox" checked={selectedSites.includes(site.id)} onChange={() => toggle(site.id, selectedSites, setSelectedSites)} className="h-4 w-4 accent-[#0F7667]" /><span className="text-sm font-semibold text-[#21464A]">{site.name}</span></label>)}</div> : <p className="mt-3 text-sm text-[#8A7065]">{t("No active sites are configured in this zone.")}</p>}</div>)}</div></div> : <div className="mt-5"><EmptyPanel title={t("Select operational zones")} description={t("Choose zones and sites")} /></div>}</div> : null}
          {step === 3 ? <div className="max-w-3xl"><p className="ledger-label text-[#0F7667]">{t("Step")} 4</p><h2 className="mt-1 font-serif text-3xl text-[#21464A]">{t("Schedule details")}</h2><div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="sm:col-span-2"><span className="text-xs font-bold text-[#315B56]">{t("Schedule title")}</span><Input className="mt-1 bg-white" value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} placeholder={t("For example: Week one site visits")} /></label><label><span className="text-xs font-bold text-[#315B56]">{t("Effective from")}</span><Input className="mt-1 bg-white" type="date" value={draft.effective_from} onChange={(event) => setDraft({ ...draft, effective_from: event.target.value })} /></label><label><span className="text-xs font-bold text-[#315B56]">{t("Effective to (optional)")}</span><Input className="mt-1 bg-white" type="date" value={draft.effective_to} onChange={(event) => setDraft({ ...draft, effective_to: event.target.value })} /></label></div><div className="mt-5"><ToggleDays label={t("Work days")} selected={draft.work_days} onChange={(work_days) => setDraft({ ...draft, work_days })} t={t} /><div className="mt-4"><ToggleDays label={t("Off days")} selected={draft.off_days} onChange={(off_days) => setDraft({ ...draft, off_days })} tone="amber" t={t} /></div></div><label className="mt-5 block"><span className="text-xs font-bold text-[#315B56]">{t("Shift")}</span><select value={draft.shift_slot} onChange={(event) => setDraft({ ...draft, shift_slot: event.target.value as ShiftSlot })} className="mt-1 h-10 w-full rounded-md border border-[#D8D2C5] bg-white px-3 text-sm"><option value="asubuhi">{shiftLabel("asubuhi", t)}</option><option value="mchana">{shiftLabel("mchana", t)}</option><option value="full_day">{shiftLabel("full_day", t)}</option></select></label><label className="mt-4 block"><span className="text-xs font-bold text-[#315B56]">{t("Notes")}</span><Textarea className="mt-1 min-h-24 bg-white" value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} placeholder={t("Add useful instructions for the supervisor.")} /></label></div> : null}
          {step === 4 ? <div><p className="ledger-label text-[#0F7667]">{t("Step")} 5</p><h2 className="mt-1 font-serif text-3xl text-[#21464A]">{t("Review before saving")}</h2><div className="mt-5 grid gap-4 lg:grid-cols-2"><div className="rounded-xl border border-[#DFE8E2] bg-[#F4FAF7] p-4"><p className="text-xs font-bold tracking-[.08em] text-[#0F7667]">{t("Schedule")}</p><dl className="mt-3 space-y-2 text-sm"><div className="flex justify-between gap-4"><dt className="text-[#687874]">{t("Supervisor scope")}</dt><dd className="font-bold text-right text-[#21464A]">{roleLabel(draft.scope_role, t)}</dd></div><div className="flex justify-between gap-4"><dt className="text-[#687874]">{t("Schedule title")}</dt><dd className="font-bold text-right text-[#21464A]">{draft.title || "—"}</dd></div><div className="flex justify-between gap-4"><dt className="text-[#687874]">{t("Shift")}</dt><dd className="font-bold text-right text-[#21464A]">{shiftLabel(draft.shift_slot, t)}</dd></div><div className="flex justify-between gap-4"><dt className="text-[#687874]">{t("Effective from")}</dt><dd className="font-bold text-right text-[#21464A]">{localizedDate(draft.effective_from, language)}</dd></div></dl></div><div className="rounded-xl border border-[#E5DFD4] bg-white p-4"><p className="text-xs font-bold tracking-[.08em] text-[#315B56]">{t("Selected supervisors")}</p><p className="mt-2 text-sm font-semibold leading-6 text-[#21464A]">{selectedCandidates.map((candidate) => candidate.name).join(", ") || "—"}</p><p className="mt-4 text-xs font-bold tracking-[.08em] text-[#315B56]">{t("Selected zones")}</p><p className="mt-2 text-sm font-semibold leading-6 text-[#21464A]">{zones.filter((zone) => selectedZones.includes(zone.id)).map((zone) => zone.name).join(", ") || "—"}</p><p className="mt-4 text-xs font-bold tracking-[.08em] text-[#315B56]">{t("Selected sites")}</p><p className="mt-2 text-sm font-semibold leading-6 text-[#21464A]">{selectedSites.length ? sites.filter((site) => selectedSites.includes(site.id)).map((site) => site.name).join(", ") : draft.scope_role === "assistant_general_supervisor" ? t("All active sites in selected zones") : "—"}</p></div></div></div> : null}
        </div>
        <div className="mt-6 flex flex-wrap justify-between gap-3 border-t border-[#EAE3D8] pt-4"><Button variant="outline" className="bg-white" disabled={step === 0 || busy} onClick={() => setStep(step - 1)}>{t("Back")}</Button>{step < 4 ? <Button disabled={!canContinue || busy} className="bg-[#0F7667] text-white" onClick={() => setStep(step + 1)}>{t("Continue")} <ChevronRight size={16} /></Button> : <Button disabled={busy || !canContinue} className="bg-[#0F7667] text-white" onClick={() => void save()}>{busy ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />} {t("Save timetable")}</Button>}</div>
      </section>}
      <AdminTimetableListSection entries={entries} loading={loading} onRefresh={load} onNew={newTimetable} report={(message, isError) => { setSuccess(isError ? "" : message); setError(isError ? message : ""); }} />
    </AppShell>
  );
}

function spanFor(anchor: string, view: "day" | "week" | "month") {
  const first = fromIso(anchor);
  if (view === "day") return [first];
  if (view === "week") {
    const monday = new Date(first);
    monday.setDate(first.getDate() - ((first.getDay() + 6) % 7));
    return Array.from({ length: 7 }, (_, index) => { const next = new Date(monday); next.setDate(monday.getDate() + index); return next; });
  }
  const month = new Date(first.getFullYear(), first.getMonth(), 1, 12);
  return Array.from({ length: new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate() }, (_, index) => new Date(first.getFullYear(), first.getMonth(), index + 1, 12));
}

function isActiveOn(entry: Timetable, value: string) {
  return entry.is_active && entry.effective_from <= value && (!entry.effective_to || entry.effective_to >= value) && entry.work_days.includes(dayCode(value)) && !entry.off_days.includes(dayCode(value));
}

function SupervisorScheduler({ scopeRole }: { scopeRole: ScopeRole }) {
  const { t, language } = useLanguage();
  const [view, setView] = useState<"day" | "week" | "month">("week");
  const [anchor, setAnchor] = useState(tanzaniaDate());
  const [entries, setEntries] = useState<Timetable[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const days = useMemo(() => spanFor(anchor, view), [anchor, view]);
  const startDate = iso(days[0]);
  const endDate = iso(days[days.length - 1]);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await api.get<Timetable[]>(`/timetables?scope_role=${scopeRole}&start_date=${startDate}&end_date=${endDate}`);
      setEntries(rows);
    } catch (caught) {
      setError(readableApiError(caught).message);
    } finally {
      setLoading(false);
    }
  }, [endDate, scopeRole, startDate]);
  useEffect(() => { void load(); }, [load]);
  const resources = useMemo(() => Array.from(new Map(entries.map((entry) => [entry.site_id, { id: entry.site_id, name: entry.site_name, zone: entry.zone_name }])).values()), [entries]);
  const move = (amount: number) => { const next = fromIso(anchor); next.setDate(next.getDate() + (view === "month" ? amount * 30 : view === "week" ? amount * 7 : amount)); setAnchor(iso(next)); };
  const title = scopeRole === "zone_supervisor" ? t("My site visit timetable") : t("My zone visit timetable");
  const headerPeriod = view === "month" ? localizedDate(anchor, language, { month: "long", year: "numeric" }) : `${localizedDate(startDate, language, { day: "numeric", month: "short" })} — ${localizedDate(endDate, language, { day: "numeric", month: "short", year: "numeric" })}`;
  const tone = (slot: ShiftSlot) => slot === "asubuhi" ? "border-[#8DD4C6] bg-[#DFF5EE] text-[#0D665A]" : slot === "mchana" ? "border-[#F2C78E] bg-[#FFF0D7] text-[#925318]" : "border-[#9EC8EC] bg-[#E3F1FF] text-[#225F8B]";

  return (
    <AppShell>
      <WorkspaceHeader eyebrow={roleLabel(scopeRole, t)} title={title} description={t("View only your own approved schedule by day, week, or month.")} actions={<Button variant="outline" className="bg-white" onClick={() => setAnchor(tanzaniaDate())}><Sparkles size={16} /> {t("Today")}</Button>} />
      <section className="mt-5 rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-3 sm:p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><Button size="icon" variant="outline" className="bg-white" onClick={() => move(-1)} aria-label={t("Previous period")}><ChevronLeft size={17} /></Button><div className="min-w-[160px] text-center"><p className="text-sm font-bold text-[#21464A]">{headerPeriod}</p></div><Button size="icon" variant="outline" className="bg-white" onClick={() => move(1)} aria-label={t("Next period")}><ChevronRight size={17} /></Button></div><div className="flex rounded-xl bg-[#E9F0EC] p-1">{(["day", "week", "month"] as const).map((item) => <button key={item} onClick={() => setView(item)} className={`rounded-lg px-3 py-1.5 text-xs font-extrabold transition-colors ${view === item ? "bg-white text-[#0F7667] shadow-sm" : "text-[#65756F]"}`}>{t(item === "day" ? "Day" : item === "week" ? "Week" : "Month")}</button>)}</div></div></section>
      {error ? <p className="mt-4 rounded-xl bg-[#FBE4DD] p-3 text-sm text-[#9D3D28]">{error}</p> : null}
      {loading ? <div className="mt-5"><LoadingPanel label={t("Loading timetable data")} /></div> : resources.length === 0 ? <div className="mt-5"><EmptyPanel title={t("No timetable is scheduled for this period.")} description={t("Your System Administrator can assign a personal timetable for your current zones or sites.")} /></div> : <section className="mt-5 overflow-hidden rounded-2xl border border-[#D7E4DF] bg-white"><div className="overflow-x-auto"><table className="min-w-[760px] w-full border-collapse text-left"><thead><tr className="bg-[#0B3540] text-white"><th className="sticky left-0 z-10 min-w-48 border-r border-white/10 bg-[#0B3540] px-4 py-3 text-xs font-extrabold tracking-[.08em]">{t("Site / zone")}</th>{days.map((date) => <th key={iso(date)} className={`min-w-28 border-l border-white/10 px-3 py-3 text-center text-xs ${iso(date) === tanzaniaDate() ? "bg-[#155260]" : ""}`}><span className="block text-[10px] uppercase text-[#B9D9D1]">{view === "month" ? compactDayLabel(date, language, t) : compactDayLabel(date, language, t)}</span><span className="mt-1 block font-serif text-base">{date.getDate()}</span></th>)}</tr></thead><tbody>{resources.map((resource) => <tr key={resource.id} className="border-t border-[#E5EAE4]"><th className="sticky left-0 z-[1] border-r border-[#E5EAE4] bg-[#FFFEFA] px-4 py-4 align-top"><p className="font-bold text-[#21464A]">{resource.name}</p><p className="mt-1 text-xs font-semibold text-[#0F7667]">{resource.zone}</p></th>{days.map((date) => { const value = iso(date); const events = entries.filter((entry) => entry.site_id === resource.id && isActiveOn(entry, value)); return <td key={value} className={`border-l border-[#EDF0EB] p-2 align-top ${value === tanzaniaDate() ? "bg-[#F1FAF6]" : ""}`}>{events.map((entry) => <Popover key={entry.id}><PopoverTrigger asChild><button className={`mb-1 w-full rounded-lg border px-2 py-1.5 text-left text-[11px] font-extrabold leading-4 ${tone(entry.shift_slot)}`}><span className="block truncate">{entry.title || t("Personal timetable")}</span><span className="mt-0.5 flex items-center gap-1 text-[10px] font-bold opacity-80"><Clock3 size={11} /> {shiftLabel(entry.shift_slot, t)}</span></button></PopoverTrigger><PopoverContent className="w-72 border-[#D9E5DF] p-4" side="top"><p className="font-serif text-lg text-[#21464A]">{entry.title || t("Personal timetable")}</p><p className="mt-1 text-xs font-extrabold uppercase tracking-[.08em] text-[#0F7667]">{entry.zone_name} · {entry.site_name}</p><div className="mt-3 space-y-1.5 text-sm text-[#536B66]"><p><strong>{t("Shift")}:</strong> {shiftLabel(entry.shift_slot, t)}</p><p><strong>{t("Schedule period")}:</strong> {localizedDate(entry.effective_from, language)}{entry.effective_to ? ` — ${localizedDate(entry.effective_to, language)}` : ` · ${t("Ongoing")}`}</p>{entry.notes ? <p className="border-t border-[#E5EAE4] pt-2"><strong>{t("Notes")}:</strong> {entry.notes}</p> : null}</div></PopoverContent></Popover>)}</td>; })}</tr>)}</tbody></table></div><div className="border-t border-[#E5EAE4] bg-[#FBFCF9] px-4 py-3 text-xs text-[#687874]">{t("Click a schedule card to view its details.")} {t("Morning shifts are green, afternoon shifts are gold, and full-day shifts are blue.")}</div></section>}
    </AppShell>
  );
}

export function ZoneSupervisorSchedulerPage() {
  return <SupervisorScheduler scopeRole="zone_supervisor" />;
}

export function AssistantGeneralSupervisorSchedulerPage() {
  return <SupervisorScheduler scopeRole="assistant_general_supervisor" />;
}

export function PersonalSupervisorSchedulerPage() {
  const { user } = useAuth();
  return user?.role === "assistant_general_supervisor" ? <AssistantGeneralSupervisorSchedulerPage /> : <ZoneSupervisorSchedulerPage />;
}
