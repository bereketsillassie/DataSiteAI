/**
 * IDWLayer.tsx — Top 3 hotspot markers
 *
 * Renders the top 3 highest-scoring locations per category as
 * Leaflet Circle elements. These are geographic circles with a
 * fixed radius in meters — they scale correctly with zoom automatically
 * because Leaflet handles the projection math.
 *
 * No canvas, no IDW math, no zoom lag.
 */

import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

interface ScoredPoint { lat: number; lng: number; score: number; }
export interface IDWLayerProps { geojson: object; layerId: string; }

const TOP_N = 3;

// Radius of each hotspot circle in meters (~8km)
const RADIUS_M = 8000;

// ── Color ramp — same vivid stops as before ───────────────────
const STOPS: [number, [number, number, number]][] = [
  [0.00, [130,   0, 180]],
  [0.18, [220,   0,   0]],
  [0.34, [255,  80,   0]],
  [0.50, [255, 210,   0]],
  [0.65, [ 80, 255, 120]],
  [0.80, [  0, 220, 255]],
  [0.90, [  0, 180,  80]],
  [1.00, [  0, 120,  50]],
];

function scoreToHex(s: number): string {
  const v = Math.max(0, Math.min(1, s));
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [s0, c0] = STOPS[i], [s1, c1] = STOPS[i + 1];
    if (v <= s1) {
      const t = (v - s0) / (s1 - s0);
      const r = Math.round(c0[0] + t * (c1[0] - c0[0]));
      const g = Math.round(c0[1] + t * (c1[1] - c0[1]));
      const b = Math.round(c0[2] + t * (c1[2] - c0[2]));
      return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}`;
    }
  }
  const last = STOPS[STOPS.length - 1][1];
  return `#${last.map(v => v.toString(16).padStart(2,'0')).join('')}`;
}

function extractTopPoints(geojson: object): ScoredPoint[] {
  const fc = geojson as { features?: Array<{ properties?: Record<string, unknown> }> };
  const all: ScoredPoint[] = [];
  for (const f of fc.features ?? []) {
    const p = f.properties;
    if (
      p &&
      typeof p.lat === 'number' &&
      typeof p.lng === 'number' &&
      typeof p.score === 'number'
    ) {
      all.push({ lat: p.lat, lng: p.lng, score: p.score });
    }
  }
  return all.sort((a, b) => b.score - a.score).slice(0, TOP_N);
}

export default function IDWLayer({ geojson, layerId }: IDWLayerProps) {
  const map = useMap();

  useEffect(() => {
    const points = extractTopPoints(geojson);
    if (points.length === 0) return;

    // Create one Leaflet Circle per top-N point
    const circles = points.map((pt, i) => {
      const color = scoreToHex(pt.score);

      // Outer glow ring — larger, very transparent
      const glow = L.circle([pt.lat, pt.lng], {
        radius: RADIUS_M * 1.8,
        color,
        fillColor: color,
        fillOpacity: 0.08,
        weight: 0,
      });

      // Main filled circle
      const main = L.circle([pt.lat, pt.lng], {
        radius: RADIUS_M,
        color,
        fillColor: color,
        fillOpacity: 0.55,
        weight: 2,
        opacity: 0.9,
      });

      // Rank label (1st, 2nd, 3rd)
      const rank = i + 1;
      const label = L.divIcon({
        className: '',
        html: `<div style="
          background:${color};
          color:#000;
          font-weight:700;
          font-size:11px;
          width:20px;height:20px;
          border-radius:50%;
          display:flex;align-items:center;justify-content:center;
          border:2px solid rgba(255,255,255,0.8);
          box-shadow:0 0 6px ${color};
        ">${rank}</div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
      const marker = L.marker([pt.lat, pt.lng], { icon: label, interactive: false });

      glow.addTo(map);
      main.addTo(map);
      marker.addTo(map);

      return { glow, main, marker };
    });

    return () => {
      circles.forEach(({ glow, main, marker }) => {
        glow.remove();
        main.remove();
        marker.remove();
      });
    };
  }, [map, geojson, layerId]);

  return null;
}