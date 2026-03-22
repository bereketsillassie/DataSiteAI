import { MapContainer, TileLayer, Marker, Circle, useMapEvents } from "react-leaflet";
import L from 'leaflet';
import IDWLayer from './IDWLayer';

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

// ── Layer render order (optimal at bottom, others stack above) ─
const LAYER_ORDER = [
  'optimal',
  'power',
  'water',
  'geological',
  'climate',
  'connectivity',
  'economic',
  'environmental',
] as const;

// ── Types ─────────────────────────────────────────────────────
interface MapViewProps {
  selectedLocation: { lat: number; lng: number } | null;
  onLocationSelect: (lat: number, lng: number) => void;
  activeLayerIds: Set<string>;
  cachedLayers: Map<string, object>;
}

// ── MapClickHandler ───────────────────────────────────────────
function MapClickHandler({ onLocationSelect }: { onLocationSelect: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onLocationSelect(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

// ── MapView ───────────────────────────────────────────────────
export default function MapView({ selectedLocation, onLocationSelect, activeLayerIds, cachedLayers }: MapViewProps) {
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

      {/* IDW heatmap layers — smooth fluid precipitation-style overlays */}
      {LAYER_ORDER.map((layerId) => {
        const data = cachedLayers.get(layerId);
        if (!activeLayerIds.has(layerId) || !data) return null;
        return (
          <IDWLayer
            key={`${layerId}-${(data as { features?: unknown[] }).features?.length ?? 0}`}
            geojson={data}
            layerId={layerId}
          />
        );
      })}

      {/* Analysis radius ring — shows the ~50km scoring area */}
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