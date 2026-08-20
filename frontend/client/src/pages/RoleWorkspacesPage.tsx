import { useState } from "react";
import { ArrowDownToLine, ArrowRight, FileSpreadsheet, Loader2, Save, Settings2, ShieldCheck, UploadCloud, UsersRound, Warehouse } from "lucide-react";
import { Link } from "wouter";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiErrorPanel } from "@/components/WorkspacePrimitives";
import { useLanguage } from "@/contexts/LanguageContext";
import { api, readableApiError } from "@/lib/api";
import { isIndividualCleanerRegistrationReady } from "@/lib/cleanerRegistration";

type Mode = "hr" | "store" | "admin";
const roleCopy: Record<Mode, { eyebrow: string; title: string; description: string }> = {
  hr: { eyebrow: "People operations", title: "A workforce register with a clear next step for every cleaner.", description: "Own onboarding, identity evidence, trainee progress, assignment integrity, and qualification decisions from one HR control room." },
  store: { eyebrow: "Supply operations", title: "Keep every configured store ready for the workday.", description: "Review reorder risks, stock requests, fulfillment handovers, and movement evidence without mixing inventory ownership into site execution." },
  admin: { eyebrow: "Platform administration", title: "Configure the operating estate without entering daily site work.", description: "Manage users, roles, sites, zones, shifts, permission governance, and audit controls from a dedicated administration boundary." },
};
const fieldClass = "h-10 border-[#D8D2C5] bg-white";

function Field({ label, required = false, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return <label className="grid gap-2"><Label>{label}{required ? <span className="ml-1 text-[#B14B35]">*</span> : null}</Label>{children}</label>;
}

function IndividualCleanerRegistration() {
  const { t } = useLanguage();
  const blank = { first_name: "", last_name: "", id_type: "nida", id_number: "", birth_date: "", gender: "unspecified", living_location: "", phone_number: "", near_person_name: "", near_person_relationship: "", near_person_phone: "", notes: "" };
  const [form, setForm] = useState(blank);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const update = (key: keyof typeof blank, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const canSave = isIndividualCleanerRegistrationReady(form);

  async function submit() {
    setSaving(true); setError(null); setMessage("");
    try {
      await api.post("/cleaners", form);
      setForm(blank);
      setMessage(t("Cleaner registered as trainee. Continue with site assignment and trainee programme setup."));
    } catch (caught) { setError(caught); } finally { setSaving(false); }
  }

  return <section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 sm:p-6">
    <div className="flex items-start gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#E5F1ED] text-[#0F7667]"><UsersRound size={20} /></span><div><p className="ledger-label text-[#0F7667]">{t("Individual onboarding")}</p><h2 className="font-serif text-2xl text-[#21464A]">{t("Register one cleaner")}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t("Record identity and contact information now. Each new cleaner starts as a trainee and can be assigned to a site afterward.")}</p></div></div>
    {error ? <div className="mt-4"><ApiErrorPanel error={error} onRetry={() => setError(null)} /></div> : null}
    {message ? <p className="mt-4 rounded-xl bg-[#E5F0EC] px-4 py-3 text-sm text-[#175F55]">{message}</p> : null}
    <div className="mt-5 grid gap-4 sm:grid-cols-2"><Field label={t("First name")} required><Input className={fieldClass} value={form.first_name} onChange={(event) => update("first_name", event.target.value)} /></Field><Field label={t("Last name")} required><Input className={fieldClass} value={form.last_name} onChange={(event) => update("last_name", event.target.value)} /></Field><Field label={t("ID type")} required><select className={fieldClass + " w-full rounded-md px-3 text-sm"} value={form.id_type} onChange={(event) => update("id_type", event.target.value)}><option value="nida">NIDA</option><option value="zanzibar_id">Zanzibar ID</option><option value="birth_certificate">Birth certificate</option></select></Field><Field label={t("ID number")} required><Input className={fieldClass} value={form.id_number} onChange={(event) => update("id_number", event.target.value)} /></Field><Field label={t("Birth date")} required><Input className={fieldClass} type="date" value={form.birth_date} onChange={(event) => update("birth_date", event.target.value)} /></Field><Field label={t("Gender")}><select className={fieldClass + " w-full rounded-md px-3 text-sm"} value={form.gender} onChange={(event) => update("gender", event.target.value)}><option value="unspecified">{t("Not specified")}</option><option value="female">{t("Female")}</option><option value="male">{t("Male")}</option><option value="other">{t("Other")}</option></select></Field><Field label={t("Living location")}><Input className={fieldClass} value={form.living_location} onChange={(event) => update("living_location", event.target.value)} /></Field><Field label={t("Phone number")}><Input className={fieldClass} value={form.phone_number} onChange={(event) => update("phone_number", event.target.value)} placeholder="+255..." /></Field></div>
    <div className="mt-5 border-t border-[#E5DED3] pt-5"><p className="ledger-label text-[#71807A]">{t("Emergency contact")}</p><div className="mt-3 grid gap-4 sm:grid-cols-3"><Field label={t("Contact name")}><Input className={fieldClass} value={form.near_person_name} onChange={(event) => update("near_person_name", event.target.value)} /></Field><Field label={t("Relationship")}><Input className={fieldClass} value={form.near_person_relationship} onChange={(event) => update("near_person_relationship", event.target.value)} /></Field><Field label={t("Contact phone")}><Input className={fieldClass} value={form.near_person_phone} onChange={(event) => update("near_person_phone", event.target.value)} placeholder="+255..." /></Field></div></div>
    <div className="mt-5"><Field label={t("Notes")}><Textarea className="min-h-20 bg-white" value={form.notes} onChange={(event) => update("notes", event.target.value)} /></Field></div>
    <Button disabled={!canSave || saving} className="mt-5 bg-[#0F7667] text-white hover:bg-[#0B6155]" onClick={() => void submit()}>{saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}{t("Register cleaner")}</Button>
  </section>;
}

function BulkWorkbookOnboarding() {
  const { t } = useLanguage();
  const [file, setFile] = useState<File | null>(null); const [preview, setPreview] = useState<Record<string, unknown> | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null);
  async function previewWorkbook() { if (!file) return; const form = new FormData(); form.append("workbook", file); setBusy(true); setError(null); try { setPreview(await api.post<Record<string, unknown>>("/hr/cleaners/import/preview", form)); } catch (caught) { setError(caught); } finally { setBusy(false); } }
  async function commitWorkbook() { if (!file || !preview || Number(preview.rejected_rows || 0) > 0) return; const form = new FormData(); form.append("workbook", file); setBusy(true); setError(null); try { setPreview(await api.post<Record<string, unknown>>("/hr/cleaners/import", form)); } catch (caught) { setError(caught); } finally { setBusy(false); } }
  return <section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 sm:p-6"><div className="flex items-start gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#E5F1ED] text-[#0F7667]"><FileSpreadsheet size={20} /></span><div><p className="ledger-label text-[#0F7667]">{t("Bulk onboarding")}</p><h2 className="font-serif text-2xl text-[#21464A]">{t("Validated cleaner workbook")}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t("Download the protected template, complete the validated dropdown fields, preview every row, and commit only after all errors are corrected. New cleaners enter White Bird as trainees.")}</p></div></div>{error ? <div className="mt-4"><ApiErrorPanel error={error} onRetry={() => setError(null)} /></div> : null}<div className="mt-5 flex flex-wrap gap-2"><a href="/api/site-management/v1/hr/cleaners/template.xlsx" download><Button variant="outline" className="bg-white"><ArrowDownToLine size={16} /> {t("Download template")}</Button></a><label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-md bg-[#0F7667] px-4 text-sm font-semibold text-white hover:bg-[#0B6155]"><UploadCloud size={16} /> {t("Select workbook")}<input className="sr-only" type="file" accept=".xlsx" onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); }} /></label></div>{file ? <div className="mt-4 rounded-xl border border-[#DDE8E2] bg-[#F5FAF7] p-3 text-sm text-[#315B56]">{t("Selected")} <strong>{file.name}</strong><div className="mt-3 flex gap-2"><Button size="sm" variant="outline" className="bg-white" onClick={() => void previewWorkbook()} disabled={busy}>{busy ? <Loader2 className="animate-spin" size={15} /> : <ShieldCheck size={15} />}{t("Preview rows")}</Button><Button size="sm" className="bg-[#0F7667] text-white" onClick={() => void commitWorkbook()} disabled={busy || !preview || Number(preview.rejected_rows || 0) > 0}>{t("Commit accepted rows")}</Button></div></div> : null}{preview ? <div className="mt-4 grid gap-2 sm:grid-cols-3">{[[t("Rows"), preview.total_rows], [t("Accepted"), preview.accepted_rows], [t("Rejected"), preview.rejected_rows]].map(([label, value]) => <div className="rounded-lg border border-[#E5DED3] bg-[#FAF8F2] p-3" key={String(label)}><p className="ledger-label text-[#71807A]">{String(label)}</p><p className="mt-1 font-serif text-2xl text-[#21464A]">{String(value)}</p></div>)}</div> : null}</section>;
}

export default function RoleWorkspacesPage({ mode }: { mode: Mode }) {
  const { t } = useLanguage();
  const copy = roleCopy[mode];
  return <AppShell><div className="space-y-7"><div><p className="ledger-label text-[#0F7667]">{t(copy.eyebrow)}</p><h1 className="mt-2 max-w-3xl font-serif text-4xl tracking-[-.04em] text-[#173B3E]">{t(copy.title)}</h1><p className="mt-3 max-w-3xl text-sm leading-7 text-[#60736E]">{t(copy.description)}</p></div>
    {mode === "hr" && <><div className="grid gap-5 xl:grid-cols-2"><IndividualCleanerRegistration /><BulkWorkbookOnboarding /></div><section className="rounded-2xl border border-[#DDD7CA] bg-[#0B3540] p-5 text-white sm:p-6"><p className="ledger-label text-[#82C8BC]">{t("HR queue")}</p><h2 className="mt-1 font-serif text-2xl">{t("Move people through the right gate.")}</h2><div className="mt-5 grid gap-2 md:grid-cols-3"><Link href="/hr/people" className="flex items-center justify-between rounded-lg bg-white/[.08] p-3 text-sm"><span className="flex items-center gap-2"><UsersRound size={16} /> {t("People registry")}</span><ArrowRight size={15} /></Link><Link href="/hr/assignments" className="flex items-center justify-between rounded-lg bg-white/[.08] p-3 text-sm"><span>{t("Assignments and shifts")}</span><ArrowRight size={15} /></Link><Link href="/trainees" className="flex items-center justify-between rounded-lg bg-white/[.08] p-3 text-sm"><span>{t("Trainee qualification queue")}</span><ArrowRight size={15} /></Link></div><p className="mt-5 text-xs leading-5 text-[#C0D6D2]">{t("Qualification is never inferred from an import. A final evaluation and verified identity remain required before activation.")}</p></section></>}
    {mode === "store" && <div className="grid gap-5 md:grid-cols-3"><Link href="/stores" className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 hover:border-[#9ECFC4]"><Warehouse className="text-[#0F7667]" /><h2 className="mt-4 font-serif text-2xl text-[#21464A]">{t("Inventory register")}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t("Review configured stores, item thresholds, counts, and movement history.")}</p></Link><Link href="/stores" className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 hover:border-[#9ECFC4]"><ShieldCheck className="text-[#0F7667]" /><h2 className="mt-4 font-serif text-2xl text-[#21464A]">{t("Request review")}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t("Process site requests, approve quantities, and keep handovers visible.")}</p></Link><Link href="/reports" className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 hover:border-[#9ECFC4]"><ArrowRight className="text-[#0F7667]" /><h2 className="mt-4 font-serif text-2xl text-[#21464A]">{t("Supply reporting")}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t("See stock risk and fulfillment evidence in the reporting chain.")}</p></Link></div>}
    {mode === "admin" && <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{[["Users & roles", "/admin/users", "Create, revoke, and assign platform roles."], ["Sites & zones", "/sites", "Configure the operating estate and zone relationships."], ["Shifts", "/sites", "Define site working modes and shift rules."], ["Audit and reports", "/reports", "Review governance evidence and handover status."], ["Integration settings", "/admin/integrations", "Securely configure DeepSeek and Mapbox for the platform."]].map(([label, href, description]) => <Link href={href} key={label} className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 hover:border-[#9ECFC4]"><Settings2 className="text-[#0F7667]" /><h2 className="mt-4 font-serif text-2xl text-[#21464A]">{t(label)}</h2><p className="mt-2 text-sm leading-6 text-[#687874]">{t(description)}</p></Link>)}</div>}
  </div></AppShell>;
}
