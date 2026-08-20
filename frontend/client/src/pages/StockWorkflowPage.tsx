import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, ClipboardCheck, Loader2, PackagePlus, RefreshCw, Send, Trash2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiErrorPanel, EmptyPanel, LoadingPanel, StatusBadge, WorkspaceHeader } from "@/components/WorkspacePrimitives";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { api, asPaginated } from "@/lib/api";
import { tanzaniaDate } from "@/lib/dates";

type Row = Record<string, any>;
type RequestLine = { itemId: string; left: string; needed: string; notes: string };
const inputClass = "h-10 border-[#D8D2C5] bg-white";
const selectClass = "h-10 w-full rounded-md border border-[#D8D2C5] bg-white px-3 text-sm text-[#294A4D]";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="grid gap-2"><Label>{label}</Label>{children}</label>;
}

function statusLabel(status: string, t: (key: string) => string) {
  return t(status.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()));
}

export default function StockWorkflowPage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [stores, setStores] = useState<Row[]>([]);
  const [storeId, setStoreId] = useState("");
  const [items, setItems] = useState<Row[]>([]);
  const [requests, setRequests] = useState<Row[]>([]);
  const [lines, setLines] = useState<RequestLine[]>([{ itemId: "", left: "", needed: "", notes: "" }]);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const role = user?.role;
  const isSiteSupervisor = role === "site_supervisor";
  const isZoneSupervisor = role === "zone_supervisor";
  const isAssistant = role === "assistant_general_supervisor";
  const isHr = role === "hr";
  const canRequest = isSiteSupervisor && new Date().getDate() <= 17;

  const refreshStore = useCallback(async (id: string) => {
    if (!id) { setItems([]); setRequests([]); return; }
    const [itemData, requestData] = await Promise.all([api.get(`/stores/${id}/items`), api.get(`/stores/${id}/requests?page_size=50`)]);
    setItems(Array.isArray(itemData) ? itemData : asPaginated(itemData).results as Row[]);
    setRequests(asPaginated(requestData).results as Row[]);
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await api.get("/stores?page_size=100");
      const available = asPaginated(data).results as Row[];
      const siteStores = available.filter((store) => store.site_id);
      setStores(siteStores);
      setStoreId((current) => current || (siteStores[0] ? String(siteStores[0].id) : ""));
    } catch (caught) { setError(caught); } finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void refreshStore(storeId).catch(setError); }, [refreshStore, storeId]);

  const selectedItem = useCallback((id: string) => items.find((item) => String(item.id) === id), [items]);
  const selectedStore = useMemo(() => stores.find((store) => String(store.id) === storeId), [storeId, stores]);
  const updateLine = (index: number, key: keyof RequestLine, value: string) => setLines((current) => current.map((line, lineIndex) => lineIndex === index ? { ...line, [key]: value } : line));

  async function run(action: () => Promise<void>, success: string) {
    setSaving(true); setError(null); setMessage("");
    try { await action(); setMessage(success); await refreshStore(storeId); } catch (caught) { setError(caught); } finally { setSaving(false); }
  }

  const submitRequest = () => run(async () => {
    const created = await api.post<Row>(`/stores/${storeId}/requests`, {
      request_date: tanzaniaDate(), notes,
      items: lines.filter((line) => line.itemId && Number(line.needed) > 0).map((line) => ({
        store_item_id: Number(line.itemId), quantity_left: Number(line.left || 0), requested_quantity: Number(line.needed), notes: line.notes,
      })),
    });
    await api.post(`/stores/${storeId}/requests/${created.id}/submit`);
    setLines([{ itemId: "", left: "", needed: "", notes: "" }]); setNotes("");
  }, t("Stock request submitted"));

  const moveRequest = (request: Row, action: "review" | "assistant-approve" | "hr-pack" | "assemble") => run(async () => {
    if (action === "review" || action === "assistant-approve") {
      await api.post(`/stores/${storeId}/requests/${request.id}/${action}`, {
        approved: (request.items || []).map((item: Row) => ({ item_id: item.id, approved_quantity: item.requested_quantity })), notes: "Verified at the site store.",
      });
    } else if (action === "hr-pack") {
      await api.post(`/stores/${storeId}/requests/${request.id}/hr-pack`, { reason: "HR packing started." });
    } else {
      await api.post(`/stores/${storeId}/requests/${request.id}/assemble`, {
        packed: (request.items || []).map((item: Row) => ({ item_id: item.id, packed_quantity: item.assistant_approved_quantity || item.verified_quantity || item.requested_quantity })), notes: "Items assembled for dispatch.",
      });
    }
  }, t("Request status updated"));

  const actionFor = (request: Row) => {
    if (isZoneSupervisor && request.status === "submitted") return { label: t("Verify request"), action: "review" as const };
    if (isAssistant && request.status === "zone_verified") return { label: t("Approve request"), action: "assistant-approve" as const };
    if (isHr && request.status === "assistant_approved") return { label: t("Start packing"), action: "hr-pack" as const };
    if (isHr && request.status === "hr_packing") return { label: t("Mark assembled"), action: "assemble" as const };
    return null;
  };

  return <AppShell><WorkspaceHeader
    eyebrow={t("Stores & stock")}
    title={t("Stock request workflow")}
    description={t("Site Supervisor submits → Zone Supervisor verifies → Assistant General Supervisor approves → HR packs and assembles.")}
    actions={<Button variant="outline" className="bg-[#FFFDF8]" onClick={() => void load()}><RefreshCw size={16} /> {t("Refresh")}</Button>}
  />
    {error ? <div className="mb-5"><ApiErrorPanel error={error} onRetry={() => void load()} /></div> : null}
    {message ? <p className="mb-5 rounded-xl bg-[#E5F0EC] px-4 py-3 text-sm text-[#175F55]">{message}</p> : null}
    {loading ? <LoadingPanel label={t("Loading configured stores")} /> : <div className="grid gap-5 xl:grid-cols-[minmax(0,1.08fr)_minmax(0,.92fr)]">
      <section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 sm:p-6">
        <p className="ledger-label text-[#0F7667]">{t("Request configured stock")}</p>
        <h2 className="mt-1 font-serif text-2xl text-[#1F4145]">{isSiteSupervisor ? t("Prepare this month’s request") : t("Review stock requests")}</h2>
        {isSiteSupervisor && !canRequest ? <p className="mt-3 rounded-lg bg-[#FBE4DD] px-3 py-2 text-sm text-[#9D3D28]">{t("The monthly request window closed after the 17th. Your submitted request remains available for review.")}</p> : null}
        <div className="mt-5 grid gap-4"><Field label={t("Assigned store")}><select className={selectClass} value={storeId} onChange={(event) => setStoreId(event.target.value)}><option value="">—</option>{stores.map((store) => <option key={store.id} value={store.id}>{store.store_name} · {store.site_name}</option>)}</select></Field>
          {isSiteSupervisor ? <><div className="overflow-x-auto"><table className="min-w-[760px] w-full border-collapse text-sm"><thead><tr className="bg-[#F3F0E8] text-left text-xs uppercase tracking-[.08em] text-[#71807A]"><th className="border border-[#E4DED2] px-3 py-2">{t("Item")}</th><th className="border border-[#E4DED2] px-3 py-2">{t("Unit")}</th><th className="border border-[#E4DED2] px-3 py-2">{t("Quantity left")}</th><th className="border border-[#E4DED2] px-3 py-2">{t("Quantity requested")}</th><th className="border border-[#E4DED2] px-3 py-2">{t("Notes")}</th><th className="border border-[#E4DED2] px-3 py-2" /></tr></thead><tbody>{lines.map((line, index) => { const item = selectedItem(line.itemId); return <tr key={index}><td className="border border-[#E8E2D8] p-2"><select className={selectClass} disabled={!canRequest || !storeId} value={line.itemId} onChange={(event) => updateLine(index, "itemId", event.target.value)}><option value="">—</option>{items.map((row) => <option key={row.id} value={row.id}>{row.item_name}</option>)}</select></td><td className="border border-[#E8E2D8] px-3 py-2 font-semibold text-[#0F7667]">{item?.unit || "—"}</td><td className="border border-[#E8E2D8] p-2"><Input disabled={!canRequest} className={inputClass + " min-w-24"} type="number" min="0" value={line.left} onChange={(event) => updateLine(index, "left", event.target.value)} /></td><td className="border border-[#E8E2D8] p-2"><Input disabled={!canRequest} className={inputClass + " min-w-24"} type="number" min="0.01" value={line.needed} onChange={(event) => updateLine(index, "needed", event.target.value)} /></td><td className="border border-[#E8E2D8] p-2"><Input disabled={!canRequest} className={inputClass + " min-w-40"} value={line.notes} onChange={(event) => updateLine(index, "notes", event.target.value)} /></td><td className="border border-[#E8E2D8] p-2">{lines.length > 1 ? <Button disabled={!canRequest} variant="ghost" size="icon" onClick={() => setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))}><Trash2 size={15} /></Button> : null}</td></tr>; })}</tbody></table></div><Button type="button" variant="outline" className="bg-white" disabled={!canRequest || !storeId} onClick={() => setLines((current) => [...current, { itemId: "", left: "", needed: "", notes: "" }])}><PackagePlus size={15} /> {t("Add another item")}</Button><Field label={t("Request notes")}><Textarea disabled={!canRequest} className="min-h-20 bg-white" value={notes} onChange={(event) => setNotes(event.target.value)} /></Field><Button disabled={!canRequest || !storeId || saving || !lines.some((line) => line.itemId && Number(line.needed) > 0)} onClick={() => void submitRequest()} className="bg-[#0F7667] text-white">{saving ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}{t("Submit stock request")}</Button></> : <div className="rounded-xl bg-[#F3F0E8] p-4 text-sm leading-6 text-[#536762]"><ClipboardCheck className="mb-2 text-[#0F7667]" size={20} />{t("Choose a site store then use the request action shown beside each itemised request in your queue.")}</div>}</div>
      </section>
      <section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 sm:p-6"><p className="ledger-label text-[#0F7667]">{t("Request history")}</p><h2 className="mt-1 font-serif text-2xl text-[#1F4145]">{selectedStore ? selectedStore.store_name : t("Stock requests")}</h2>{!storeId ? <div className="mt-5"><EmptyPanel title={t("Select a store to begin")} description={t("Only requests inside your authorised scope are shown.")} /></div> : !requests.length ? <div className="mt-5"><EmptyPanel title={t("No requests for this store")} description={t("Submitted requests will appear here with their complete approval trail.")} /></div> : <div className="mt-5 space-y-3">{requests.map((request) => { const action = actionFor(request); return <article key={request.id} className="rounded-xl border border-[#E4DED2] bg-[#FAF8F2] p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold text-[#315156]">{t("Request")} #{request.id} · {request.request_date}</p><p className="mt-1 text-sm text-[#536762]">{request.notes || t("No notes")}</p></div><StatusBadge status={request.status} /></div><ul className="mt-3 space-y-1 text-sm text-[#62736E]">{(request.items || []).map((item: Row) => <li key={item.id}><strong>{item.item_name}</strong>: {item.requested_quantity} {item.unit} · {t("left")}: {item.quantity_left} · {t("verified")}: {item.verified_quantity ?? "—"} · {t("approved")}: {item.assistant_approved_quantity ?? "—"}</li>)}</ul>{request.approval_events?.length ? <p className="mt-3 text-xs text-[#71807A]">{request.approval_events.map((entry: Row) => `${statusLabel(entry.stage, t)} · ${entry.decision_by}`).join("  |  ")}</p> : null}{action ? <Button disabled={saving} onClick={() => void moveRequest(request, action.action)} className="mt-4 bg-[#0F7667] text-white"><CheckCircle2 size={16} /> {action.label}</Button> : null}</article>; })}</div>}</section>
    </div>}
  </AppShell>;
}
