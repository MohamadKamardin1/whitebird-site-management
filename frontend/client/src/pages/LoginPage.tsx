/** Coastal Ledger authentication page: a controlled operational entry with explicit scope, responsibility, and White Bird identity. */
import { FormEvent, useEffect, useState } from "react";
import { Link, useLocation } from "wouter";
import { ArrowRight, Eye, EyeOff, Loader2, MapPin, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { readableApiError } from "@/lib/api";
import { brandLogo, loginOperationsImage } from "@/lib/assets";

const LOGO = brandLogo;
const LOGIN_ILLUSTRATION = loginOperationsImage;

function BrandLockup({ light = false }: { light?: boolean }) {
  return <span className={`inline-flex items-center gap-3 ${light ? "text-white" : "text-[#16383B]"}`}>
    <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FDFBF6] shadow-[0_10px_30px_rgba(27,51,50,.12)]"><img src={LOGO} alt="" className="h-9 w-9 object-contain" /></span>
    <span className="leading-tight"><strong className="block text-[13px] font-extrabold uppercase tracking-[.18em]">White Bird</strong><span className={`mt-1 block text-[10px] font-bold uppercase tracking-[.13em] ${light ? "text-[#B4D6D0]" : "text-[#53706E]"}`}>Zanzibar operational ledger</span></span>
  </span>;
}

export default function LoginPage() {
  const [, navigate] = useLocation();
  const { status, signIn } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (status === "authenticated") navigate("/"); }, [navigate, status]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setSubmitting(true); setError(null);
    try { await signIn(String(form.get("email") || ""), String(form.get("password") || "")); navigate("/"); }
    catch (caught) { setError(readableApiError(caught).message); }
    finally { setSubmitting(false); }
  }

  return <div className="min-h-screen bg-[#F8F5EC] p-3 sm:p-5"><div className="relative mx-auto grid min-h-[calc(100vh-1.5rem)] max-w-[1640px] overflow-hidden rounded-[28px] border border-[#D8D1C2] bg-[#FFFCF5] lg:grid-cols-[1.12fr_.88fr] sm:min-h-[calc(100vh-2.5rem)]">
    <div className="relative hidden overflow-hidden lg:block"><img src={LOGIN_ILLUSTRATION} alt="White Bird site team completing an operations handover at a Zanzibar property" className="absolute inset-0 h-full w-full object-cover" /><div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(249,246,237,.94)_0%,rgba(249,246,237,.62)_43%,rgba(10,43,48,.1)_100%)]" />
      <div className="absolute inset-x-0 top-0 p-10"><BrandLockup /><div className="tide-line mt-7 max-w-md" /><div className="mt-4 flex items-center gap-3 text-[10px] font-extrabold uppercase tracking-[.14em] text-[#4B716F]"><MapPin size={13} className="text-[#0F7667]" /> Site standards · people · accountability</div></div>
      <div className="absolute bottom-0 left-0 max-w-xl p-10"><p className="ledger-label text-[#0F7667]">Daily work register · 01</p><h1 className="mt-3 font-serif text-5xl leading-[.98] tracking-[-.045em] text-[#11393D]">Every standard has an owner. Every day has a clear next step.</h1><p className="mt-5 max-w-md text-[15px] leading-7 text-[#426060]">Coordinate attendance, inspections, stock, issues, and reports through one role-aware command layer.</p><div className="mt-7 grid max-w-md grid-cols-3 border-y border-[#77A9A0]/60 py-3"><LedgerMeta label="Scope" value="Policy-bound" /><LedgerMeta label="Evidence" value="Traceable" /><LedgerMeta label="Handover" value="Accountable" /></div></div>
    </div>
    <div className="relative flex items-center justify-center px-5 py-12 sm:px-10 lg:px-16"><div className="w-full max-w-[420px]"><div className="mb-9 lg:hidden"><BrandLockup /></div><div className="tide-line mb-5 w-16 bg-[#0F7667]" /><p className="ledger-label text-[#0F7667]">Controlled entry · secure sign in</p><h2 className="mt-2 font-serif text-4xl tracking-[-.035em] text-[#183A3E]">Start with today’s work.</h2><p className="mt-3 text-[15px] leading-6 text-[#65736F]">Your sign-in opens only the sites, tasks, and approvals assigned to your White Bird role.</p>
      <div className="mt-6 grid grid-cols-3 divide-x divide-[#DED7C9] rounded-xl border border-[#E2DBCE] bg-[#FAF8F1] px-2 py-3"><LedgerMeta label="Role" value="Verified" /><LedgerMeta label="Scope" value="Assigned" /><LedgerMeta label="Session" value="Protected" /></div>
      <form className="mt-7 space-y-5" onSubmit={submit}><div className="grid gap-2"><Label htmlFor="email" className="text-[#294A4D]">Email address</Label><Input id="email" name="email" type="email" autoComplete="email" placeholder="you@whitebird.co.tz" required className="h-12 border-[#D8D1C4] bg-white px-4 shadow-sm focus-visible:ring-[#0F7667]" /></div><div className="grid gap-2"><div className="flex items-center justify-between"><Label htmlFor="password" className="text-[#294A4D]">Password</Label><a href="#account-support" className="text-xs font-bold text-[#0F7667] hover:underline">Need help?</a></div><div className="relative"><Input id="password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" required className="h-12 border-[#D8D1C4] bg-white px-4 pr-12 shadow-sm focus-visible:ring-[#0F7667]" /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6D7F7B] hover:text-[#0F7667]">{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></div>{error && <div className="rounded-xl border border-[#F0C5B8] bg-[#FFF5F1] px-4 py-3 text-sm leading-5 text-[#98412B]">{error}</div>}<Button type="submit" disabled={submitting || status === "checking"} className="h-12 w-full bg-[#0F7667] text-base font-bold text-white shadow-[0_10px_20px_rgba(15,118,103,.18)] transition-transform active:scale-[.98] hover:bg-[#0B6155]">{submitting || status === "checking" ? <Loader2 className="animate-spin" size={18} /> : <>Enter your assigned workspace <ArrowRight size={18} /></>}</Button></form>
      <div className="mt-7 flex items-start gap-3 rounded-xl border border-[#D5E5DE] bg-[#F2F8F4] p-3.5 text-xs leading-5 text-[#487068]"><ShieldCheck className="mt-0.5 shrink-0 text-[#0F7667]" size={18} />The White Bird API checks your role, permissions, and accessible sites before it returns operational data.</div><p id="account-support" className="mt-7 text-center text-xs text-[#7A8580]">Account support and password reset are managed through your White Bird administrator.</p></div></div>
  </div></div>;
}

function LedgerMeta({ label, value }: { label: string; value: string }) { return <span className="px-3 text-center first:pl-0 last:pr-0"><span className="block text-[9px] font-extrabold uppercase tracking-[.13em] text-[#77908B]">{label}</span><strong className="mt-1 block text-[10px] uppercase tracking-[.08em] text-[#365B5C]">{value}</strong></span>; }
