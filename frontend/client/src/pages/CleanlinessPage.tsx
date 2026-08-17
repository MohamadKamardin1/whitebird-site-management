import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ClipboardCheck, Loader2, PlayCircle, Send, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AppShell } from "@/components/AppShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { ApiErrorPanel, AttentionNotice, EmptyPanel, LoadingPanel, StatusBadge, WorkflowNotice, WorkspaceHeader, formatDateValue, formatDisplayValue } from "@/components/WorkspacePrimitives";
import { api, asPaginated, readableApiError } from "@/lib/api";

interface Site { id: number; name?: string; site_name?: string; }
interface Cleaner { id: number; full_name?: string; first_name?: string; last_name?: string; status?: string; }
interface TemplateItem { id: number; item_label: string; item_type: string; required?: boolean; help_text?: string; }
interface Template { id: number; template_name: string; description?: string; site_id?: number | null; area_id?: number | null; area_name?: string | null; frequency?: string; is_active?: boolean; items: TemplateItem[]; }
interface Result { id: number; template_item_id: number; item_label: string; value_boolean?: boolean | null; value_text?: string; passed?: boolean | null; notes?: string; responsible_cleaner_id?: number | null; }
interface Inspection { id: number; site_id: number; area_id: number; area_name?: string; template_id: number; template_name?: string; inspection_date: string; status: string; results: Result[]; notes?: string; }
interface RowDraft { passed: "yes" | "no" | "pending"; notes: string; cleanerId: string; saving?: boolean; saved?: boolean; error?: string; }

function label(value: { name?: string; site_name?: string; area_name?: string; full_name?: string; first_name?: string; last_name?: string }, fallback: string) {
  return value.name || value.site_name || value.area_name || value.full_name || [value.first_name, value.last_name].filter(Boolean).join(" ") || fallback;
}

export default function CleanlinessPage() {
  const { t } = useLanguage();
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
  const [startingAll, setStartingAll] = useState(false);
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
      setDrafts({});
    } catch (caught) { setError(caught); }
    finally { setLoadingSheet(false); }
  }, [date, siteId]);
  useEffect(() => { if (siteId) void loadSheet(); }, [loadSheet, siteId]);

  const siteName = useMemo(() => label(sites.find((site) => String(site.id) === siteId) || {}, "Assigned site"), [siteId, sites]);
  const activeTemplates = templates.filter((template) => template.is_active !== false);
  const inspectionFor = (template: Template) => inspections.find((row) => row.template_id === template.id && (!template.area_id || row.area_id === template.area_id));
  const totalQuestions = activeTemplates.reduce((total, template) => total + template.items.length, 0);
  const answeredQuestions = activeTemplates.reduce((total, template) => {
    const inspection = inspectionFor(template);
    if (!inspection) return total;
    return total + template.items.filter((item) => inspection.results.some((result) => result.template_item_id === item.id && result.passed !== null && result.passed !== undefined)).length;
  }, 0);
  const completedAreas = activeTemplates.filter((template) => inspectionFor(template)?.status === "submitted").length;

  function key(inspectionId: number, itemId: number) { return `${inspectionId}:${itemId}`; }
  function draftFor(inspection: Inspection, item: TemplateItem, result?: Result): RowDraft {
    const current = drafts[key(inspection.id, item.id)];
    if (current) return current;
    return { passed: result?.passed === true || result?.value_boolean === true ? "yes" : result?.passed === false || result?.value_boolean === false ? "no" : "pending", notes: result?.notes || result?.value_text || "", cleanerId: result?.responsible_cleaner_id ? String(result.responsible_cleaner_id) : "" };
  }
  function updateDraft(id: string, patch: Partial<RowDraft>) { setDrafts((current) => ({ ...current, [id]: { ...current[id], ...patch, saved: false, error: undefined } })); }

  async function startInspection(template: Template) {
    if (!siteId || !template.area_id) return;
    try {
      const created = await api.post<Inspection>("/inspections", { site_id: Number(siteId), area_id: template.area_id, template_id: template.id, inspection_date: date, notes: "Daily cleanliness declaration" });
      setInspections((current) => [...current, created]);
    } catch (caught) { setError(caught); }
  }

  async function startAllAreas() {
    const missing = activeTemplates.filter((template) => !inspectionFor(template));
    if (!missing.length) return;
    setStartingAll(true); setError(null); setMessage(null);
    try {
      await Promise.all(missing.map((template) => template.area_id ? startInspection(template) : Promise.resolve()));
      setMessage("Today’s cleanliness sheet is open. Work down the rows, mark each check, and save exceptions with their responsible cleaner.");
      await loadSheet();
    } catch (caught) { setError(caught); }
    finally { setStartingAll(false); }
  }

  async function saveItem(inspection: Inspection, item: TemplateItem) {
    const inspectionResult = inspection.results.find((result) => result.template_item_id === item.id);
    const draft = draftFor(inspection, item, inspectionResult);
    const id = key(inspection.id, item.id);
    if (draft.passed === "pending") { updateDraft(id, { error: t("Choose Done on time or Exception before saving.") }); return; }
    if (draft.passed === "no" && !draft.notes.trim()) { updateDraft(id, { error: t("Add a corrective note for this exception.") }); return; }
    updateDraft(id, { saving: true });
    try {
      const payload = { template_item_id: item.id, responsible_cleaner_id: draft.cleanerId ? Number(draft.cleanerId) : null, value_boolean: draft.passed === "yes", passed: draft.passed === "yes", notes: draft.notes };
      let savedResult: Result;
      try {
        savedResult = inspectionResult
          ? await api.put<Result>(`/inspections/${inspection.id}/results/${inspectionResult.id}`, payload)
          : await api.post<Result>(`/inspections/${inspection.id}/results`, payload);
      } catch (caught) {
        const readable = readableApiError(caught);
        if (inspectionResult && readable.message.includes("not found")) {
          savedResult = await api.post<Result>(`/inspections/${inspection.id}/results`, payload);
        } else {
          throw caught;
        }
      }
      setInspections((current) => current.map((row) => {
        if (row.id !== inspection.id) return row;
        const existingIndex = row.results.findIndex((result) => result.template_item_id === savedResult.template_item_id);
        const results = existingIndex >= 0
          ? row.results.map((result, index) => index === existingIndex ? savedResult : result)
          : [...row.results, savedResult];
        return { ...row, results };
      }));
      updateDraft(id, { saving: false, saved: true, error: undefined });
    } catch (caught) {
      const readable = readableApiError(caught);
      if (readable.message.toLowerCase().includes("already exists") || readable.message.toLowerCase().includes("unique")) {
        await loadSheet();
        updateDraft(id, { saving: false, saved: true, error: undefined });
        setMessage(t("This answer was already saved. The worksheet is now synchronized with the server record."));
      } else {
        updateDraft(id, { saving: false, error: readable.message });
      }
    }
  }

  async function submitInspection(inspection: Inspection, template: Template) {
    try {
      const freshInspection = await api.get<Inspection>(`/inspections/${inspection.id}`);
      const unanswered = template.items.filter((item) => !freshInspection.results.some((result) => result.template_item_id === item.id && result.passed !== null && result.passed !== undefined));
      if (unanswered.length) { setMessage(`${t(template.area_name || "This area")} ${t("still has unanswered questions. Save every row before submitting.")}`); return; }
      await api.post(`/inspections/${inspection.id}/submit`, {});
      setMessage(`${t(template.area_name || "Area")} ${t("declaration submitted for review.")}`);
      await loadSheet();
    }
    catch (caught) { setError(caught); }
  }

  if (loading) return <LoadingPanel label={t("Loading assigned cleanliness scope")} />;
  return <AppShell><WorkspaceHeader eyebrow={t("Daily cleanliness declaration")} title={t("Complete today’s site sheet, one clear row at a time.")} description={t("This beginner-friendly checklist follows the White Bird paper report. Your assigned site and selected date control the evidence scope; every question must be answered before its area can be submitted.")} actions={<Button className="bg-[#0F7667] text-white hover:bg-[#0B6155]" onClick={() => void loadSheet()} disabled={!siteId || loadingSheet}><ClipboardCheck size={16} /> {t("Refresh sheet")}</Button>} /><div className="mb-5 grid gap-4 rounded-2xl border border-[#D9E6E0] bg-[#F1F8F5] p-4 md:grid-cols-[minmax(0,1fr)_180px_auto] md:items-end"><div className="grid gap-2"><Label htmlFor="cleanliness_site">{t("Assigned site")}</Label><select id="cleanliness_site" value={siteId} onChange={(event) => setSiteId(event.target.value)} className="h-10 rounded-md border border-[#C9DED7] bg-white px-3 text-sm text-[#294A4D]" disabled={sites.length <= 1}><option value="">{t("Select assigned site")}</option>{sites.map((site) => <option key={site.id} value={site.id}>{label(site, `Site ${site.id}`)}</option>)}</select></div><div className="grid gap-2"><Label htmlFor="cleanliness_date">{t("Date")}</Label><Input id="cleanliness_date" type="date" value={date} onChange={(event) => setDate(event.target.value)} className="h-10 border-[#C9DED7] bg-white" /></div><div className="text-sm text-[#477168]"><strong>{siteName}</strong><br />{formatDateValue(date)} · {t("daily declaration")}</div></div><div className="mb-5 grid gap-3 rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-4 sm:grid-cols-[1fr_auto_auto] sm:items-center"><div><p className="ledger-label text-[#0F7667]">{t("Daily worksheet progress")}</p><p className="mt-1 text-sm text-[#687874]">{answeredQuestions} of {totalQuestions || 0} {t("questions answered")} · {completedAreas} of {activeTemplates.length} {t("areas submitted")}</p><div className="mt-2 h-2 overflow-hidden rounded-full bg-[#E6E1D7]"><div className="h-full rounded-full bg-[#0F7667] transition-all" style={{ width: `${totalQuestions ? Math.round(answeredQuestions / totalQuestions * 100) : 0}%` }} /></div></div><Button onClick={() => void startAllAreas()} disabled={!siteId || startingAll || !activeTemplates.length} className="bg-[#173F43] text-white hover:bg-[#0D3034]"><PlayCircle size={16} /> {startingAll ? "Inafungua…" : t("Open today’s sheet")}</Button><span className="text-xs text-[#71807A]">{t("Saved answers stay auditable.")}</span></div><AttentionNotice><strong>{t("How to use this sheet:")}</strong> choose <strong>{t("Done on time")}</strong> when the check is complete. Choose <strong>{t("Exception")}</strong> when it is not complete, then record what must happen and who is responsible. {t("Save the row before moving on.")}</AttentionNotice>{error ? <div className="my-4"><ApiErrorPanel error={error} onRetry={() => void loadSheet()} /></div> : null}{message ? <div className="my-4"><WorkflowNotice>{message}</WorkflowNotice></div> : null}{loadingSheet ? <LoadingPanel label={t("Loading today’s questions and assigned cleaners")} /> : activeTemplates.length === 0 ? <EmptyPanel title={t("No daily cleanliness templates configured")} description={t("Ask an administrator to configure the PDF-derived daily templates for toilets, offices, indoor areas, outdoor areas, gardens, store readiness, and staff performance.")} /> : <div className="mt-5 space-y-5">{activeTemplates.map((template) => { const inspection = inspectionFor(template); const locked = Boolean(inspection && !["draft", "returned"].includes(inspection.status)); return <section key={template.id} className="min-w-0 overflow-hidden rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] shadow-[0_8px_22px_rgba(24,51,48,.035)]"><div className="flex flex-col gap-3 border-b border-[#E9E3D8] p-4 sm:flex-row sm:items-start sm:justify-between sm:p-5"><div className="min-w-0"><p className="ledger-label text-[#0F7667]">{t(template.area_name || "Operational area")}</p><h2 className="mt-1 font-serif text-2xl text-[#1F4145]">{template.template_name}</h2><p className="mt-1 text-sm leading-6 text-[#6B7974]">{t(template.description || "Work across the rows below and save each answer.")}</p></div>{inspection ? <div className="flex shrink-0 flex-wrap items-center gap-2"><StatusBadge status={inspection.status} /><Button size="sm" onClick={() => void submitInspection(inspection, template)} disabled={locked} className="bg-[#173F43] text-white hover:bg-[#0D3034]"><Send size={14} /> {t("Submit area")}</Button></div> : <Button size="sm" onClick={() => void startInspection(template)} className="shrink-0 bg-[#0F7667] text-white hover:bg-[#0B6155]"><ClipboardCheck size={14} /> {t("Open area")}</Button>}</div>{inspection ? <div className="overflow-x-auto"><table className="min-w-[940px] w-full border-collapse text-sm"><thead><tr className="bg-[#F3F0E8] text-left text-xs uppercase tracking-[.08em] text-[#71807A]"><th className="sticky left-0 z-10 w-[34%] border-b border-r border-[#E4DED2] bg-[#F3F0E8] px-4 py-3">{t("Question / check")}</th><th className="w-[13%] border-b border-r border-[#E4DED2] px-3 py-3 text-center">{t("Done on time")}</th><th className="w-[13%] border-b border-r border-[#E4DED2] px-3 py-3 text-center">{t("Exception")}</th><th className="w-[25%] border-b border-r border-[#E4DED2] px-3 py-3">{t("Evidence / responsible cleaner")}</th><th className="w-[15%] border-b border-[#E4DED2] px-3 py-3 text-center">{t("Save")}</th></tr></thead><tbody>{template.items.map((item, index) => { const result = inspection.results.find((row) => row.template_item_id === item.id); const draft = draftFor(inspection, item, result); const id = key(inspection.id, item.id); return <tr key={item.id} className={index % 2 ? "bg-[#FCFBF7]" : "bg-white"}><td className="sticky left-0 z-[1] border-b border-r border-[#E8E2D8] bg-inherit px-4 py-3 align-top"><div className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#E5F0EC] text-xs font-bold text-[#0F7667]">{index + 1}</span><div className="min-w-0"><p className="font-medium leading-6 text-[#315156]">{t(item.item_label)}</p>{item.help_text ? <p className="mt-1 text-xs leading-5 text-[#71807A]">{item.help_text}</p> : null}</div></div></td><td className="border-b border-r border-[#E8E2D8] px-3 py-3 text-center align-top"><Button size="sm" disabled={locked} onClick={() => updateDraft(id, { passed: "yes" })} className={`w-full justify-center ${draft.passed === "yes" ? "bg-[#0F7667] text-white" : "bg-[#E5F0EC] text-[#0F7667] hover:bg-[#CFE9DF]"}`}><CheckCircle2 size={14} /> {t("Yes")}</Button></td><td className="border-b border-r border-[#E8E2D8] px-3 py-3 text-center align-top"><Button size="sm" disabled={locked} onClick={() => updateDraft(id, { passed: "no" })} className={`w-full justify-center ${draft.passed === "no" ? "bg-[#A13E26] text-white" : "bg-[#FBE4DD] text-[#A13E26] hover:bg-[#F5D3C8]"}`}><AlertTriangle size={14} /> {t("No")}</Button></td><td className="border-b border-r border-[#E8E2D8] px-3 py-3 align-top">{draft.passed === "no" ? <div className="grid gap-2"><Input disabled={locked} value={draft.notes} onChange={(event) => updateDraft(id, { notes: event.target.value })} placeholder={t("What happened and what must happen next?")} className="h-9 bg-white text-xs" /><select disabled={locked} value={draft.cleanerId} onChange={(event) => updateDraft(id, { cleanerId: event.target.value })} className="h-9 rounded-md border border-[#D8D1C4] bg-white px-2 text-xs"><option value="">{t("Select responsible cleaner")}</option>{cleaners.map((cleaner) => <option key={cleaner.id} value={cleaner.id}>{label(cleaner, `Cleaner ${cleaner.id}`)} · {formatDisplayValue(cleaner.status || "active")}</option>)}</select></div> : <span className="text-xs text-[#9BA6A1]">{t("No exception note required.")}</span>}</td><td className="border-b border-[#E8E2D8] px-3 py-3 text-center align-top"><Button size="sm" variant="outline" disabled={locked || draft.saving} onClick={() => void saveItem(inspection, item)} className="w-full bg-white">{draft.saving ? <Loader2 className="animate-spin" size={14} /> : <ShieldCheck size={14} />} {draft.saved ? t("Saved") : t("Save") }</Button>{draft.error ? <p className="mt-2 text-left text-xs leading-4 text-[#A13E26]">{draft.error}</p> : null}</td></tr>; })}</tbody></table></div> : <div className="border-t border-dashed border-[#D8D1C4] bg-[#FAF8F2] p-5 text-sm text-[#687671]">{t("Open this area to load its daily questions into the worksheet.")}</div>}</section>; })}</div>}</AppShell>;
}
