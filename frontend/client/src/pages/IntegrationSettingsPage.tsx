import { useEffect, useState } from "react";
import { Eye, EyeOff, KeyRound, Loader2, Save, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiErrorPanel, WorkspaceHeader } from "@/components/WorkspacePrimitives";
import { api, readableApiError } from "@/lib/api";

type Settings = {
  deepseek_configured: boolean;
  deepseek_key_suffix: string;
  mapbox_public_token: string;
};

export default function IntegrationSettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [deepseekKey, setDeepseekKey] = useState("");
  const [mapboxToken, setMapboxToken] = useState("");
  const [showDeepseek, setShowDeepseek] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<Settings>("/integrations/settings");
      setSettings(result);
      setMapboxToken(result.mapbox_public_token || "");
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function save() {
    setSaving(true);
    setError(null);
    setMessage("");
    try {
      const result = await api.patch<Settings>("/integrations/settings", {
        ...(deepseekKey.trim() ? { deepseek_api_key: deepseekKey.trim() } : {}),
        mapbox_public_token: mapboxToken.trim(),
      });
      setSettings(result);
      setDeepseekKey("");
      setMapboxToken(result.mapbox_public_token || "");
      setMessage("Integration settings saved and recorded in the audit trail.");
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <WorkspaceHeader
        eyebrow="System administration"
        title="Integration settings"
        description="Configure the service connections used by the White Bird AI Optimization Engine and GIS workspace. DeepSeek remains server-only; Mapbox is a public browser token and should be restricted by URL in Mapbox."
      />
      {error ? <div className="mb-5"><ApiErrorPanel error={error} onRetry={() => void load()} /></div> : null}
      {message ? <p className="mb-5 rounded-xl border border-[#BFDAD2] bg-[#F0F8F4] px-4 py-3 text-sm text-[#28564E]">{message}</p> : null}
      {loading ? <div className="rounded-2xl border border-dashed border-[#D5CFC2] bg-[#FCFAF5] p-8 text-center"><Loader2 className="mx-auto animate-spin text-[#0F7667]" size={24} /><p className="mt-3 text-sm text-[#62736E]">Loading integration configuration.</p></div> : <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(300px,.85fr)]">
        <section className="min-w-0 rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5 shadow-[0_8px_24px_rgba(24,51,48,.035)] sm:p-6">
          <div className="flex items-start gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#E5F0EC] text-[#0F7667]"><KeyRound size={20} /></span><div className="min-w-0"><p className="ledger-label text-[#0F7667]">Connection control</p><h2 className="font-serif text-2xl text-[#21464A]">Provider credentials</h2><p className="mt-2 text-sm leading-6 text-[#687874]">Only system administrators can update these values. Existing DeepSeek credentials are never returned to the browser after saving.</p></div></div>
          <div className="mt-6 grid gap-5">
            <div className="grid gap-2"><label className="text-sm font-semibold text-[#315156]" htmlFor="deepseek-key">DeepSeek API key</label><div className="flex min-w-0 gap-2"><Input id="deepseek-key" type={showDeepseek ? "text" : "password"} autoComplete="new-password" value={deepseekKey} onChange={(event) => setDeepseekKey(event.target.value)} placeholder={settings?.deepseek_configured ? `Configured · ending ${settings.deepseek_key_suffix}` : "sk-…"} className="min-w-0 border-[#D8D2C5] bg-white" /><Button type="button" variant="outline" size="icon" className="shrink-0 bg-white" onClick={() => setShowDeepseek((value) => !value)} aria-label={showDeepseek ? "Hide DeepSeek API key" : "Show DeepSeek API key"}>{showDeepseek ? <EyeOff size={16} /> : <Eye size={16} />}</Button></div><p className="text-xs leading-5 text-[#71807A]">Leave blank to keep the current server-side key. The value is masked in responses and never displayed in the UI.</p></div>
            <div className="grid gap-2"><label className="text-sm font-semibold text-[#315156]" htmlFor="mapbox-token">Mapbox public token</label><Input id="mapbox-token" type="text" autoComplete="off" value={mapboxToken} onChange={(event) => setMapboxToken(event.target.value)} placeholder="pk.…" className="border-[#D8D2C5] bg-white" /><p className="text-xs leading-5 text-[#71807A]">Use a `pk.` token restricted to your production domain and the required Mapbox styles/draw scopes.</p></div>
            <Button disabled={saving} onClick={() => void save()} className="w-full bg-[#0F7667] text-white hover:bg-[#0B6155] sm:w-auto"><Save size={16} /> {saving ? "Saving configuration…" : "Save integration settings"}</Button>
          </div>
        </section>
        <aside className="min-w-0 rounded-2xl border border-[#D5E5DF] bg-[#F0F8F4] p-5 sm:p-6"><ShieldCheck className="text-[#0F7667]" size={22} /><h2 className="mt-4 font-serif text-2xl text-[#21464A]">Safe operating boundary</h2><div className="mt-4 space-y-3 text-sm leading-6 text-[#416A62]"><p>DeepSeek is used only by the server-side optimization engine. It is not sent to the browser, report preview, or client logs.</p><p>Mapbox is intentionally a public client token, but it should be restricted in the Mapbox console. Every settings save records the actor and whether each integration was configured without storing raw secret values in the audit record.</p><p>After saving, reload the GIS workspace and refresh the AI Optimization Engine to use the latest configuration.</p></div></aside>
      </div>}
    </AppShell>
  );
}
