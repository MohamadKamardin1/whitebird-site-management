import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ClipboardCheck, Loader2, PlayCircle, Send, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AppShell } from "@/components/AppShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { ApiErrorPanel, AttentionNotice, EmptyPanel, LoadingPanel, StatusBadge, WorkflowNotice, WorkspaceHeader, formatDateValue, formatDisplayValue } from "@/components/WorkspacePrimitives";
import { api, asPaginated, readableApiError } from "@/lib/api";
import { preferredCleanlinessTemplates } from "@/lib/cleanlinessTemplates";

interface Site { id: number; name?: string; site_name?: string; }
interface Cleaner { id: number; full_name?: string; first_name?: string; last_name?: string; status?: string; }
interface TemplateItem { id: number; item_label: string; item_type: string; required?: boolean; help_text?: string; }
interface Template { id: number; template_name: string; description?: string; area_id?: number | null; area_name?: string | null; is_active?: boolean; items: TemplateItem[]; }
interface Result { id: number; template_item_id: number; value_boolean?: boolean | null; value_text?: string; passed?: boolean | null; notes?: string; responsible_cleaner_id?: number | null; }
interface Inspection { id: number; site_id: number; template_id: number; status: string; results: Result[]; }
interface RowDraft { passed: "yes" | "no" | "pending"; notes: string; cleanerId: string; saving?: boolean; saved?: boolean; error?: string; }

const dateToday = () => new Date().toISOString().slice(0, 10);
const valueLabel = (value: { name?: string; site_name?: string; area_name?: string; full_name?: string; first_name?: string; last_name?: string }, fallback: string) => value.name || value.site_name || value.area_name || value.full_name || [value.first_name, value.last_name].filter(Boolean).join(" ") || fallback;

export default function CleanlinessPage() {
  const { t } = useLanguage();
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState("");
  const [date, setDate] = useState(dateToday());
  const [templates, setTemplates] = useState<Template[]>([]);
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [cleaners, setCleaners] = useState<Cleaner[]>([]);
  const [drafts, setDrafts] = useState<Record<string, RowDraft>>({});
  const [loading, setLoading] = useState(true);
  const [loadingSheet, setLoadingSheet] = useState(false);
  const [startingAll, setStartingAll] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadSites = useCallback(async () => {
    try {
      const next = asPaginated(await api.get("/sites?page_size=100")).results as unknown as Site[];
      setSites(next); setSiteId((current) => current || (next.length === 1 ? String(next[0].id) : ""));
    } catch (caught) { setError(caught); } finally { setLoading(false); }
  }, []);

  const loadSheet = useCallback(async () => {
    if (!siteId) return;
    setLoadingSheet(true); setError(null); setMessage(null);
    try {
      const [templateResponse, inspectionResponse, cleanerResponse] = await Promise.all([
        api.get(`/inspection-templates?page_size=100&frequency=daily&is_active=true&site_id=${siteId}`),
        api.get(`/inspections?page_size=100&site_id=${siteId}&date_from=${date}&date_to=${date}`),
        api.get("/cleaners?page_size=100"),
      ]);
      setTemplates(asPaginated(templateResponse).results as unknown as Template[]);
      setInspections(asPaginated(inspectionResponse).results as unknown as Inspection[]);
      setCleaners(asPaginated(cleanerResponse).results as unknown as Cleaner[]);
      setDrafts({});
    } catch (caught) { setError(caught); } finally { setLoadingSheet(false); }
  }, [date, siteId]);

  useEffect(() => { void loadSites(); }, [loadSites]);
  useEffect(() => { if (siteId) void loadSheet(); }, [loadSheet, siteId]);

  const activeTemplates = preferredCleanlinessTemplates(templates);
  const inspectionFor = (template: Template) => inspections.find((inspection) => inspection.template_id === template.id);
  const key = (inspectionId: number, itemId: number) => `${inspectionId}:${itemId}`;
  const complete = (item: TemplateItem, result?: Result) => item.item_type === "text" ? Boolean(result?.value_text?.trim()) : result?.passed !== null && result?.passed !== undefined;
  const totalQuestions = activeTemplates.reduce((total, template) => total + template.items.length, 0);
  const answeredQuestions = activeTemplates.reduce((total, template) => total + (inspectionFor(template)?.results || []).filter((result) => complete(template.items.find((item) => item.id === result.template_item_id) || { item_type: "yes_no" } as TemplateItem, result)).length, 0);
  const completedAreas = activeTemplates.filter((template) => inspectionFor(template)?.status === "submitted").length;

  const draftFor = (inspection: Inspection, item: TemplateItem, result?: Result): RowDraft => drafts[key(inspection.id, item.id)] || ({
    passed: item.item_type === "text" ? (result?.value_text?.trim() ? "yes" : "pending") : result?.passed === true || result?.value_boolean === true ? "yes" : result?.passed === false || result?.value_boolean === false ? "no" : "pending",
    notes: result?.value_text || result?.notes || "", cleanerId: result?.responsible_cleaner_id ? String(result.responsible_cleaner_id) : "",
  });
  const updateDraft = (id: string, patch: Partial<RowDraft>) => setDrafts((current) => ({ ...current, [id]: { ...current[id], ...patch, saved: false, error: undefined } }));

  const startInspection = async (template: Template) => {
    if (!siteId || !template.area_id) return;
    try { await api.post("/inspections", { site_id: Number(siteId), area_id: template.area_id, template_id: template.id, inspection_date: date, notes: "Daily cleanliness declaration" }); await loadSheet(); }
    catch (caught) { setError(caught); }
  };
  const startAllAreas = async () => {
    const missing = activeTemplates.filter((template) => !inspectionFor(template));
    if (!missing.length) return;
    setStartingAll(true);
    try { await Promise.all(missing.map((template) => startInspection(template))); setMessage(t("Today's cleanliness sheet is open.")); }
    finally { setStartingAll(false); }
  };
  const saveItem = async (inspection: Inspection, item: TemplateItem) => {
    const current = inspection.results.find((result) => result.template_item_id === item.id);
    const draft = draftFor(inspection, item, current); const id = key(inspection.id, item.id);
    if (item.item_type === "text" && !draft.notes.trim()) { updateDraft(id, { error: t("Write an answer before saving.") }); return; }
    if (item.item_type !== "text" && draft.passed === "pending") { updateDraft(id, { error: t("Choose Done on time or Exception before saving.") }); return; }
    if (item.item_type !== "text" && draft.passed === "no" && !draft.notes.trim()) { updateDraft(id, { error: t("Add a corrective note for this exception.") }); return; }
    updateDraft(id, { saving: true });
    const payload = { template_item_id: item.id, responsible_cleaner_id: draft.cleanerId ? Number(draft.cleanerId) : null, value_text: item.item_type === "text" ? draft.notes : "", value_boolean: item.item_type === "text" ? null : draft.passed === "yes", passed: item.item_type === "text" ? null : draft.passed === "yes", notes: item.item_type === "text" ? "" : draft.notes };
    try {
      const saved = current ? await api.put<Result>(`/inspections/${inspection.id}/results/${current.id}`, payload) : await api.post<Result>(`/inspections/${inspection.id}/results`, payload);
      setInspections((rows) => rows.map((row) => row.id !== inspection.id ? row : { ...row, results: row.results.some((result) => result.template_item_id === item.id) ? row.results.map((result) => result.template_item_id === item.id ? saved : result) : [...row.results, saved] }));
      updateDraft(id, { saving: false, saved: true });
    } catch (caught) { updateDraft(id, { saving: false, error: readableApiError(caught).message }); }
  };
  const submitInspection = async (inspection: Inspection, template: Template) => {
    try {
      const fresh = await api.get<Inspection>(`/inspections/${inspection.id}`);
      const unanswered = template.items.filter((item) => !fresh.results.some((result) => result.template_item_id === item.id && complete(item, result)));
      if (unanswered.length) { setMessage(`${t(template.area_name || "This area")} ${t("still has unanswered questions. Save every row before submitting.")}`); return; }
      await api.post(`/inspections/${inspection.id}/submit`, {}); setMessage(`${t(template.area_name || "Area")} ${t("declaration submitted for review.")}`); await loadSheet();
    } catch (caught) { setError(caught); }
  };

  if (loading) return <LoadingPanel label={t("Loading assigned cleanliness scope")} />;
  return <AppShell><WorkspaceHeader eyebrow={t("Daily cleanliness declaration")} title={t("Daily cleanliness worksheet")} description="" actions={<Button className="bg-[#0F7667] text-white hover:bg-[#0B6155]" onClick={() => void loadSheet()} disabled={!siteId || loadingSheet}><ClipboardCheck size={16} /> {t("Refresh sheet")}</Button>} />
    <div className="mb-5 grid gap-4 rounded-2xl border border-[#D9E6E0] bg-[#F1F8F5] p-4 md:grid-cols-[minmax(0,1fr)_180px_auto] md:items-end"><div className="grid gap-2"><Label>{t("Assigned site")}</Label><select value={siteId} onChange={(event) => setSiteId(event.target.value)} disabled={sites.length <= 1} className="h-10 rounded-md border border-[#C9DED7] bg-white px-3 text-sm text-[#294A4D]"><option value="">{t("Select assigned site")}</option>{sites.map((site) => <option key={site.id} value={site.id}>{valueLabel(site, `Site ${site.id}`)}</option>)}</select></div><div className="grid gap-2"><Label>{t("Date")}</Label><Input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></div><div className="text-sm text-[#477168]"><strong>{valueLabel(sites.find((site) => String(site.id) === siteId) || {}, t("Assigned site"))}</strong><br />{formatDateValue(date)}</div></div>
    <div className="mb-5 grid gap-3 rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-4 sm:grid-cols-[1fr_auto_auto] sm:items-center"><div><p className="ledger-label text-[#0F7667]">{t("Daily worksheet progress")}</p><p className="mt-1 text-sm text-[#687874]">{answeredQuestions} / {totalQuestions} {t("questions answered")} · {completedAreas} / {activeTemplates.length} {t("areas submitted")}</p></div><Button onClick={() => void startAllAreas()} disabled={!siteId || startingAll} className="bg-[#173F43] text-white hover:bg-[#0D3034]">{startingAll ? <Loader2 className="animate-spin" size={16} /> : <PlayCircle size={16} />}{t("Open today's sheet")}</Button></div>
    <AttentionNotice><strong>{t("How to use this sheet:")}</strong> {t("Answer each row, save it, and submit the area when all rows are complete.")}</AttentionNotice>{error ? <div className="my-4"><ApiErrorPanel error={error} onRetry={() => void loadSheet()} /></div> : null}{message ? <div className="my-4"><WorkflowNotice>{message}</WorkflowNotice></div> : null}
    {loadingSheet ? <LoadingPanel label={t("Loading daily surveys")} /> : !activeTemplates.length ? <EmptyPanel title={t("No daily cleanliness templates configured")} description={t("Ask an administrator to configure daily templates.")} /> : <div className="mt-5 space-y-5">{activeTemplates.map((template) => {
      const inspection = inspectionFor(template); const locked = Boolean(inspection && !["draft", "returned"].includes(inspection.status));
      return <section key={template.id} className="min-w-0 overflow-hidden rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] shadow-[0_8px_22px_rgba(24,51,48,.035)]"><div className="flex flex-col gap-3 border-b border-[#E9E3D8] p-4 sm:flex-row sm:items-start sm:justify-between sm:p-5"><div><p className="ledger-label text-[#0F7667]">{t(template.area_name || "Operational area")}</p><h2 className="mt-1 font-serif text-2xl text-[#1F4145]">{t(template.template_name)}</h2><p className="mt-1 text-sm text-[#6B7974]">{t(template.description || "")}</p></div>{inspection ? <div className="flex items-center gap-2"><StatusBadge status={inspection.status} /><Button size="sm" disabled={locked} className="bg-[#173F43] text-white" onClick={() => void submitInspection(inspection, template)}><Send size={14} /> {t("Submit area")}</Button></div> : <Button size="sm" className="bg-[#0F7667] text-white" onClick={() => void startInspection(template)}><ClipboardCheck size={14} /> {t("Open area")}</Button>}</div>
      {inspection ? <div className="overflow-x-auto"><table className="min-w-[940px] w-full border-collapse text-sm"><thead><tr className="bg-[#F3F0E8] text-left text-xs uppercase tracking-[.08em] text-[#71807A]"><th className="sticky left-0 z-10 w-[34%] border-b border-r border-[#E4DED2] bg-[#F3F0E8] px-4 py-3">{t("Question / check")}</th><th className="w-[13%] border-b border-r border-[#E4DED2] px-3 py-3 text-center">{t("Done on time")}</th><th className="w-[13%] border-b border-r border-[#E4DED2] px-3 py-3 text-center">{t("Exception")}</th><th className="w-[25%] border-b border-r border-[#E4DED2] px-3 py-3">{t("Evidence / responsible cleaner")}</th><th className="w-[15%] border-b border-[#E4DED2] px-3 py-3 text-center">{t("Save")}</th></tr></thead><tbody>{template.items.map((item, index) => {
        const result = inspection.results.find((row) => row.template_item_id === item.id); const draft = draftFor(inspection, item, result); const id = key(inspection.id, item.id); const textItem = item.item_type === "text";
        return <tr key={item.id} className={index % 2 ? "bg-[#FCFBF7]" : "bg-white"}><td className="sticky left-0 z-[1] border-b border-r border-[#E8E2D8] bg-inherit px-4 py-3 align-top"><div className="flex gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#E5F0EC] text-xs font-bold text-[#0F7667]">{index + 1}</span><div><p className="font-medium leading-6 text-[#315156]">{t(item.item_label)}</p>{item.help_text && <p className="mt-1 text-xs leading-5 text-[#71807A]">{t(item.help_text)}</p>}</div></div></td>{textItem ? <td colSpan={2} className="border-b border-r border-[#E8E2D8] px-3 py-3 text-center text-xs font-bold text-[#71807A]">{t("Text answer")}</td> : <><td className="border-b border-r border-[#E8E2D8] p-3"><Button size="sm" disabled={locked} onClick={() => updateDraft(id, { passed: "yes" })} className={`w-full ${draft.passed === "yes" ? "bg-[#0F7667] text-white" : "bg-[#E5F0EC] text-[#0F7667]"}`}><CheckCircle2 size={14} /> {t("Yes")}</Button></td><td className="border-b border-r border-[#E8E2D8] p-3"><Button size="sm" disabled={locked} onClick={() => updateDraft(id, { passed: "no" })} className={`w-full ${draft.passed === "no" ? "bg-[#A13E26] text-white" : "bg-[#FBE4DD] text-[#A13E26]"}`}><AlertTriangle size={14} /> {t("No")}</Button></td></>}<td className="border-b border-r border-[#E8E2D8] p-3 align-top">{textItem ? <Textarea disabled={locked} value={draft.notes} onChange={(event) => updateDraft(id, { notes: event.target.value })} placeholder={t("Write your answer")} className="min-h-24 resize-y bg-white text-sm" /> : draft.passed === "no" ? <div className="grid gap-2"><Textarea disabled={locked} value={draft.notes} onChange={(event) => updateDraft(id, { notes: event.target.value })} placeholder={t("What happened and what must happen next?")} className="min-h-20 resize-y bg-white text-xs" /><select disabled={locked} value={draft.cleanerId} onChange={(event) => updateDraft(id, { cleanerId: event.target.value })} className="h-9 rounded-md border border-[#D8D1C4] bg-white px-2 text-xs"><option value="">{t("Select responsible cleaner")}</option>{cleaners.map((cleaner) => <option key={cleaner.id} value={cleaner.id}>{valueLabel(cleaner, `Cleaner ${cleaner.id}`)} · {formatDisplayValue(cleaner.status || "active")}</option>)}</select></div> : <span className="text-xs text-[#9BA6A1]">{t("No exception note required.")}</span>}</td><td className="border-b border-[#E8E2D8] p-3 align-top"><Button size="sm" variant="outline" disabled={locked || draft.saving} onClick={() => void saveItem(inspection, item)} className="w-full bg-white">{draft.saving ? <Loader2 className="animate-spin" size={14} /> : <ShieldCheck size={14} />}{draft.saved ? t("Saved") : t("Save")}</Button>{draft.error && <p className="mt-2 text-xs text-[#A13E26]">{draft.error}</p>}</td></tr>;
      })}</tbody></table></div> : <p className="p-5 text-sm text-[#687671]">{t("Open this area to load its daily questions into the worksheet.")}</p>}</section>;
    })}</div>}</AppShell>;
}
