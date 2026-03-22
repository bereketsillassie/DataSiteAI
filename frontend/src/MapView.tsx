import { MapContainer, TileLayer, Marker, Circle, Popup, useMapEvents } from "react-leaflet";
import L from 'leaflet';
import type { Listing } from '@/App'

// ── Fix default marker icon (required for Vite + Leaflet) ─────
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});
L.Marker.prototype.setIcon(DefaultIcon);

// ── Custom glowing marker for selected site ───────────────────
const glowMarker = L.divIcon({
  className: '',
  html: `
    <div style="position:relative;width:20px;height:20px;">
      <div style="
        position:absolute;inset:-10px;border-radius:50%;
        background:rgba(99,102,241,0.12);
        animation:ping 2s cubic-bezier(0,0,0.2,1) infinite;
      "></div>
      <div style="
        position:absolute;inset:-5px;border-radius:50%;
        background:rgba(99,102,241,0.2);
      "></div>
      <div style="
        width:20px;height:20px;border-radius:50%;
        background:linear-gradient(135deg,#818cf8,#6366f1);
        border:2px solid rgba(199,210,254,0.85);
        box-shadow:0 0 0 4px rgba(99,102,241,0.25),0 0 20px rgba(99,102,241,0.7);
      "></div>
    </div>
  `,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

// ── Listing marker — green pin with dollar sign ───────────────
function makeListingIcon(composite: number) {
  // Color: green for high score, amber for mid, red for low
  const color = composite >= 0.7 ? '#10b981' : composite >= 0.5 ? '#f59e0b' : '#ef4444'
  const border = composite >= 0.7 ? '#064e3b' : composite >= 0.5 ? '#451a03' : '#450a0a'
  return L.divIcon({
    className: '',
    html: `
      <div style="
        width:14px;height:14px;border-radius:50%;
        background:${color};
        border:2px solid ${border};
        box-shadow:0 0 6px ${color}99;
      "></div>
    `,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -10],
  })
}

// ── Risk overlay zones (approximate US geographic data) ────────
interface Zone { center: [number, number]; radius: number }
const OVERLAY_ZONES: Record<string, Zone[]> = {
  carbonEmissions: [
    { center: [41.5, -87.8], radius: 280000 }, // Chicago/Midwest industrial belt
    { center: [40.5, -80.5], radius: 250000 }, // Ohio Valley / PA steel
    { center: [29.7, -95.0], radius: 230000 }, // Texas Gulf Coast refineries
    { center: [37.5, -82.0], radius: 200000 }, // Appalachian coal region
    { center: [38.6, -90.2], radius: 200000 }, // St. Louis coal corridor
  ],
  wildfireRisk: [
    { center: [37.5, -119.5], radius: 360000 }, // CA Sierra Nevada
    { center: [44.0, -121.5], radius: 280000 }, // Oregon Cascades
    { center: [47.5, -120.5], radius: 300000 }, // Washington Cascades
    { center: [36.5, -110.0], radius: 400000 }, // Four Corners AZ/NM
    { center: [39.5, -106.5], radius: 260000 }, // Colorado Rockies
    { center: [33.5, -117.5], radius: 220000 }, // Southern California
  ],
  floodZone: [
    { center: [29.5, -90.5], radius: 280000 }, // Louisiana Delta
    { center: [30.2, -81.5], radius: 200000 }, // Florida / Georgia coast
    { center: [25.8, -80.3], radius: 180000 }, // South Florida
    { center: [35.5, -77.5], radius: 200000 }, // NC coastal plain
    { center: [29.8, -95.2], radius: 200000 }, // Houston flood zone
    { center: [32.5, -90.0], radius: 220000 }, // Mississippi River basin
  ],
  seismicHazard: [
    { center: [37.8, -122.3], radius: 200000 }, // SF Bay / Hayward fault
    { center: [34.0, -118.2], radius: 250000 }, // Los Angeles / San Andreas
    { center: [46.0, -123.0], radius: 240000 }, // PNW Cascadia subduction
    { center: [36.5, -89.5], radius: 330000 }, // New Madrid seismic zone
    { center: [40.8, -111.9], radius: 180000 }, // Wasatch Front Utah
    { center: [44.5, -110.8], radius: 180000 }, // Yellowstone caldera
  ],
};

const OVERLAY_STYLES: Record<string, { color: string; fillColor: string }> = {
  carbonEmissions: { color: '#f97316', fillColor: '#f97316' }, // orange
  wildfireRisk:    { color: '#ef4444', fillColor: '#ef4444' }, // red
  floodZone:       { color: '#3b82f6', fillColor: '#3b82f6' }, // blue
  seismicHazard:   { color: '#a855f7', fillColor: '#a855f7' }, // purple
};

// ── Types ─────────────────────────────────────────────────────
interface ActiveOverlays {
  carbonEmissions: boolean
  wildfireRisk: boolean
  floodZone: boolean
  seismicHazard: boolean
}

interface MapViewProps {
  selectedLocation: { lat: number; lng: number } | null;
  onLocationSelect: (lat: number, lng: number) => void;
  activeOverlays: ActiveOverlays;
  listings: Listing[];
}

// ── MapClickHandler — PRESERVED EXACTLY ──────────────────────
function MapClickHandler({ onLocationSelect }: { onLocationSelect: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onLocationSelect(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

// ── Helpers ───────────────────────────────────────────────────
function formatPrice(usd: number | null): string {
  if (!usd) return 'Price N/A'
  if (usd >= 1_000_000) return `$${(usd / 1_000_000).toFixed(1)}M`
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`
  return `$${usd}`
}

function scorePct(val: number | undefined): string {
  return val != null ? `${Math.round(val * 100)}%` : '—'
}

// ── MapView ───────────────────────────────────────────────────
export default function MapView({ selectedLocation, onLocationSelect, activeOverlays, listings }: MapViewProps) {
  const center: [number, number] = [39.8283, -98.5795];

  const usBounds: [[number, number], [number, number]] = [
    [24.396308, -125.0],
    [49.384358, -66.93457],
  ];

  return (
    <MapContainer
      center={center}
      zoom={4}
      minZoom={3}
      maxZoom={14}
      maxBounds={usBounds}
      maxBoundsViscosity={1.0}
      style={{ height: "100%", width: "100%" }}
      zoomControl={false}
    >
      <MapClickHandler onLocationSelect={onLocationSelect} />

      {/* CartoDB Dark Matter — dark tile layer */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        subdomains="abcd"
        maxZoom={19}
      />

      {/* Risk overlay zones — rendered as semi-transparent circles */}
      {(Object.keys(activeOverlays) as Array<keyof ActiveOverlays>)
        .filter((key) => activeOverlays[key])
        .flatMap((key) =>
          (OVERLAY_ZONES[key] ?? []).map((zone, i) => (
            <Circle
              key={`${key}-${i}`}
              center={zone.center}
              radius={zone.radius}
              pathOptions={{
                color: OVERLAY_STYLES[key].color,
                fillColor: OVERLAY_STYLES[key].fillColor,
                fillOpacity: 0.18,
                weight: 1,
                opacity: 0.5,
              }}
            />
          ))
        )}

      {/* Analysis radius ring — shows the ~5km scoring area */}
      {selectedLocation && (
        <Circle
          center={[selectedLocation.lat, selectedLocation.lng]}
          radius={8000}
          pathOptions={{
            color: '#6366f1',
            fillColor: '#6366f1',
            fillOpacity: 0.06,
            weight: 1.5,
            dashArray: '6 5',
            opacity: 0.8,
          }}
        />
      )}

      {/* Land listing markers */}
      {listings.map((listing) => {
        const { lat, lng } = listing.coordinates
        if (!lat || !lng) return null
        const composite = listing.nearest_cell_scores?.composite ?? 0.5
        return (
          <Marker
            key={listing.id}
            position={[lat, lng]}
            icon={makeListingIcon(composite)}
          >
            <Popup
              className="listing-popup"
              maxWidth={220}
            >
              <div style={{ fontFamily: 'monospace', fontSize: '11px', lineHeight: '1.5', color: '#e2e8f0' }}>
                <div style={{ fontWeight: 700, fontSize: '12px', marginBottom: '4px', color: '#38bdf8' }}>
                  {listing.address ?? `${listing.county ?? listing.state} Parcel`}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px', marginBottom: '4px' }}>
                  <span style={{ color: '#94a3b8' }}>Acres</span>
                  <span style={{ fontWeight: 600 }}>{listing.acres?.toFixed(1)}</span>
                  <span style={{ color: '#94a3b8' }}>Price</span>
                  <span style={{ fontWeight: 600, color: '#4ade80' }}>{formatPrice(listing.price_usd)}</span>
                  {listing.price_per_acre && (
                    <>
                      <span style={{ color: '#94a3b8' }}>/acre</span>
                      <span>${Math.round(listing.price_per_acre).toLocaleString()}</span>
                    </>
                  )}
                </div>
                <div style={{ borderTop: '1px solid #334155', paddingTop: '4px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px 8px' }}>
                  <span style={{ color: '#94a3b8' }}>Score</span>
                  <span style={{ color: composite >= 0.7 ? '#10b981' : composite >= 0.5 ? '#f59e0b' : '#ef4444', fontWeight: 700 }}>
                    {scorePct(composite)}
                  </span>
                  <span style={{ color: '#94a3b8' }}>Power</span>
                  <span>{scorePct(listing.nearest_cell_scores?.power)}</span>
                  <span style={{ color: '#94a3b8' }}>Climate</span>
                  <span>{scorePct(listing.nearest_cell_scores?.climate)}</span>
                </div>
                {listing.listing_url && (
                  <a
                    href={listing.listing_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ display: 'block', marginTop: '6px', color: '#818cf8', textDecoration: 'underline', fontSize: '10px' }}
                  >
                    View listing →
                  </a>
                )}
              </div>
            </Popup>
          </Marker>
        )
      })}

      {/* Glowing selected-site marker */}
      {selectedLocation && (
        <Marker
          position={[selectedLocation.lat, selectedLocation.lng]}
          icon={glowMarker}
        />
      )}
    </MapContainer>
  );
}
