/** Coastal Ledger workflow composer: concise, validated forms that submit to real White Bird API actions. */
import { FormEvent, useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, readableApiError } from "@/lib/api";

export type ActionKind = "issue" | "cleaner" | "inspection" | "stock_request" | "general_report";
const copy: Record<ActionKind, { label: string; title: string; description: string }> = {
  issue: { label: "Raise issue", title: "Raise a site issue", description: "Create an operational issue for a permitted site. Prioritise clarity so the next reviewer can act without delay." },
  cleaner: { label: "Register cleaner", title: "Register a cleaner", description: "Start the cleaner registry workflow. Identity verification remains a separate documented review action." },
  inspection: { label: "Start inspection", title: "Start a field inspection", description: "Open a draft inspection against a permitted site, area, and active inspection template." },
  stock_request: { label: "Create stock request", title: "Create a stock request", description: "Create a draft request for one store item. The backend controls review, approval, and completion." },
  general_report: { label: "Generate management report", title: "Generate a management report", description: "Generate the general report for a selected reporting date. The reporting chain remains permission-controlled." },
};

export function ActionComposer({ kind, onComplete }: { kind: ActionKind; onComplete?: () => void }) {
  const [open, setOpen] = useState(false); const [submitting, setSubmitting] = useState(false); const [error, setError] = useState<string | null>(null); const config = copy[kind];
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const fields = new FormData(event.currentTarget); const value = (name: string) => String(fields.get(name) || "").trim(); const number = (name: string) => Number(value(name)); let endpoint = ""; let payload: Record<string, unknown> = {};
    if (kind === "issue") { endpoint = "/issues"; payload = { title: value("title"), description: value("description"), site_id: number("site_id"), priority: value("priority"), issue_category: value("issue_category"), source: "manual" }; }
    if (kind === "cleaner") { endpoint = "/cleaners"; payload = { first_name: value("first_name"), last_name: value("last_name"), phone_number: value("phone_number"), gender: value("gender"), nationality: value("nationality") }; }
    if (kind === "inspection") { endpoint = "/inspections"; payload = { site_id: number("site_id"), area_id: number("area_id"), template_id: number("template_id"), inspection_date: value("inspection_date") || undefined, shift_id: value("shift_id") ? number("shift_id") : undefined, notes: value("notes") }; }
    if (kind === "stock_request") { endpoint = `/stores/${number("store_id")}/requests`; payload = { request_date: value("request_date") || undefined, notes: value("notes"), items: [{ store_item_id: number("store_item_id"), requested_quantity: number("requested_quantity"), notes: value("item_notes") }] }; }
    if (kind === "general_report") { endpoint = "/reports/general/generate"; payload = { report_date: value("report_date") }; }
    setSubmitting(true); setError(null);
    try { await api.post(endpoint, payload); setOpen(false); onComplete?.(); } catch (caught) { setError(readableApiError(caught).message); } finally { setSubmitting(false); }
  }
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button className="bg-[#0F7667] text-white hover:bg-[#0B6155]"><Plus size={16} /> {config.label}</Button></DialogTrigger><DialogContent className="max-h-[90vh] overflow-y-auto border-[#DDD5C7] bg-[#FFFDF8] sm:max-w-lg"><DialogHeader><p className="ledger-label text-[#0F7667]">Authorised action</p><DialogTitle className="font-serif text-3xl text-[#193D41]">{config.title}</DialogTitle><DialogDescription className="leading-6 text-[#61706B]">{config.description}</DialogDescription></DialogHeader><form className="mt-3 space-y-4" onSubmit={submit}>{kind === "cleaner" && <CleanerFields />}{kind === "issue" && <IssueFields />}{kind === "inspection" && <InspectionFields />}{kind === "stock_request" && <StockRequestFields />}{kind === "general_report" && <Field label="Report date" name="report_date" type="date" required />}{error && <p className="rounded-lg bg-[#FBE4DD] px-3 py-2 text-sm text-[#9D3D28]">{error}</p>}<div className="flex justify-end gap-2 pt-2"><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" disabled={submitting} className="bg-[#0F7667] text-white hover:bg-[#0B6155]">{submitting && <Loader2 className="animate-spin" size={16} />} Submit action</Button></div></form></DialogContent></Dialog>;
}

function CleanerFields() { return <><div className="grid gap-4 sm:grid-cols-2"><Field label="First name" name="first_name" required /><Field label="Last name" name="last_name" required /></div><Field label="Phone number" name="phone_number" required /><div className="grid gap-4 sm:grid-cols-2"><SelectField label="Gender" name="gender" values={["female", "male", "other"]} /><Field label="Nationality" name="nationality" /></div></>; }
function IssueFields() { return <><Field label="Issue title" name="title" required /><div className="grid gap-4 sm:grid-cols-2"><Field label="Site ID" name="site_id" type="number" required /><SelectField label="Priority" name="priority" values={["low", "medium", "high", "urgent"]} defaultValue="medium" /></div><SelectField label="Category" name="issue_category" values={["maintenance", "cleaning", "safety", "security", "stock", "other"]} defaultValue="maintenance" /><TextAreaField label="Context" name="description" /></>; }
function InspectionFields() { return <><div className="grid gap-4 sm:grid-cols-2"><Field label="Site ID" name="site_id" type="number" required /><Field label="Area ID" name="area_id" type="number" required /></div><div className="grid gap-4 sm:grid-cols-2"><Field label="Template ID" name="template_id" type="number" required /><Field label="Inspection date" name="inspection_date" type="date" /></div><Field label="Shift ID (if applicable)" name="shift_id" type="number" /><TextAreaField label="Inspection notes" name="notes" /></>; }
function StockRequestFields() { return <><Field label="Store ID" name="store_id" type="number" required /><div className="grid gap-4 sm:grid-cols-2"><Field label="Store item ID" name="store_item_id" type="number" required /><Field label="Requested quantity" name="requested_quantity" type="number" required /></div><Field label="Request date" name="request_date" type="date" /><TextAreaField label="Request notes" name="notes" /><TextAreaField label="Item notes" name="item_notes" /></>; }
function Field({ label, name, type = "text", required = false }: { label: string; name: string; type?: string; required?: boolean }) { return <div className="grid gap-2"><Label htmlFor={name}>{label}{required && <span className="ml-1 text-[#B54B2E]">*</span>}</Label><Input id={name} name={name} type={type} required={required} min={type === "number" ? "0" : undefined} className="border-[#D8D2C5] bg-white" /></div>; }
function TextAreaField({ label, name }: { label: string; name: string }) { return <div className="grid gap-2"><Label htmlFor={name}>{label}</Label><Textarea id={name} name={name} className="min-h-20 border-[#D8D2C5] bg-white" /></div>; }
function SelectField({ label, name, values, defaultValue }: { label: string; name: string; values: string[]; defaultValue?: string }) { return <div className="grid gap-2"><Label>{label}</Label><Select name={name} defaultValue={defaultValue || values[0]}><SelectTrigger className="border-[#D8D2C5] bg-white"><SelectValue /></SelectTrigger><SelectContent>{values.map((value) => <SelectItem key={value} value={value}>{value.replaceAll("_", " ")}</SelectItem>)}</SelectContent></Select></div>; }
