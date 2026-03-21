import { useEffect } from "react";
import {
//   ImageOverlay,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import type { LatLngBoundsLiteral, LatLngExpression } from "leaflet";
import type { SelectedLocation } from "./App";

interface MapViewProps {
  selectedLocation: SelectedLocation | null;
  onLocationSelect: (location: SelectedLocation) => void;
}

const center: LatLngExpression = [39.8283, -98.5795];

const usBounds: LatLngBoundsLiteral = [
  [24.5, -125.0],
  [49.5, -66.5],
];

function MapClickHandler({
  onLocationSelect,
}: {
  onLocationSelect: (location: SelectedLocation) => void;
}) {
  useMapEvents({
    async click(e) {
      const lat = e.latlng.lat;
      const lng = e.latlng.lng;

      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`
        );
        const data = await res.json();

        onLocationSelect({
          lat,
          lng,
          address: data?.display_name ?? `${lat.toFixed(4)}, ${lng.toFixed(4)}`,
        });
      } catch (error) {
        console.error("Reverse geocoding error:", error);
        onLocationSelect({
          lat,
          lng,
          address: `${lat.toFixed(4)}, ${lng.toFixed(4)}`,
        });
      }
    },
  });

  return null;
}

function RecenterMap({
  selectedLocation,
}: {
  selectedLocation: SelectedLocation | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (selectedLocation) {
      map.flyTo([selectedLocation.lat, selectedLocation.lng], 9, {
        duration: 1.2,
      });
    } else {
      map.flyTo(center, 4, { duration: 1.2 });
    }
  }, [selectedLocation, map]);

  return null;
}

export default function MapView({
  selectedLocation,
  onLocationSelect,
}: MapViewProps) {
  return (
    <MapContainer
      center={center}
      zoom={4}
      minZoom={3}
      maxZoom={15}
      maxBounds={usBounds}
      maxBoundsViscosity={1.0}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <MapClickHandler onLocationSelect={onLocationSelect} />
      <RecenterMap selectedLocation={selectedLocation} />

      {/* <ImageOverlay
        url="/mock-drought.png"
        bounds={usBounds}
        opacity={0.6}
      /> */}

      {selectedLocation && (
        <Marker position={[selectedLocation.lat, selectedLocation.lng]}>
          <Popup>
            <div>
              <strong>Selected Site</strong>
              <br />
              {selectedLocation.address}
              <br />
              Lat: {selectedLocation.lat.toFixed(4)}
              <br />
              Lng: {selectedLocation.lng.toFixed(4)}
            </div>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}