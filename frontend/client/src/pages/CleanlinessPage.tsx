/** Daily operational cleanliness declaration built on the auditable inspection and issue workflow. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ClipboardCheck, Loader2, Send, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AppShell } from "@/components/AppShell";
import { ApiErrorPanel, AttentionNotice, EmptyPanel, LoadingPanel, StatusBadge, WorkflowNotice, WorkspaceHeader, formatDateValue, formatDisplayValue } from "@/components/WorkspacePrimitives";
import { api, asPaginated, readableApiError } from "@/lib/api";

interface Site { id: number; name?: string; site_name?: string; }
interface Area { id: number; area_name?: string; name?: string; site_id: number; is_active?: boolean; }
interface Cleaner { id: number; full_name?: string; first_name?: string; last_name?: string; status?: string; }
interface TemplateItem { id: number; item_label: string; item_type: string; required?: boolean; help_text?: string; }
interface Template { id: number; template_name: string; description?: string; site_id?: number | null; area_id?: number | null; area_name?: string | null; frequency?: string; is_active?: boolean; items: TemplateItem[]; }
interface Result { id: number; template_item_id: number; item_label: string; value_boolean?: boolean | null; value_text?: string; passed?: boolean | null; notes?: string; }
interface Inspection { id: number; site_id: number; area_id: number; area_name?: string; template_id: number; template_name?: string; inspection_date: string; status: string; results: Result[]; notes?: string; }
interface RowDraft { passed: "yes" | "no" | "pending"; notes: string; cleanerId: string; saving?: boolean; saved?: boolean; error?: string; }

function label(value: { name?: string; site_name?: string; area_name?: string; full_name?: string; first_name?: string; last_name?: string }, fallback: string) {
  return value.name || value.site_name || value.area_name || value.full_name || [value.first_name, value.last_name].filter(Boolean).join(" ") || fallback;
}

export default function CleanlinessPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState("");
  const [date, setDate] = useState(today);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [cleaners, setCleaners] = useState<Cleaner[]>([]);
  const [drafts, setDrafts] = useState<Record<string, RowDraft>>({});
  const [loading, setLoading] = useState(true);
  const [loadingSheet, setLoadingSheet] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadSites = useCallback(async () => {
    try {
      const data = asPaginated(await api.get("/sites?page_size=100"));
      const next = data.results as unknown as Site[];
      setSites(next);
      setSiteId((current) => current || (next.length === 1 ? String(next[0].id) : ""));
    } catch (caught) { setError(caught); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void loadSites(); }, [loadSites]);

  const loadSheet = useCallback(async () => {
    if (!siteId) return;
    setLoadingSheet(true); setError(null); setMessage(null);
    try {
      const [templateResponse, inspectionResponse, cleanerResponse] = await Promise.all([
        api.get(`/inspection-templates?page_size=100&frequency=daily&is_active=true&site_id=${siteId}`),
        api.get(`/inspections?page_size=100&site_id=${siteId}&date_from=${date}&date_to=${date}`),
        api.get(`/cleaners?page_size=100`),
      ]);
      setTemplates(asPaginated(templateResponse).results as unknown as Template[]);
      setInspections(asPaginated(inspectionResponse).results as unknown as Inspection[]);
      setCleaners(asPaginated(cleanerResponse).results as unknown as Cleaner[]);
    } catch (caught) { setError(caught); }
    finally { setLoadingSheet(false); }
  }, [date, siteId]);
  useEffect(() => { if (siteId) void loadSheet(); }, [loadSheet, siteId]);

  const inspectionFor = (template: Template) => inspections.find((row) => row.template_id === template.id && (!template.area_id || row.area_id === template.area_id));
  const siteName = useMemo(() => label(sites.find((site) => String(site.id) === siteId) || {}, "Assigned site"), [siteId, sites]);
  const activeTemplates = templates.filter((template) => template.is_active !== false);

  function key(inspectionId: number, itemId: number) { return `${inspectionId}:${itemId}`; }
  function draftFor(inspection: Inspection, item: TemplateItem, result?: Result): RowDraft {
    const current = drafts[key(inspection.id, item.id)];
    if (current) return current;
    return { passed: result?.passed === true || result?.value_boolean === true ? "yes" : result?.passed === false || result?.value_boolean === false ? "no" : "pending", notes: result?.notes || result?.value_text || "", cleanerId: "" };
  }
  function updateDraft(id: string, patch: Partial<RowDraft>) { setDrafts((current) => ({ ...current, [id]: { ...current[id], ...patch, saved: false, error: undefined } })); }

  async function startInspection(template: Template) {
    if (!siteId || !template.area_id) return;
    try {
      const created = await api.post<Inspection>("/inspections", { site_id: Number(siteId), area_id: template.area_id, template_id: template.id, inspection_date: date, notes: "Daily cleanliness declaration" });
      setInspections((current) => [...current, created]);
    } catch (caught) { setError(caught); }
  }

  async function saveItem(inspection: Inspection, item: TemplateItem) {
    const inspectionResult = inspection.results.find((result) => result.template_item_id === item.id);
    const draft = draftFor(inspection, item, inspectionResult);
    const id = key(inspection.id, item.id);
    updateDraft(id, { saving: true });
    try {
      const payload = { template_item_id: item.id, responsible_cleaner_id: draft.cleanerId ? Number(draft.cleanerId) : null, value_boolean: draft.passed === "pending" ? null : draft.passed === "yes", passed: draft.passed === "pending" ? null : draft.passed === "yes", notes: draft.notes };
      if (inspectionResult) await api.put(`/inspections/${inspection.id}/results/${inspectionResult.id}`, payload);
      else await api.post(`/inspections/${inspection.id}/results`, payload);
      updateDraft(id, { saving: false, saved: true });
    } catch (caught) { updateDraft(id, { saving: false, error: readableApiError(caught).message }); }
  }

  async function submitInspection(inspection: Inspection) {
    try { await api.post(`/inspections/${inspection.id}/submit`, {}); setMessage(`${inspection.area_name || inspection.template_name || "Area"} declaration submitted for review.`); await loadSheet(); }
    catch (caught) { setError(caught); }
  }

  if (loading) return <LoadingPanel label="Loading assigned cleanliness scope" />;
  return <AppShell><WorkspaceHeader eyebrow="Daily cleanliness declaration" title="Turn site standards into accountable evidence." description="Declare the condition of every important area, record whether work was completed on time, attribute exceptions to the responsible cleaner, and submit the site for review." actions={<Button className="bg-[#0F7667] text-white hover:bg-[#0B6155]" onClick={() => void loadSheet()} disabled={!siteId || loadingSheet}><ClipboardCheck size={16} /> Refresh declaration</Button>} /><div className="mb-5 grid gap-4 rounded-2xl border border-[#D9E6E0] bg-[#F1F8F5] p-4 md:grid-cols-[1fr_180px_auto] md:items-end"><div className="grid gap-2"><Label htmlFor="cleanliness_site">Assigned site</Label><select id="cleanliness_site" value={siteId} onChange={(event) => setSiteId(event.target.value)} className="h-10 rounded-md border border-[#C9DED7] bg-white px-3 text-sm text-[#294A4D]"><option value="">Select assigned site</option>{sites.map((site) => <option key={site.id} value={site.id}>{label(site, `Site ${site.id}`)}</option>)}</select></div><div className="grid gap-2"><Label htmlFor="cleanliness_date">Date</Label><Input id="cleanliness_date" type="date" value={date} onChange={(event) => setDate(event.target.value)} className="h-10 border-[#C9DED7] bg-white" /></div><div className="text-sm text-[#477168]"><strong>{siteName}</strong><br />{formatDateValue(date)} · daily declaration</div></div><AttentionNotice><strong>Control rule:</strong> a failed area must carry a corrective note and a responsible cleaner where assignment data is available. Unresolved exceptions should be escalated as issues before the day is submitted.</AttentionNotice>{error ? <div className="my-4"><ApiErrorPanel error={error} onRetry={() => void loadSheet()} /></div> : null}{message ? <div className="my-4"><WorkflowNotice>{message}</WorkflowNotice></div> : null}{loadingSheet ? <LoadingPanel label="Loading daily questions and assigned cleaners" /> : activeTemplates.length === 0 ? <EmptyPanel title="No daily cleanliness templates configured" description="Ask an administrator to configure daily templates for toilets, garden, reception, and other required operational areas." /> : <div className="mt-5 space-y-5">{activeTemplates.map((template) => { const inspection = inspectionFor(template); return <section key={template.id} className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 shadow-[0_8px_22px_rgba(24,51,48,.035)]"><div className="flex flex-col gap-3 border-b border-[#E9E3D8] pb-4 md:flex-row md:items-start md:justify-between"><div><p className="ledger-label text-[#0F7667]">{template.area_name || "Operational area"}</p><h2 className="font-serif text-2xl text-[#1F4145]">{template.template_name}</h2><p className="mt-1 text-sm text-[#6B7974]">{template.description || "Declare completion, timeliness, and exceptions for this area."}</p></div>{inspection ? <div className="flex items-center gap-2"><StatusBadge status={inspection.status} /><Button size="sm" onClick={() => void submitInspection(inspection)} disabled={inspection.status !== "draft" && inspection.status !== "returned"} className="bg-[#173F43] text-white hover:bg-[#0D3034]"><Send size={14} /> Submit area</Button></div> : <Button size="sm" onClick={() => void startInspection(template)} className="bg-[#0F7667] text-white hover:bg-[#0B6155]"><ClipboardCheck size={14} /> Start area</Button>}</div>{inspection ? <div className="mt-4 space-y-3">{template.items.map((item) => { const result = inspection.results.find((row) => row.template_item_id === item.id); const draft = draftFor(inspection, item, result); const id = key(inspection.id, item.id); const locked = !["draft", "returned"].includes(inspection.status); return <div key={item.id} className="rounded-xl border border-[#E4DED2] bg-[#FAF8F2] p-4"><div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div className="min-w-0"><p className="font-semibold text-[#315156]">{item.item_label}</p>{item.help_text ? <p className="mt-1 text-xs text-[#71807A]">{item.help_text}</p> : null}</div><div className="flex flex-wrap gap-2"><Button size="sm" disabled={locked} onClick={() => updateDraft(id, { passed: "yes" })} className={draft.passed === "yes" ? "bg-[#0F7667] text-white" : "bg-[#E5F0EC] text-[#0F7667]"}><CheckCircle2 size={14} /> Done on time</Button><Button size="sm" disabled={locked} onClick={() => updateDraft(id, { passed: "no" })} className={draft.passed === "no" ? "bg-[#A13E26] text-white" : "bg-[#FBE4DD] text-[#A13E26]"}><AlertTriangle size={14} /> Not done / exception</Button></div></div>{draft.passed === "no" ? <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end"><div className="grid gap-1"><Label className="text-xs">Corrective note / reason</Label><Input disabled={locked} value={draft.notes} onChange={(event) => updateDraft(id, { notes: event.target.value })} placeholder="What was missed and what must happen next?" className="bg-white" /></div><div className="grid gap-1"><Label className="text-xs">Responsible cleaner</Label><select disabled={locked} value={draft.cleanerId} onChange={(event) => updateDraft(id, { cleanerId: event.target.value })} className="h-10 rounded-md border border-[#D8D1C4] bg-white px-2 text-sm"><option value="">Select responsible cleaner</option>{cleaners.map((cleaner) => <option key={cleaner.id} value={cleaner.id}>{label(cleaner, `Cleaner ${cleaner.id}`)} · {formatDisplayValue(cleaner.status || "active")}</option>)}</select></div><Button size="sm" disabled={locked || draft.saving} onClick={() => void saveItem(inspection, item)} className="bg-[#173F43] text-white hover:bg-[#0D3034]">{draft.saving ? <Loader2 className="animate-spin" size={14} /> : <ShieldCheck size={14} />} {draft.saved ? "Saved" : "Save exception"}</Button></div> : <div className="mt-3 flex items-center justify-between gap-3"><p className="text-xs text-[#71807A]">Answer the area question and save the declaration.</p><Button size="sm" variant="outline" disabled={locked || draft.saving} onClick={() => void saveItem(inspection, item)}>{draft.saving ? <Loader2 className="animate-spin" size={14} /> : <ShieldCheck size={14} />} {draft.saved ? "Saved" : "Save answer"}</Button></div>}{draft.error ? <p className="mt-2 text-xs text-[#A13E26]">{draft.error}</p> : null}</div>; })}</div> : <div className="mt-5 rounded-xl border border-dashed border-[#D8D1C4] bg-[#FAF8F2] p-5 text-sm text-[#687671]">Start this area to load its daily questions. The declaration remains linked to the authenticated site scope and review chain.</div>}</section>; })}</div>}</AppShell>;
}
