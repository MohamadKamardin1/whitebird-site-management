/** Coastal Ledger fallback page: users can always return to a known operational entry point. */
import { Link } from "wouter";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
export default function NotFound() { return <main className="coastal-shell flex min-h-screen items-center justify-center bg-[#F6F2E9] p-6"><section className="max-w-lg rounded-3xl border border-[#D8D1C4] bg-[#FFFDF8] p-9 text-center shadow-[0_20px_60px_rgba(14,50,54,.1)]"><p className="ledger-label text-[#0F7667]">Route not found</p><h1 className="mt-3 font-serif text-5xl tracking-[-.04em] text-[#173B3E]">This path has no assigned work.</h1><p className="mt-4 text-sm leading-6 text-[#697772]">Return to your White Bird command centre to continue with an operational workspace.</p><Button asChild className="mt-7 bg-[#0F7667] text-white hover:bg-[#0B6155]"><Link href="/"><ArrowLeft size={16} /> Return to today</Link></Button></section></main>; }
