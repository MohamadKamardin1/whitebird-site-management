import { useCallback, useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
// @ts-expect-error Mapbox Draw ships JavaScript-first types in some bundlers.
import MapboxDraw from "@mapbox/mapbox-gl-draw";
import "mapbox-gl/dist/mapbox-gl.css";
import "@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css";
import { Building2, MapPinned, Plus, RefreshCw, Save, ShieldAlert, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { AppShell } from "@/components/AppShell";
import { EmptyPanel, LoadingPanel, WorkspaceHeader } from "@/components/WorkspacePrimitives";
import { api, asPaginated, readableApiError } from "@/lib/api";

type Row = Record<string, any>;
const fieldClass = "h-10 border-[#D8D2C5] bg-white";

function ErrorMessage({ error }: { error: unknown }) {
  return <p className="rounded-lg bg-[#FBE4DD] px-3 py-2 text-sm text-[#9D3D28]">{readableApiError(error).message}</p>;
}

export default function AdminEstatePage() {
  const [zones, setZones] = useState<Row[]>([]);
  const [sites, setSites] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [mapboxToken, setMapboxToken] = useState("");
  const [tokenNotice, setTokenNotice] = useState("");
  const [zoneDraft, setZoneDraft] = useState({ name: "", code: "", description: "" });
  const [siteDraft, setSiteDraft] = useState({ name: "", zone_id: "", city: "", region: "", latitude: "", longitude: "" });
  const [selectedZone, setSelectedZone] = useState<Row | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [zoneData, siteData] = await Promise.all([api.get("/zones?page_size=100"), api.get("/sites?page_size=100")]);
      setZones(asPaginated(zoneData).results);
      setSites(asPaginated(siteData).results);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshMapToken = useCallback(async () => {
    try {
      const settings = await api.get<Row>("/integrations/settings");
      const token = String(settings.mapbox_public_token || "");
      setMapboxToken(token);
      setTokenNotice(token ? "" : "The integration settings endpoint returned no Mapbox token.");
    } catch (caught) {
      setMapboxToken("");
      setTokenNotice(`Could not load the Mapbox token (${readableApiError(caught).message}).`);
    }
  }, []);

  useEffect(() => {
    void load();
    void refreshMapToken();
  }, [load, refreshMapToken]);

  async function createZone() {
    setSaving(true);
    setError(null);
    try {
      await api.post("/zones", zoneDraft);
      setZoneDraft({ name: "", code: "", description: "" });
      setMessage("Zone created. You can now draw its boundary and assign sites.");
      await load();
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  async function createSite() {
    setSaving(true);
    setError(null);
    try {
      await api.post("/sites", {
        name: siteDraft.name,
        zone_id: siteDraft.zone_id ? Number(siteDraft.zone_id) : null,
        city: siteDraft.city,
        region: siteDraft.region,
        latitude: siteDraft.latitude ? Number(siteDraft.latitude) : null,
        longitude: siteDraft.longitude ? Number(siteDraft.longitude) : null,
      });
      setSiteDraft({ name: "", zone_id: "", city: "", region: "", latitude: "", longitude: "" });
      setMessage("Site created with its configured site store and ready-made cleanliness survey areas.");
      await load();
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  async function updateSite(site: Row, patch: Row) {
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/sites/${site.id}`, patch);
      setMessage("Site configuration saved and audited.");
      await load();
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  async function deactivateSite(site: Row) {
    if (!window.confirm(`Deactivate ${site.name}? Historical records will remain preserved.`)) return;
    setSaving(true);
    setError(null);
    try {
      await api.delete(`/sites/${site.id}`);
      setMessage("Site deactivated; historical data remains protected.");
      await load();
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
        title="Sites, zones, and geographic control"
        description="Configure the operating estate, assign every site to a zone, and maintain an auditable geographic view. Daily site-operation actions remain outside this administrator workspace."
        actions={
          <Button variant="outline" className="bg-[#FFFDF8]" onClick={() => { void load(); void refreshMapToken(); }}>
            <RefreshCw size={16} /> Refresh
          </Button>
        }
      />
      {error ? <div className="mb-5"><ErrorMessage error={error} /></div> : null}
      {message ? <p className="mb-5 rounded-lg bg-[#E5F0EC] px-3 py-2 text-sm text-[#175F55]">{message}</p> : null}
      {tokenNotice ? <p className="mb-5 rounded-lg bg-[#FBE4DD] px-3 py-2 text-sm text-[#9D3D28]">{tokenNotice}</p> : null}
      <div className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]">
        <section className="space-y-5">
          <EstateCreateCard
            title="Create a zone"
            icon={<MapPinned size={18} />}
            fields={
              <>
                <Input className={fieldClass} placeholder="Zone name" value={zoneDraft.name} onChange={(event) => setZoneDraft({ ...zoneDraft, name: event.target.value })} />
                <Input className={fieldClass} placeholder="Code e.g. UNGUJA-N" value={zoneDraft.code} onChange={(event) => setZoneDraft({ ...zoneDraft, code: event.target.value })} />
                <Textarea className="border-[#D8D2C5] bg-white" placeholder="Zone definition and management notes" value={zoneDraft.description} onChange={(event) => setZoneDraft({ ...zoneDraft, description: event.target.value })} />
              </>
            }
            onSubmit={() => void createZone()}
            disabled={!zoneDraft.name || !zoneDraft.code || saving}
            label="Create zone"
          />
          <EstateCreateCard
            title="Create a site"
            icon={<Building2 size={18} />}
            fields={
              <>
                <Input className={fieldClass} placeholder="Site name" value={siteDraft.name} onChange={(event) => setSiteDraft({ ...siteDraft, name: event.target.value })} />
                <select className="h-10 rounded-md border border-[#D8D2C5] bg-white px-3 text-sm" value={siteDraft.zone_id} onChange={(event) => setSiteDraft({ ...siteDraft, zone_id: event.target.value })}>
                  <option value="">Assign zone later</option>
                  {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name} · {zone.code}</option>)}
                </select>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Input className={fieldClass} placeholder="City" value={siteDraft.city} onChange={(event) => setSiteDraft({ ...siteDraft, city: event.target.value })} />
                  <Input className={fieldClass} placeholder="Region" value={siteDraft.region} onChange={(event) => setSiteDraft({ ...siteDraft, region: event.target.value })} />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Input className={fieldClass} type="number" placeholder="Latitude" value={siteDraft.latitude} onChange={(event) => setSiteDraft({ ...siteDraft, latitude: event.target.value })} />
                  <Input className={fieldClass} type="number" placeholder="Longitude" value={siteDraft.longitude} onChange={(event) => setSiteDraft({ ...siteDraft, longitude: event.target.value })} />
                </div>
              </>
            }
            onSubmit={() => void createSite()}
            disabled={!siteDraft.name || saving}
            label="Create site"
          />
        </section>

        <ZoneMap
          token={mapboxToken}
          zones={zones}
          sites={sites}
          selectedZone={selectedZone}
          onSelectZone={setSelectedZone}
          onRetryToken={() => void refreshMapToken()}
          onSaveBoundary={async (zoneId, boundary) => {
            setSaving(true);
            try {
              await api.patch(`/zones/${zoneId}`, { boundary });
              setMessage("Zone boundary saved and audited.");
              await load();
            } catch (caught) {
              setError(caught);
            } finally {
              setSaving(false);
            }
          }}
        />
      </div>

      <section className="mt-5 rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="ledger-label text-[#0F7667]">Configuration register</p>
            <h2 className="mt-1 font-serif text-2xl text-[#1F4145]">Zones and sites</h2>
            <p className="mt-2 text-sm text-[#687671]">All changes are administrator-only, soft-deactivated where applicable, and preserved for audit review.</p>
          </div>
          <ShieldAlert className="text-[#D17837]" size={22} />
        </div>
        {loading ? (
          <LoadingPanel label="Loading estate configuration" />
        ) : (
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div>
              <h3 className="font-semibold text-[#315156]">Zones</h3>
              {zones.length === 0 ? (
                <EmptyPanel title="No zones configured" description="Create the first geographic management zone." />
              ) : (
                <div className="mt-3 space-y-3">
                  {zones.map((zone) => (
                    <div key={zone.id} className={`rounded-xl border p-4 ${selectedZone?.id === zone.id ? "border-[#0F7667] bg-[#F0F7F4]" : "border-[#E4DED2] bg-[#FAF8F2]"}`}>
                      <button className="w-full text-left" onClick={() => setSelectedZone(zone)}>
                        <div className="flex items-center justify-between">
                          <p className="font-semibold text-[#315156]">{zone.name} · {zone.code}</p>
                          <span className="text-xs text-[#62736E]">{zone.site_count || 0} sites</span>
                        </div>
                        <p className="mt-1 text-xs text-[#71807A]">{zone.description || "No definition recorded."}</p>
                      </button>
                      <div className="mt-3 flex gap-2">
                        <Button size="sm" variant="outline" className="bg-white" onClick={() => setSelectedZone(zone)}>
                          <MapPinned size={14} /> Draw boundary
                        </Button>
                        {zone.is_active ? (
                          <Button size="sm" variant="outline" className="bg-white" disabled={saving} onClick={() => void api.delete(`/zones/${zone.id}`).then(() => load()).catch(setError)}>
                            <Trash2 size={14} /> Deactivate
                          </Button>
                        ) : (
                          <span className="self-center text-xs text-[#A13E26]">Inactive</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <h3 className="font-semibold text-[#315156]">Sites</h3>
              {sites.length === 0 ? (
                <EmptyPanel title="No sites configured" description="Create a site to begin the operating estate." />
              ) : (
                <div className="mt-3 space-y-3">
                  {sites.map((site) => (
                    <SiteRow key={site.id} site={site} zones={zones} onSave={updateSite} onDeactivate={deactivateSite} disabled={saving} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </section>
    </AppShell>
  );
}

function EstateCreateCard({ title, icon, fields, onSubmit, disabled, label }: { title: string; icon: React.ReactNode; fields: React.ReactNode; onSubmit: () => void; disabled: boolean; label: string }) {
  return (
    <section className="rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8] p-5">
      <div className="flex items-center gap-2 text-[#0F7667]">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#E5F0EC]">{icon}</span>
        <h2 className="font-serif text-xl text-[#1F4145]">{title}</h2>
      </div>
      <div className="mt-4 grid gap-3">
        {fields}
        <Button disabled={disabled} onClick={onSubmit} className="bg-[#0F7667] text-white hover:bg-[#0B6155]">
          <Plus size={16} /> {label}
        </Button>
      </div>
    </section>
  );
}

function SiteRow({ site, zones, onSave, onDeactivate, disabled }: { site: Row; zones: Row[]; onSave: (site: Row, patch: Row) => void; onDeactivate: (site: Row) => void; disabled: boolean }) {
  const [name, setName] = useState(site.name || "");
  const [zoneId, setZoneId] = useState(site.zone_id ? String(site.zone_id) : "");
  const [latitude, setLatitude] = useState(site.latitude ?? "");
  const [longitude, setLongitude] = useState(site.longitude ?? "");
  return (
    <div className="rounded-xl border border-[#E4DED2] bg-[#FAF8F2] p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Input className={fieldClass} value={name} onChange={(event) => setName(event.target.value)} />
        <select className="h-10 rounded-md border border-[#D8D2C5] bg-white px-3 text-sm" value={zoneId} onChange={(event) => setZoneId(event.target.value)}>
          <option value="">Unassigned zone</option>
          {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
        </select>
        <Input className={fieldClass} type="number" placeholder="Latitude" value={latitude} onChange={(event) => setLatitude(event.target.value)} />
        <Input className={fieldClass} type="number" placeholder="Longitude" value={longitude} onChange={(event) => setLongitude(event.target.value)} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" disabled={disabled} onClick={() => onSave(site, { name, zone_id: zoneId ? Number(zoneId) : null, latitude: latitude === "" ? null : Number(latitude), longitude: longitude === "" ? null : Number(longitude) })}>
          <Save size={14} /> Save site
        </Button>
        <Button size="sm" variant="outline" className="bg-white" disabled={disabled || !site.is_active} onClick={() => onDeactivate(site)}>
          <Trash2 size={14} /> Deactivate
        </Button>
        <span className="self-center text-xs text-[#71807A]">{site.city || ""} {site.region ? `· ${site.region}` : ""}</span>
      </div>
    </div>
  );
}

function ZoneMap({ token, zones, sites, selectedZone, onSelectZone, onRetryToken, onSaveBoundary }: {
  token: string;
  zones: Row[];
  sites: Row[];
  selectedZone: Row | null;
  onSelectZone: (zone: Row) => void;
  onRetryToken: () => void;
  onSaveBoundary: (zoneId: number, boundary: Row) => Promise<void>;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const drawRef = useRef<any>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const selectedZoneRef = useRef<Row | null>(selectedZone);
  const onSaveBoundaryRef = useRef(onSaveBoundary);
  const [mapError, setMapError] = useState("");

  useEffect(() => {
    selectedZoneRef.current = selectedZone;
  }, [selectedZone]);

  useEffect(() => {
    onSaveBoundaryRef.current = onSaveBoundary;
  }, [onSaveBoundary]);

  const renderMarkers = (map: mapboxgl.Map) => {
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = sites
      .filter((site) => site.latitude != null && site.longitude != null)
      .map((site) => {
        const marker = new mapboxgl.Marker({ color: "#D17837" })
          .setLngLat([Number(site.longitude), Number(site.latitude)])
          .setPopup(new mapboxgl.Popup().setHTML(`<strong>${site.name}</strong><br/>${site.city || ""}`));
        marker.addTo(map);
        return marker;
      });
  };

  // Create the map once a token is available. The map <div> is always mounted,
  // so ref.current is always present and a late-arriving token still initialises it.
  useEffect(() => {
    if (!token) {
      setMapError("Mapbox is not configured. A system administrator can add the public token under Integration settings.");
      return;
    }
    setMapError("");
    if (mapRef.current) return; // already initialised
    if (!ref.current) return; // wait one render for the container

    mapboxgl.accessToken = token;
    const map = new mapboxgl.Map({ container: ref.current, style: "mapbox://styles/mapbox/streets-v12", center: [39.2, -6.16], zoom: 7 });
    map.addControl(new mapboxgl.NavigationControl(), "top-right");
    const draw = new MapboxDraw({ displayControlsDefault: false, controls: { polygon: true, trash: true } });
    map.addControl(draw, "top-left");

    const commitBoundary = (event: any) => {
      const zone = selectedZoneRef.current;
      if (zone && event.features?.[0]) void onSaveBoundaryRef.current(zone.id, event.features[0].geometry);
    };
    map.on("draw.create", commitBoundary);
    map.on("draw.update", commitBoundary);
    map.on("load", () => renderMarkers(map));

    mapRef.current = map;
    drawRef.current = draw;

    return () => {
      map.remove();
      mapRef.current = null;
      drawRef.current = null;
      markersRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Refresh site markers whenever the site list changes after the map is ready.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !token) return;
    if (map.loaded()) renderMarkers(map);
    else map.once("load", () => renderMarkers(map));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sites, token]);

  // Draw the selected zone's saved boundary.
  useEffect(() => {
    if (!drawRef.current || !selectedZone?.boundary?.coordinates) return;
    drawRef.current.deleteAll();
    drawRef.current.add({ type: "Feature", properties: {}, geometry: selectedZone.boundary });
  }, [selectedZone]);

  return (
    <section className="overflow-hidden rounded-2xl border border-[#DDD7CA] bg-[#FFFDF8]">
      <div className="border-b border-[#E7E1D6] p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="ledger-label text-[#0F7667]">GIS awareness</p>
            <h2 className="mt-1 font-serif text-2xl text-[#1F4145]">Zone boundaries and site markers</h2>
            <p className="mt-2 text-sm leading-6 text-[#687671]">Select a zone, draw or edit its boundary, and use site markers to verify geographic coverage.</p>
          </div>
          <MapPinned className="text-[#0F7667]" size={22} />
        </div>
        {selectedZone ? (
          <p className="mt-3 rounded-lg bg-[#E5F0EC] px-3 py-2 text-xs text-[#175F55]">
            Editing <strong>{selectedZone.name}</strong>. Draw the polygon; every update is saved through the audited administrator endpoint.
          </p>
        ) : null}
      </div>
      <div className="relative">
        {/* Always mounted so the effect can initialise once a token arrives. */}
        <div ref={ref} className="h-[480px] w-full" />
        {!token ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#FBF6EC]/90 p-6">
            <div className="w-full max-w-md rounded-xl border border-[#EADFC3] bg-white p-5 text-center shadow-sm">
              <p className="text-sm leading-6 text-[#9D3D28]">
                Mapbox is not configured. A system administrator can add the public token under Integration settings.
              </p>
              <button
                onClick={onRetryToken}
                className="mt-3 inline-flex items-center gap-2 rounded-md bg-[#0F7667] px-3 py-1.5 text-sm font-semibold text-white hover:bg-[#0B6155]"
              >
                <RefreshCw size={14} /> Retry token
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
