import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { Crosshair, Loader2, MapPin, Pencil, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, readableApiError } from "@/lib/api";

type Coordinates = { latitude: string; longitude: string };

const ZANZIBAR_DEFAULT: [number, number] = [39.2083, -6.1659];

function readCoordinate(latitude: string, longitude: string): [number, number] | null {
  const lat = Number(latitude);
  const lng = Number(longitude);
  return Number.isFinite(lat) && Number.isFinite(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180 ? [lng, lat] : null;
}

function coordinateText(value: Coordinates) {
  const position = readCoordinate(value.latitude, value.longitude);
  return position ? `${Number(value.latitude).toFixed(6)}, ${Number(value.longitude).toFixed(6)}` : "No point selected";
}

export function SiteLocationPickerControl({ token, latitude, longitude, onChange, compact = false }: {
  token: string;
  latitude: string;
  longitude: string;
  onChange: (coordinates: Coordinates) => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<Coordinates>({ latitude, longitude });
  const [runtimeToken, setRuntimeToken] = useState(token);
  const [loadingMap, setLoadingMap] = useState(false);
  const [mapError, setMapError] = useState("");
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markerRef = useRef<mapboxgl.Marker | null>(null);
  const selected = readCoordinate(latitude, longitude);

  useEffect(() => { setRuntimeToken(token); }, [token]);

  useEffect(() => {
    if (!open) return;
    setPending({ latitude, longitude });
  }, [open, latitude, longitude]);

  useEffect(() => {
    if (!open || loadingMap || !runtimeToken || !mapContainer.current) return;
    mapboxgl.accessToken = runtimeToken;
    const initialPosition = readCoordinate(latitude, longitude) || ZANZIBAR_DEFAULT;
    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: initialPosition,
      zoom: selected ? 15 : 10,
    });
    map.addControl(new mapboxgl.NavigationControl(), "top-right");
    mapRef.current = map;

    const setPoint = (lngLat: mapboxgl.LngLat) => {
      markerRef.current?.remove();
      const marker = new mapboxgl.Marker({ color: "#0F7667", draggable: true }).setLngLat(lngLat).addTo(map);
      marker.on("dragend", () => setPoint(marker.getLngLat()));
      markerRef.current = marker;
      setPending({ latitude: lngLat.lat.toFixed(6), longitude: lngLat.lng.toFixed(6) });
    };
    if (selected) setPoint(new mapboxgl.LngLat(selected[0], selected[1]));
    map.on("click", (event) => setPoint(event.lngLat));
    map.once("load", () => { setMapError(""); window.requestAnimationFrame(() => map.resize()); });
    map.on("error", (event) => {
      const detail = String(event.error?.message || "");
      if (/token|unauthori[sz]ed|forbidden|access denied/i.test(detail)) setMapError("Mapbox rejected the configured public token. Check its domain and style permissions in Integration settings.");
    });

    return () => {
      markerRef.current?.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, [open, runtimeToken, loadingMap, latitude, longitude]);

  const apply = () => {
    if (!readCoordinate(pending.latitude, pending.longitude)) return;
    onChange(pending);
    setOpen(false);
  };

  const openPicker = async () => {
    setMapError("");
    setLoadingMap(true);
    setOpen(true);
    try {
      const latest = await api.get<{ mapbox_public_token?: string }>("/integrations/settings");
      const refreshedToken = String(latest.mapbox_public_token || token || "").trim();
      if (!refreshedToken) throw new Error("No Mapbox public token is saved in Integration settings.");
      setRuntimeToken(refreshedToken);
    } catch (caught) {
      setMapError(readableApiError(caught).message);
    } finally {
      setLoadingMap(false);
    }
  };

  return <>
    <div className={`flex items-center justify-between gap-3 rounded-xl border border-[#D7E3DE] bg-[#F6FBF9] ${compact ? "p-3" : "p-3.5"}`}>
      <div className="min-w-0"><p className="text-xs font-extrabold uppercase tracking-[.12em] text-[#0F7667]">Site location</p><p className="mt-1 truncate font-mono text-xs text-[#56706C]">{coordinateText({ latitude, longitude })}</p><p className="mt-1 text-[11px] leading-4 text-[#718681]">Click a point or drag the pin to set the exact site position.</p></div>
      <Button type="button" variant={selected ? "outline" : "default"} onClick={() => void openPicker()} className={selected ? "shrink-0 border-[#BBDAD2] bg-white text-[#0F7667]" : "shrink-0 bg-[#0F7667] text-white hover:bg-[#0B6155]"}>
        {selected ? <Pencil size={15} /> : <MapPin size={15} />}{selected ? "Edit pin" : "Pick location"}
      </Button>
    </div>
    {!token && <p className="mt-2 text-xs text-[#718681]">The latest Mapbox credential is checked when you open the picker.</p>}
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="w-[calc(100vw-1rem)] max-w-3xl overflow-hidden rounded-2xl p-0 sm:w-full">
        <DialogHeader className="border-b border-[#E1E8E4] px-5 pb-4 pt-5 sm:px-6"><DialogTitle className="font-serif text-2xl text-[#1A4144]">Pick site location</DialogTitle><DialogDescription>Click the exact point on the map. Drag the pin if you need to correct it before saving.</DialogDescription></DialogHeader>
        <div className="p-3 sm:p-5"><div className="relative"><div ref={mapContainer} className="h-[420px] max-h-[56dvh] w-full overflow-hidden rounded-xl border border-[#D5E4DE]" />{(loadingMap || mapError) && <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-[#F9FCFA]/95 p-5"><div className="max-w-sm text-center">{loadingMap ? <><Loader2 className="mx-auto animate-spin text-[#0F7667]" size={26} /><p className="mt-3 text-sm font-semibold text-[#315C56]">Loading your configured Mapbox map…</p></> : <><p className="text-sm font-semibold text-[#9D3D28]">{mapError}</p><Button type="button" variant="outline" className="mt-4 bg-white" onClick={() => void openPicker()}><RefreshCw size={15} /> Reload map credential</Button></>}</div></div>}</div><div className="mt-3 flex items-center gap-2 rounded-lg bg-[#EAF5F1] px-3 py-2 text-xs font-semibold text-[#27635B]"><Crosshair size={14} /><span className="font-mono">{coordinateText(pending)}</span></div></div>
        <DialogFooter className="border-t border-[#E1E8E4] px-5 py-4 sm:px-6"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button type="button" disabled={!readCoordinate(pending.latitude, pending.longitude)} onClick={apply} className="bg-[#0F7667] text-white hover:bg-[#0B6155]"><MapPin size={16} /> Use this location</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </>;
}
