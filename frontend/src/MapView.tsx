import { MapContainer, TileLayer } from "react-leaflet";
import { LatLngBoundsLiteral, LatLngExpression } from "leaflet";

export default function MapView() {
  const center: LatLngExpression = [39.8283, -98.5795];

  // Rough bounding box around the continental U.S.
  const usBounds: LatLngBoundsLiteral = [
    [24.396308, -125.0], // southwest
    [49.384358, -66.93457], // northeast
  ];

  return (
    <MapContainer
      center={center}
      zoom={4}
      minZoom={3}
      maxZoom={10}
      maxBounds={usBounds}
      maxBoundsViscosity={1.0}
      style={{ height: "100%", width: "100%" }}
      zoomControl={true}
    >
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
    </MapContainer>
  );
}