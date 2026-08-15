/** Coastal Ledger attendance workspace: authenticated site scope plus simple daily attendance marking. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, Check, CheckCircle2, ClipboardCheck, Clock3, Loader2, Save, Send, Undo2, UserCheck, UserX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AppShell } from "@/components/AppShell";
import { ApiErrorPanel, AttentionNotice, EmptyPanel, LoadingPanel, StatusBadge, WorkflowNotice, WorkspaceHeader, formatDateValue, formatDisplayValue, formatTimeValue } from "@/components/WorkspacePrimitives";
import { api, asPaginated, readableApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface SiteOption { id: number; name?: string; site_name?: string; work_mode?: string; }
interface AttendanceRecord { id: number; cleaner_id: number; cleaner_name?: string; cleaner?: unknown; site_id: number; shift_name?: string | null; attendance_date: string; status: string; check_in_time?: string | null; check_out_time?: string | null; notes?: string; review_status?: string; is_editable?: boolean; return_reason?: string; }
interface Draft { status: string; checkIn: string; checkOut: string; notes: string; saving?: boolean; saved?: boolean; error?: string; }

const STATUS_OPTIONS = ["present", "late", "absent", "sick", "leave", "permission", "off"];
function nowTime() { return new Date().toTimeString().slice(0, 5); }
function siteLabel(site: SiteOption) { return site.name || site.site_name || `Site ${site.id}`; }

export default function AttendancePage() {
  const { user } = useAuth();
  const today = new Date().toISOString().slice(0, 10);
  const [sites, setSites] = useState<SiteOption[]>([]);
  const [siteId, setSiteId] = useState("");
  const [date, setDate] = useState(today);
  const [records, setRecords] = useState<AttendanceRecord[] | null>(null);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [loadingSites, setLoadingSites] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadSites = useCallback(async () => {
    setLoadingSites(true); setError(null);
    try {
      const response = asPaginated(await api.get("/sites?page_size=100"));
      const visible = response.results as unknown as SiteOption[];
      setSites(visible);
      setSiteId((current) => current || (visible.length === 1 ? String(visible[0].id) : ""));
    } catch (caught) { setError(caught); }
    finally { setLoadingSites(false); }
  }, []);
  useEffect(() => { void loadSites(); }, [loadSites]);

  const loadSheet = useCallback(async () => {
    if (!siteId) return;
    setLoading(true); setError(null); setMessage(null);
    try {
      const result = await api.get<AttendanceRecord[]>(`/attendance/daily?site_id=${encodeURIComponent(siteId)}&date=${encodeURIComponent(date)}`);
      const rows = (Array.isArray(result) ? result : (asPaginated(result).results as unknown)) as AttendanceRecord[];
      setRecords(rows);
      setDrafts(Object.fromEntries(rows.map((record) => [record.id, { status: record.status === "scheduled" ? "present" : record.status, checkIn: formatTimeValue(record.check_in_time), checkOut: formatTimeValue(record.check_out_time), notes: record.notes || "", saved: false }])));
    } catch (caught) { setError(caught); }
    finally { setLoading(false); }
  }, [date, siteId]);

  const updateDraft = (recordId: number, patch: Partial<Draft>) => setDrafts((current) => ({ ...current, [recordId]: { ...current[recordId], ...patch, saved: false, error: undefined } }));
  const markQuick = (record: AttendanceRecord, status: string) => updateDraft(record.id, { status, checkIn: status === "present" || status === "late" ? (drafts[record.id]?.checkIn || nowTime()) : "", checkOut: drafts[record.id]?.checkOut || "" });

  async function saveRecord(record: AttendanceRecord) {
    const draft = drafts[record.id];
    if (!draft || record.is_editable === false) return;
    updateDraft(record.id, { saving: true });
    try {
      const updated = await api.put<AttendanceRecord>(`/attendance/${record.id}`, { status: draft.status, check_in_time: draft.checkIn || null, check_out_time: draft.checkOut || null, notes: draft.notes });
      setRecords((current) => current?.map((row) => row.id === record.id ? { ...row, ...updated } : row) || current);
      updateDraft(record.id, { saving: false, saved: true });
    } catch (caught) { updateDraft(record.id, { saving: false, error: readableApiError(caught).message }); }
  }

  async function submitDay() {
    if (!siteId || !records?.length) return;
    setSubmitting(true); setError(null); setMessage(null);
    try { await api.post("/attendance/submit", { site_id: Number(siteId), attendance_date: date }); setMessage("Attendance submitted to the reviewing supervisor."); await loadSheet(); }
    catch (caught) { setError(readableApiError(caught)); }
    finally { setSubmitting(false); }
  }

  const assignedSiteLabel = useMemo(() => sites.find((site) => String(site.id) === siteId)?.name || sites.find((site) => String(site.id) === siteId)?.site_name, [siteId, sites]);

  return <AppShell><WorkspaceHeader eyebrow="Daily completion" title="Attendance that takes seconds to mark." description="White Bird already knows the sites assigned to your account. Choose the date, mark each scheduled cleaner, add sign-in or sign-out times when needed, and submit the completed sheet." actions={<Button className="bg-[#0F7667] text-white hover:bg-[#0B6155]" onClick={() => void submitDay()} disabled={!siteId || !records?.length || submitting}><Send size={16} /> Submit day</Button>} /><div className="grid gap-5 xl:grid-cols-[.68fr_1.32fr]"><aside className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 sm:p-6"><p className="ledger-label text-[#0F7667]">Your assigned scope</p><h3 className="mt-1 font-serif text-2xl text-[#1F4145]">Start with the date.</h3><div className="mt-5 space-y-4"><div className="grid gap-2"><Label htmlFor="attendance_site">Assigned site</Label>{loadingSites ? <div className="flex h-11 items-center gap-2 rounded-md border border-[#D8D1C4] bg-[#FAF8F2] px-3 text-sm text-[#73817B]"><Loader2 className="animate-spin" size={15} /> Loading your assigned sites</div> : sites.length === 0 ? <div className="rounded-xl border border-dashed border-[#D8D1C4] bg-[#FAF8F2] p-3 text-sm text-[#6E7B76]">No site is currently assigned to this account.</div> : <select id="attendance_site" value={siteId} onChange={(event) => { setSiteId(event.target.value); setRecords(null); }} className="h-11 rounded-md border border-[#D8D1C4] bg-white px-3 text-sm text-[#294A4D] outline-none focus:ring-2 focus:ring-[#0F7667]" aria-label="Assigned site">{sites.map((site) => <option key={site.id} value={site.id}>{siteLabel(site)}</option>)}</select>}</div><div className="grid gap-2"><Label htmlFor="attendance_date">Attendance date</Label><Input id="attendance_date" type="date" required value={date} onChange={(event) => setDate(event.target.value)} className="h-11 border-[#D8D1C4] bg-white" /></div><Button type="button" className="mt-2 w-full bg-[#0F7667] text-white hover:bg-[#0B6155]" disabled={!siteId || loading || loadingSites} onClick={() => void loadSheet()}>{loading ? <Loader2 className="animate-spin" size={16} /> : <CalendarDays size={16} />} Load {assignedSiteLabel || "site"} sheet</Button></div><AttentionNotice>Attendance follows <strong>DRAFT → SUBMITTED → REVIEWED → LOCKED</strong>. Returned rows can be corrected; locked rows stay read-only.</AttentionNotice><div className="mt-4 rounded-xl border border-[#E4DED2] bg-[#FAF8F2] p-4"><p className="text-sm font-bold text-[#315156]">Simple marking</p><ol className="mt-2 space-y-2 text-xs leading-5 text-[#687671]"><li><span className="mr-2 font-bold text-[#0F7667]">01</span>Tap Present or Absent.</li><li><span className="mr-2 font-bold text-[#0F7667]">02</span>Add sign-in and sign-out times if required.</li><li><span className="mr-2 font-bold text-[#0F7667]">03</span>Save each row, then submit the day.</li></ol></div></aside><section className="min-w-0">{loading ? <LoadingPanel label="Loading scheduled cleaners" /> : error ? <ApiErrorPanel error={error} onRetry={() => void loadSheet()} /> : message ? <div className="mb-4"><WorkflowNotice>{message}</WorkflowNotice></div> : null}{records ? records.length > 0 ? <div className="space-y-4"><div className="flex items-center justify-between"><div><p className="ledger-label text-[#0F7667]">{formatDateValue(date)} · {assignedSiteLabel || "Assigned site"}</p><h3 className="font-serif text-2xl text-[#1F4145]">Scheduled cleaners for {date}</h3></div><span className="rounded-full bg-[#E5F0EC] px-3 py-1.5 text-xs font-bold text-[#0F7667]">{records.length} cleaners</span></div>{records.map((record) => { const draft = drafts[record.id] || { status: record.status, checkIn: formatTimeValue(record.check_in_time), checkOut: formatTimeValue(record.check_out_time), notes: "" }; const locked = record.is_editable === false || ["submitted", "reviewed", "locked"].includes(record.review_status || ""); return <article key={record.id} className={`rounded-2xl border bg-[#FFFDF8] p-4 shadow-[0_8px_22px_rgba(24,51,48,.035)] ${locked ? "border-[#DDD7CA] opacity-80" : "border-[#D7E4DE]"}`}><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div className="min-w-[210px]"><div className="flex items-center gap-2"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#E5F1ED] text-[#0F7667]"><UserCheck size={17} /></span><div><p className="font-bold text-[#21464A]">{formatDisplayValue(record.cleaner_name || record.cleaner, "Assigned cleaner")}</p><p className="text-xs text-[#71807A]">{record.shift_name ? `${record.shift_name} shift` : "Standard assignment"}</p></div></div><div className="mt-2 flex flex-wrap items-center gap-2"><StatusBadge status={draft.status} />{record.review_status && <StatusBadge status={record.review_status} />}</div></div><div className="grid flex-1 gap-3 sm:grid-cols-[auto_auto_1fr_auto] sm:items-end"><div className="flex gap-2"><Button type="button" size="sm" disabled={locked} onClick={() => markQuick(record, "present")} className={draft.status === "present" ? "bg-[#0F7667] text-white hover:bg-[#0B6155]" : "bg-[#E6F2ED] text-[#0F7667] hover:bg-[#D5EAE2]"}><Check size={15} /> Present</Button><Button type="button" size="sm" disabled={locked} onClick={() => markQuick(record, "absent")} className={draft.status === "absent" ? "bg-[#A13E26] text-white hover:bg-[#87351F]" : "bg-[#FBE4DD] text-[#A13E26] hover:bg-[#F5D4CA]"}><UserX size={15} /> Absent</Button></div><div className="grid gap-1"><Label className="text-[11px] text-[#687671]">Status</Label><select disabled={locked} value={draft.status} onChange={(event) => updateDraft(record.id, { status: event.target.value })} className="h-9 rounded-md border border-[#D8D1C4] bg-white px-2 text-xs text-[#294A4D]"><option value="present">Present</option>{STATUS_OPTIONS.filter((status) => status !== "present").map((status) => <option key={status} value={status}>{formatDisplayValue(status)}</option>)}</select></div><div className="grid gap-1 sm:grid-cols-2"><div><Label className="text-[11px] text-[#687671]"><Clock3 size={12} className="mr-1 inline" />Sign in</Label><Input disabled={locked} type="time" value={draft.checkIn} onChange={(event) => updateDraft(record.id, { checkIn: event.target.value })} className="h-9 border-[#D8D1C4] bg-white text-xs" /></div><div><Label className="text-[11px] text-[#687671]"><Clock3 size={12} className="mr-1 inline" />Sign out</Label><Input disabled={locked} type="time" value={draft.checkOut} onChange={(event) => updateDraft(record.id, { checkOut: event.target.value })} className="h-9 border-[#D8D1C4] bg-white text-xs" /></div></div><Button type="button" size="sm" disabled={locked || draft.saving} onClick={() => void saveRecord(record)} className="bg-[#173F43] text-white hover:bg-[#0D3034]">{draft.saving ? <Loader2 className="animate-spin" size={15} /> : draft.saved ? <CheckCircle2 size={15} /> : <Save size={15} />} {draft.saved ? "Saved" : "Save"}</Button></div></div>{draft.error && <p className="mt-3 rounded-lg bg-[#FBE4DD] px-3 py-2 text-xs text-[#9D3D28]">{draft.error}</p>}{record.return_reason && <p className="mt-3 rounded-lg bg-[#FFF8E8] px-3 py-2 text-xs text-[#805718]">Returned for correction: {record.return_reason}</p>}</article>; })}</div> : <EmptyPanel title="No scheduled cleaners for this date" description="This assigned site has no active scheduled cleaner records for the selected date. Check the assignment and shift setup before continuing." /> : <div className="flex min-h-[430px] flex-col items-center justify-center rounded-2xl border border-dashed border-[#D8D1C4] bg-[#FFFCF6] p-8 text-center"><span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#E5F1ED] text-[#0F7667]"><ClipboardCheck size={26} /></span><h3 className="mt-5 font-serif text-3xl text-[#21464A]">Your daily sheet starts here.</h3><p className="mt-3 max-w-md text-sm leading-6 text-[#6B7974]">{user?.role === "site_supervisor" ? "Your assigned site is selected automatically from your account scope." : "Choose an assigned site and date to load the operational schedule."}</p><span className="mt-6 inline-flex items-center gap-2 text-xs font-bold text-[#56716D]"><CheckCircle2 size={16} className="text-[#0F7667]" />No manual site IDs.</span></div>}<div className="mt-5 flex items-start gap-3 rounded-xl border border-[#D9E6E0] bg-[#F1F8F5] p-4 text-xs leading-5 text-[#477168]"><Undo2 size={17} className="mt-0.5 shrink-0 text-[#0F7667]" />If a submitted day requires correction, the designated reviewer can return it with a reason. White Bird preserves that backend status instead of silently changing locked data.</div></section></div></AppShell>;
}
