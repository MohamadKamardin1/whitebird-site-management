import { ArrowRight, Check, ChevronRight, CircleDot, Compass, Layers3, LockKeyhole, Menu, Orbit, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import { Link } from "wouter";
import { brandMark, coastalContours } from "@/lib/assets";

const workflowCards = [
  { icon: Compass, eyebrow: "01 / Scope", title: "Know what is yours to act on.", body: "Role-aware access keeps sites, zones, people, and decisions in the right operational context." },
  { icon: Workflow, eyebrow: "02 / Work", title: "Move daily work without guesswork.", body: "Attendance, inspections, issues, jobs, stock, and reports follow visible backend-controlled states." },
  { icon: ShieldCheck, eyebrow: "03 / Review", title: "Make evidence easy to trust.", body: "Submissions, exceptions, supporting documents, and review actions stay connected to the work item." },
];

const capabilities = [
  ["People and assignments", "Keep cleaner, trainee, role, shift, and site relationships understandable."],
  ["Attendance and inspections", "Turn daily routines and quality standards into accountable review flows."],
  ["Issues, jobs, and stock", "Give operational risk a clear owner, priority, evidence, and next action."],
  ["Reporting and notifications", "Keep handovers visible from site-level work through management oversight."],
];

export default function MarketingPage() {
  return (
    <main className="marketing-page min-h-screen overflow-hidden bg-[#F7F3EA] text-[#173B3E]">
      <header className="relative z-20 mx-auto flex max-w-[1440px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
        <a href="#top" className="marketing-lockup" aria-label="White Bird Zanzibar home">
          <span className="marketing-mark"><img src={brandMark} alt="" /></span>
          <span><strong>White Bird</strong><small>Zanzibar operations</small></span>
        </a>
        <nav className="hidden items-center gap-7 text-sm font-bold text-[#496260] lg:flex" aria-label="Marketing navigation">
          <a href="#platform" className="transition-colors hover:text-[#0F7667]">Platform</a>
          <a href="#workflows" className="transition-colors hover:text-[#0F7667]">Workflows</a>
          <a href="#roles" className="transition-colors hover:text-[#0F7667]">For every role</a>
          <a href="#trust" className="transition-colors hover:text-[#0F7667]">Trust layer</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login" className="hidden rounded-full px-4 py-2 text-sm font-bold text-[#335554] transition-colors hover:bg-[#E9E4D8] sm:inline-flex">Sign in</Link>
          <Link href="/login" className="marketing-button marketing-button-dark">Open workspace <ArrowRight size={15} /></Link>
          <button className="marketing-mobile-menu" type="button" aria-label="Open navigation"><Menu size={20} /></button>
        </div>
      </header>

      <section id="top" className="relative mx-auto grid min-h-[710px] max-w-[1440px] items-center gap-10 px-5 pb-20 pt-8 sm:px-8 lg:grid-cols-[.83fr_1.17fr] lg:px-12 lg:pb-28 lg:pt-12">
        <div className="relative z-10 max-w-[620px]">
          <p className="marketing-kicker"><span className="marketing-kicker-dot" /> Operational clarity, site by site</p>
          <h1 className="marketing-display">The operating layer for teams that keep every site moving.</h1>
          <p className="marketing-lede">White Bird brings people, schedules, standards, stock, issues, and reporting into one role-aware workspace built for the rhythm of real site operations.</p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/login" className="marketing-button marketing-button-primary">Enter operations <ArrowRight size={16} /></Link>
            <a href="#platform" className="marketing-text-link">See how the layer works <ChevronRight size={15} /></a>
          </div>
          <div className="marketing-hero-meta mt-10"><span><LockKeyhole size={15} /> Backend-authorised</span><span><CircleDot size={15} /> Scope-aware</span><span><Sparkles size={15} /> Evidence-led</span></div>
        </div>

        <div className="marketing-hero-stage" aria-label="Abstract 3D visualization of the White Bird operations layer" role="img">
          <div className="marketing-orbit marketing-orbit-one" /><div className="marketing-orbit marketing-orbit-two" />
          <div className="marketing-map-slab"><span /><span /><span /><span /><span /></div>
          <div className="marketing-3d-panel marketing-panel-primary"><div className="marketing-panel-top"><span className="marketing-panel-icon"><Layers3 size={15} /></span><span className="marketing-panel-label">Live work layer</span><span className="marketing-live-dot" /></div><strong>Every responsibility has a place.</strong><div className="marketing-mini-bars"><i /><i /><i /><i /></div><small>sites / people / standards / handover</small></div>
          <div className="marketing-3d-panel marketing-panel-secondary"><span className="marketing-panel-icon marketing-panel-icon-light"><ShieldCheck size={14} /></span><div><small>Review state</small><strong>Evidence connected</strong></div><Check size={17} /></div>
          <div className="marketing-3d-panel marketing-panel-tertiary"><span className="marketing-panel-icon marketing-panel-icon-warm"><CircleDot size={14} /></span><div><small>Daily pulse</small><strong>Next action visible</strong></div></div>
          <div className="marketing-hero-glow" />
        </div>
      </section>

      <section id="platform" className="marketing-section marketing-section-dark"><div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[.75fr_1.25fr] lg:px-12 lg:py-32"><div><p className="marketing-kicker marketing-kicker-light"><span className="marketing-kicker-dot" /> One layer, many workstreams</p><h2 className="marketing-heading marketing-heading-light">Complex operations should feel composed.</h2><p className="marketing-copy marketing-copy-light">White Bird is designed around accountability, not administrative noise. The platform turns the movement between a site, a person, a standard, and a decision into a visible chain of work.</p><a href="#workflows" className="marketing-button marketing-button-outline mt-8">Explore the workflow <ArrowRight size={15} /></a></div><div className="grid gap-4 sm:grid-cols-2">{workflowCards.map(({ icon: Icon, eyebrow, title, body }) => <article className="marketing-dark-card" key={eyebrow}><span className="marketing-dark-icon"><Icon size={18} /></span><p className="marketing-card-eyebrow">{eyebrow}</p><h3>{title}</h3><p>{body}</p></article>)}</div></div></section>

      <section id="workflows" className="marketing-section"><div className="mx-auto max-w-[1440px] px-5 py-24 sm:px-8 lg:px-12 lg:py-32"><div className="max-w-2xl"><p className="marketing-kicker"><span className="marketing-kicker-dot" /> Built around the daily handover</p><h2 className="marketing-heading">The work is connected before it is reported.</h2><p className="marketing-copy">Start with the next responsible action. Keep context close. Let the API-controlled workflow decide what can move, what needs review, and what must stay protected.</p></div><div className="marketing-capability-grid mt-14">{capabilities.map(([title, body], index) => <article className="marketing-capability" key={title}><span>0{index + 1}</span><h3>{title}</h3><p>{body}</p><ArrowRight size={18} /></article>)}</div></div></section>

      <section id="roles" className="marketing-role-section"><div className="mx-auto grid max-w-[1440px] items-center gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[1fr_1fr] lg:px-12 lg:py-32"><div className="marketing-role-visual"><div className="marketing-role-card marketing-role-card-back"><small>Management viewer</small><strong>See the chain.</strong><span>Read-only oversight</span></div><div className="marketing-role-card marketing-role-card-front"><small>Site supervisor</small><strong>Move the day.</strong><span>Attendance · issues · checks</span></div><div className="marketing-role-stamp">ROLE<br />AWARE</div></div><div><p className="marketing-kicker"><span className="marketing-kicker-dot" /> Made for the whole operating rhythm</p><h2 className="marketing-heading">Simple for the person doing the work. Clear for the person reviewing it.</h2><p className="marketing-copy">White Bird gives each role a useful view of the same operational truth. The interface stays approachable for daily users while preserving the scope, permissions, and evidence managers need.</p><div className="marketing-check-list"><span><Check size={16} /> System administration</span><span><Check size={16} /> General and zone supervision</span><span><Check size={16} /> Site operations</span><span><Check size={16} /> Management oversight</span></div></div></div></section>

      <section id="trust" className="marketing-trust-section"><div className="mx-auto max-w-[1440px] px-5 py-24 text-center sm:px-8 lg:px-12 lg:py-32"><span className="marketing-trust-icon"><ShieldCheck size={24} /></span><p className="marketing-kicker justify-center"><span className="marketing-kicker-dot" /> A deliberate trust layer</p><h2 className="marketing-heading mx-auto max-w-3xl">Authority stays with the backend. Clarity stays with the interface.</h2><p className="marketing-copy mx-auto max-w-2xl">Role-aware screens guide the user, but Django remains the source of authorization. Tokens, signed private files, review states, and scope checks are handled as operational controls, not decorative promises.</p><div className="mt-10 flex flex-wrap justify-center gap-3"><span className="marketing-trust-pill">Django Ninja API</span><span className="marketing-trust-pill">Scoped access</span><span className="marketing-trust-pill">Reviewable evidence</span><span className="marketing-trust-pill">Production Docker path</span></div></div></section>

      <footer className="marketing-footer"><div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-5 py-10 sm:px-8 md:flex-row md:items-end md:justify-between lg:px-12"><div><a href="#top" className="marketing-lockup marketing-lockup-footer"><span className="marketing-mark"><img src={brandMark} alt="" /></span><span><strong>White Bird</strong><small>Zanzibar operations</small></span></a><p className="mt-4 max-w-sm text-sm leading-6 text-[#AFC9C5]">A clear operating layer for teams accountable for every site, person, standard, and handover.</p></div><div className="flex flex-wrap gap-4 text-sm font-bold text-[#D7E5E2]"><a href="#platform">Platform</a><a href="#workflows">Workflows</a><a href="#trust">Trust layer</a><Link href="/login">Sign in</Link></div><p className="text-xs text-[#78938F]">© White Bird Zanzibar operations</p></div></footer>
    </main>
  );
}

void coastalContours;
