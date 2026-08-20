import {
  ArrowLeftRight,
  Boxes,
  Building2,
  ClipboardList,
  Loader2,
  PackagePlus,
  RefreshCw,
  Save,
  Warehouse,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { EmptyPanel, LoadingPanel, StatusBadge, WorkspaceHeader } from "@/components/WorkspacePrimitives";
import { api, asPaginated, readableApiError } from "@/lib/api";

type Row = Record<string, any>;
type Pane = "overview" | "catalogue" | "stores" | "transfers";

const inputClass = "h-10 border-[#D8D2C5] bg-white";
const selectClass = "h-10 w-full rounded-md border border-[#D8D2C5] bg-white px-3 text-sm text-[#294A4D]";
const emptyProduct = { product_name: "", product_code: "", unit: "piece", category: "", current_unit_cost: "" };
const emptyStore = { store_name: "", store_type: "site", site_id: "", parent_store_id: "", location: "" };

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="grid gap-2"><Label>{label}</Label>{children}</label>;
}

function money(value: unknown) {
  const numeric = Number(value || 0);
  return new Intl.NumberFormat("en-TZ", { style: "currency", currency: "TZS", maximumFractionDigits: 0 }).format(numeric);
}

export default function StoreControlPage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [pane, setPane] = useState<Pane>("overview");
  const [stores, setStores] = useState<Row[]>([]);
  const [sites, setSites] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [storeItems, setStoreItems] = useState<Row[]>([]);
  const [transfers, setTransfers] = useState<Row[]>([]);
  const [usage, setUsage] = useState<Row[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState("");
  const [productForm, setProductForm] = useState(emptyProduct);
  const [storeForm, setStoreForm] = useState(emptyStore);
  const [itemForm, setItemForm] = useState({ product_id: "", opening_stock: "0", minimum_stock_level: "0" });
  const [openingForm, setOpeningForm] = useState({ store_item_id: "", opening_month: new Date().toISOString().slice(0, 7) + "-01", opening_quantity: "0", unit_cost: "0" });
  const [transferForm, setTransferForm] = useState({ source_item_id: "", destination_item_id: "", quantity: "", unit_cost: "", notes: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const centralRole = user?.role === "system_admin" || user?.role === "store_manager";

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [storeData, siteData, productData, transferData, usageData] = await Promise.all([
        api.get("/stores?page_size=100"),
        api.get("/sites?page_size=100"),
        api.get("/company-products?page_size=100"),
        api.get("/stock-transfers?page_size=25"),
        api.get("/inventory/usage-trends"),
      ]);
      const nextStores = asPaginated(storeData).results as Row[];
      setStores(nextStores);
      setSites(asPaginated(siteData).results as Row[]);
      setProducts(asPaginated(productData).results as Row[]);
      setTransfers(asPaginated(transferData).results as Row[]);
      setUsage(Array.isArray(usageData) ? usageData as Row[] : []);
      setSelectedStoreId((current) => current || (nextStores[0] ? String(nextStores[0].id) : ""));
      const itemGroups = await Promise.all(nextStores.map(async (store) => {
        const result = await api.get(`/stores/${store.id}/items`);
        return (Array.isArray(result) ? result : asPaginated(result).results).map((item: Row) => ({ ...item, store_name: store.store_name, store_type: store.store_type }));
      }));
      setStoreItems(itemGroups.flat());
    } catch (caught) { setError(caught); } finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const activeStore = stores.find((store) => String(store.id) === selectedStoreId);
  const activeItems = storeItems.filter((item) => String(item.store_id) === selectedStoreId);
  const productForTransfer = (itemId: string) => storeItems.find((item) => String(item.id) === itemId)?.product_id;

  async function execute(action: () => Promise<void>, success: string) {
    setSaving(true); setError(null); setMessage("");
    try { await action(); setMessage(success); await load(); } catch (caught) { setError(caught); } finally { setSaving(false); }
  }

  const createProduct = () => execute(async () => {
    await api.post("/company-products", { ...productForm, current_unit_cost: Number(productForm.current_unit_cost || 0) });
    setProductForm(emptyProduct);
  }, t("Company product catalogue") + " · " + t("Saved"));

  const createStore = () => execute(async () => {
    await api.post("/stores", {
      ...storeForm,
      site_id: storeForm.site_id ? Number(storeForm.site_id) : null,
      parent_store_id: storeForm.parent_store_id ? Number(storeForm.parent_store_id) : null,
    });
    setStoreForm(emptyStore);
  }, t("Store hierarchy") + " · " + t("Saved"));

  const addProductToStore = () => execute(async () => {
    if (!selectedStoreId) return;
    const product = products.find((row) => String(row.id) === itemForm.product_id);
    await api.post(`/stores/${selectedStoreId}/items`, {
      product_id: Number(itemForm.product_id),
      item_name: product?.product_name || "Company product",
      opening_stock: Number(itemForm.opening_stock || 0),
      minimum_stock_level: Number(itemForm.minimum_stock_level || 0),
    });
    setItemForm({ product_id: "", opening_stock: "0", minimum_stock_level: "0" });
  }, t("Company inventory") + " · " + t("Saved"));

  const recordOpening = () => execute(async () => {
    if (!selectedStoreId) return;
    await api.post(`/stores/${selectedStoreId}/monthly-openings`, {
      ...openingForm,
      store_item_id: Number(openingForm.store_item_id),
      opening_quantity: Number(openingForm.opening_quantity || 0),
      unit_cost: Number(openingForm.unit_cost || 0),
    });
  }, t("Opening balance") + " · " + t("Saved"));

  const recordTransfer = () => execute(async () => {
    await api.post("/stock-transfers", {
      ...transferForm,
      source_item_id: Number(transferForm.source_item_id),
      destination_item_id: Number(transferForm.destination_item_id),
      quantity: Number(transferForm.quantity),
      unit_cost: transferForm.unit_cost ? Number(transferForm.unit_cost) : null,
    });
    setTransferForm({ source_item_id: "", destination_item_id: "", quantity: "", unit_cost: "", notes: "" });
  }, t("Stock transfers") + " · " + t("Saved"));

  const panes: { id: Pane; label: string; icon: typeof Warehouse }[] = [
    { id: "overview", label: t("Weekly usage and value"), icon: ClipboardList },
    { id: "catalogue", label: t("Company products"), icon: Boxes },
    { id: "stores", label: t("Store hierarchy"), icon: Warehouse },
    { id: "transfers", label: t("Stock transfers"), icon: ArrowLeftRight },
  ];

  return <AppShell><WorkspaceHeader
    eyebrow={t("Supply operations")}
    title={t("Company inventory")}
    description={t("Manage company stores, products, stock transfers, opening balances, and usage evidence.")}
    actions={<Button variant="outline" className="bg-[#FFFDF8]" onClick={() => void load()}><RefreshCw size={16} /> {t("Refresh inventory")}</Button>}
  />
    {error ? <p className="mb-5 rounded-xl bg-[#FBE4DD] px-4 py-3 text-sm text-[#9D3D28]">{readableApiError(error).message}</p> : null}
    {message ? <p className="mb-5 rounded-xl bg-[#E5F0EC] px-4 py-3 text-sm text-[#175F55]">{message}</p> : null}
    <div className="mb-5 flex gap-2 overflow-x-auto pb-1">{panes.map((entry) => { const Icon = entry.icon; return <Button key={entry.id} variant={pane === entry.id ? "default" : "outline"} onClick={() => setPane(entry.id)} className={pane === entry.id ? "bg-[#0F7667] text-white" : "bg-[#FFFDF8]"}><Icon size={15} /> {entry.label}</Button>; })}</div>
    {loading ? <LoadingPanel label={t("Refresh inventory")} /> : <div className="space-y-5">
      {pane === "overview" && <>
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[
          [t("Super Store"), stores.filter((store) => store.store_type === "super").length, "#173F43"],
          [t("Power Store"), stores.filter((store) => store.store_type === "power").length, "#0F7667"],
          [t("Site Store"), stores.filter((store) => store.store_type === "site").length, "#D17837"],
          [t("Company products"), products.filter((product) => product.is_active).length, "#765A9A"],
        ].map(([label, value, color]) => <article key={String(label)} className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5"><p className="ledger-label text-[#71807A]">{label}</p><p className="mt-2 font-serif text-4xl" style={{ color: String(color) }}>{String(value)}</p></article>)}</section>
        <section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="ledger-label text-[#0F7667]">{t("Weekly usage and value")}</p><h2 className="mt-1 font-serif text-2xl text-[#21464A]">{t("Stock usage workflow")}</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-[#687874]">{t("Site Supervisor submits → Zone Supervisor verifies → Assistant General Supervisor approves → HR packs and assembles.")}</p></div><StatusBadge status="audited" /></div>{usage.length ? <div className="mt-5 overflow-x-auto"><table className="min-w-[720px] w-full text-sm"><thead className="text-left text-xs uppercase tracking-[.08em] text-[#71807A]"><tr><th className="pb-3">{t("Store name")}</th><th className="pb-3">{t("Product name")}</th><th className="pb-3">{t("Quantity used")}</th><th className="pb-3 text-right">{t("Value used")}</th></tr></thead><tbody className="divide-y divide-[#E8E2D8]">{usage.map((row, index) => <tr key={`${row.store_id}-${row.item_name}-${index}`}><td className="py-3"><p className="font-semibold text-[#315156]">{row.store_name}</p><p className="text-xs text-[#7A8984]">{row.site_name || t("Super Store")}</p></td><td className="py-3 text-[#536762]">{row.item_name}</td><td className="py-3 text-[#536762]">{row.quantity_used} {row.unit}</td><td className="py-3 text-right font-semibold text-[#173F43]">{money(row.value_used)}</td></tr>)}</tbody></table></div> : <div className="mt-5"><EmptyPanel title={t("No usage has been recorded for this period.")} description={t("Stock transfers and store issue records create the weekly company usage picture.")} /></div>}</section>
      </>}
      {pane === "catalogue" && <div className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]"><section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5"><div className="flex items-center gap-2"><PackagePlus size={20} className="text-[#0F7667]" /><h2 className="font-serif text-2xl text-[#21464A]">{t("Create product")}</h2></div><div className="mt-5 grid gap-4"><Field label={t("Product name")}><Input className={inputClass} value={productForm.product_name} onChange={(event) => setProductForm({ ...productForm, product_name: event.target.value })} /></Field><div className="grid gap-3 sm:grid-cols-2"><Field label={t("Product code")}><Input className={inputClass} value={productForm.product_code} onChange={(event) => setProductForm({ ...productForm, product_code: event.target.value })} /></Field><Field label={t("Unit of measure")}><Input className={inputClass} value={productForm.unit} onChange={(event) => setProductForm({ ...productForm, unit: event.target.value })} /></Field></div><div className="grid gap-3 sm:grid-cols-2"><Field label={t("Category")}><Input className={inputClass} value={productForm.category} onChange={(event) => setProductForm({ ...productForm, category: event.target.value })} /></Field><Field label={t("Current unit cost")}><Input className={inputClass} type="number" min="0" value={productForm.current_unit_cost} onChange={(event) => setProductForm({ ...productForm, current_unit_cost: event.target.value })} /></Field></div><Button disabled={!centralRole || saving || !productForm.product_name || !productForm.product_code || !productForm.current_unit_cost} onClick={() => void createProduct()} className="bg-[#0F7667] text-white">{saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}{t("Create product")}</Button></div></section><section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5"><h2 className="font-serif text-2xl text-[#21464A]">{t("Company product catalogue")}</h2>{products.length ? <div className="mt-5 grid gap-3">{products.map((product) => <article key={product.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E4DED2] bg-[#FAF8F2] p-4"><div><p className="font-semibold text-[#315156]">{product.product_name}</p><p className="mt-1 text-xs text-[#71807A]">{product.product_code} · {product.category || "—"} · {product.unit}</p></div><p className="font-serif text-xl text-[#173F43]">{money(product.current_unit_cost)}</p></article>)}</div> : <div className="mt-5"><EmptyPanel title={t("No company products are configured yet.")} description={t("Create each company product once, then allocate it to the appropriate stores.")} /></div>}</section></div>}
      {pane === "stores" && <div className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]"><section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5"><div className="flex items-center gap-2"><Building2 size={20} className="text-[#0F7667]" /><h2 className="font-serif text-2xl text-[#21464A]">{t("Create store")}</h2></div><div className="mt-5 grid gap-4"><Field label={t("Store name")}><Input className={inputClass} value={storeForm.store_name} onChange={(event) => setStoreForm({ ...storeForm, store_name: event.target.value })} /></Field><div className="grid gap-3 sm:grid-cols-2"><Field label={t("Store type")}><select className={selectClass} value={storeForm.store_type} onChange={(event) => setStoreForm({ ...storeForm, store_type: event.target.value })}><option value="super">{t("Super Store")}</option><option value="power">{t("Power Store")}</option><option value="site">{t("Site Store")}</option></select></Field><Field label={t("Parent store")}><select className={selectClass} value={storeForm.parent_store_id} onChange={(event) => setStoreForm({ ...storeForm, parent_store_id: event.target.value })}><option value="">—</option>{stores.filter((store) => store.id !== Number(storeForm.parent_store_id)).map((store) => <option value={store.id} key={store.id}>{store.store_name} · {store.store_type}</option>)}</select></Field></div><Field label={t("Optional site")}><select className={selectClass} value={storeForm.site_id} onChange={(event) => setStoreForm({ ...storeForm, site_id: event.target.value })}><option value="">—</option>{sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></Field><Button disabled={!centralRole || saving || !storeForm.store_name || (storeForm.store_type === "site" && !storeForm.site_id)} onClick={() => void createStore()} className="bg-[#0F7667] text-white">{saving ? <Loader2 size={16} className="animate-spin" /> : <Warehouse size={16} />}{t("Create store")}</Button></div></section><section className="space-y-5"><section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5"><Field label={t("Store hierarchy")}><select className={selectClass} value={selectedStoreId} onChange={(event) => setSelectedStoreId(event.target.value)}><option value="">—</option>{stores.map((store) => <option key={store.id} value={store.id}>{store.store_name} · {store.store_type}{store.site_name ? ` · ${store.site_name}` : ""}</option>)}</select></Field>{activeStore ? <div className="mt-4 rounded-xl bg-[#F3F0E8] p-4"><p className="font-semibold text-[#315156]">{activeStore.store_name}</p><p className="mt-1 text-sm text-[#687874]">{activeStore.store_type} · {activeStore.parent_store_name || "—"} · {activeStore.site_name || t("Company inventory")}</p></div> : <div className="mt-4"><EmptyPanel title={t("No stores are configured yet.")} description={t("Create the distribution hierarchy before allocating products.")} /></div>}</section>{activeStore ? <section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5"><h2 className="font-serif text-2xl text-[#21464A]">{t("Company products")}</h2><div className="mt-4 grid gap-3 sm:grid-cols-3"><Field label={t("Company product catalogue")}><select className={selectClass} value={itemForm.product_id} onChange={(event) => setItemForm({ ...itemForm, product_id: event.target.value })}><option value="">—</option>{products.filter((product) => product.is_active).map((product) => <option key={product.id} value={product.id}>{product.product_name} · {product.unit}</option>)}</select></Field><Field label={t("Opening quantity")}><Input className={inputClass} type="number" min="0" value={itemForm.opening_stock} onChange={(event) => setItemForm({ ...itemForm, opening_stock: event.target.value })} /></Field><Field label={t("Low stock threshold")}><Input className={inputClass} type="number" min="0" value={itemForm.minimum_stock_level} onChange={(event) => setItemForm({ ...itemForm, minimum_stock_level: event.target.value })} /></Field></div><Button className="mt-4 bg-[#0F7667] text-white" disabled={!centralRole || saving || !itemForm.product_id} onClick={() => void addProductToStore()}><PackagePlus size={16} /> {t("Add configured item")}</Button><div className="mt-5 overflow-x-auto"><table className="min-w-[660px] w-full text-sm"><thead className="text-left text-xs uppercase tracking-[.08em] text-[#71807A]"><tr><th className="pb-2">{t("Product name")}</th><th className="pb-2">{t("Current quantity")}</th><th className="pb-2">{t("Current unit cost")}</th><th className="pb-2">{t("Opening balance")}</th></tr></thead><tbody className="divide-y divide-[#E8E2D8]">{activeItems.map((item) => <tr key={item.id}><td className="py-3 font-semibold text-[#315156]">{item.item_name}<span className="ml-2 text-xs font-normal text-[#71807A]">{item.unit}</span></td><td className="py-3">{item.current_stock}</td><td className="py-3">{money(item.unit_cost)}</td><td className="py-3">{item.opening_stock}</td></tr>)}</tbody></table></div><div className="mt-5 rounded-xl border border-dashed border-[#C9D8D2] bg-[#F5FAF8] p-4"><p className="font-semibold text-[#315156]">{t("Record opening balance")}</p><div className="mt-3 grid gap-3 sm:grid-cols-4"><Field label={t("Company product catalogue")}><select className={selectClass} value={openingForm.store_item_id} onChange={(event) => setOpeningForm({ ...openingForm, store_item_id: event.target.value })}><option value="">—</option>{activeItems.map((item) => <option key={item.id} value={item.id}>{item.item_name}</option>)}</select></Field><Field label={t("Opening month")}><Input className={inputClass} type="date" value={openingForm.opening_month} onChange={(event) => setOpeningForm({ ...openingForm, opening_month: event.target.value })} /></Field><Field label={t("Opening quantity")}><Input className={inputClass} type="number" min="0" value={openingForm.opening_quantity} onChange={(event) => setOpeningForm({ ...openingForm, opening_quantity: event.target.value })} /></Field><Field label={t("Current unit cost")}><Input className={inputClass} type="number" min="0" value={openingForm.unit_cost} onChange={(event) => setOpeningForm({ ...openingForm, unit_cost: event.target.value })} /></Field></div><Button className="mt-3 bg-[#0F7667] text-white" disabled={!centralRole || saving || !openingForm.store_item_id} onClick={() => void recordOpening()}><Save size={16} /> {t("Record opening balance")}</Button></div></section> : null}</section></div>}
      {pane === "transfers" && <div className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]"><section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5"><div className="flex items-center gap-2"><ArrowLeftRight size={20} className="text-[#0F7667]" /><h2 className="font-serif text-2xl text-[#21464A]">{t("Record transfer")}</h2></div><div className="mt-5 grid gap-4"><Field label={t("Source item")}><select className={selectClass} value={transferForm.source_item_id} onChange={(event) => setTransferForm({ ...transferForm, source_item_id: event.target.value })}><option value="">—</option>{storeItems.map((item) => <option key={item.id} value={item.id}>{item.store_name} · {item.item_name} ({item.current_stock} {item.unit})</option>)}</select></Field><Field label={t("Destination item")}><select className={selectClass} value={transferForm.destination_item_id} onChange={(event) => setTransferForm({ ...transferForm, destination_item_id: event.target.value })}><option value="">—</option>{storeItems.filter((item) => !transferForm.source_item_id || (item.product_id && item.product_id === productForTransfer(transferForm.source_item_id))).map((item) => <option key={item.id} value={item.id}>{item.store_name} · {item.item_name}</option>)}</select></Field><div className="grid gap-3 sm:grid-cols-2"><Field label={t("Transfer quantity")}><Input className={inputClass} type="number" min="0.01" value={transferForm.quantity} onChange={(event) => setTransferForm({ ...transferForm, quantity: event.target.value })} /></Field><Field label={t("Current unit cost")}><Input className={inputClass} type="number" min="0" value={transferForm.unit_cost} onChange={(event) => setTransferForm({ ...transferForm, unit_cost: event.target.value })} /></Field></div><Field label={t("Notes")}><Textarea className="min-h-24 bg-white" value={transferForm.notes} onChange={(event) => setTransferForm({ ...transferForm, notes: event.target.value })} /></Field><Button disabled={!centralRole || saving || !transferForm.source_item_id || !transferForm.destination_item_id || !transferForm.quantity} onClick={() => void recordTransfer()} className="bg-[#0F7667] text-white">{saving ? <Loader2 size={16} className="animate-spin" /> : <ArrowLeftRight size={16} />}{t("Record transfer")}</Button></div></section><section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5"><h2 className="font-serif text-2xl text-[#21464A]">{t("Stock transfers")}</h2>{transfers.length ? <div className="mt-5 space-y-3">{transfers.map((transfer) => <article key={transfer.id} className="rounded-xl border border-[#E4DED2] bg-[#FAF8F2] p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold text-[#315156]">{transfer.product_name}</p><p className="mt-1 text-sm text-[#60736E]">{transfer.source_store_name} <span className="px-1">→</span> {transfer.destination_store_name}</p></div><p className="font-serif text-xl text-[#173F43]">{transfer.quantity} {transfer.unit}</p></div><div className="mt-3 flex flex-wrap justify-between gap-2 text-xs text-[#71807A]"><span>{transfer.transfer_date}</span><span>{money(transfer.unit_cost)} / {transfer.unit}</span></div></article>)}</div> : <div className="mt-5"><EmptyPanel title={t("No stock transfers are recorded yet.")} description={t("Every Super, Power, or Site Store distribution will appear here with quantity and current value.")} /></div>}</section></div>}
    </div>}
  </AppShell>;
}
