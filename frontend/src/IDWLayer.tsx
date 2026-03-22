/**
 * IDWLayer.tsx — Smooth heatmap overlay with contour texture
 *
 * Rendering pipeline:
 *   1. Spatial grid bucketing → 10x faster than naive IDW (700K ops vs 7.8M)
 *   2. IDW interpolation at 1/4 resolution
 *   3. Contour line pass — detects score threshold crossings, draws
 *      thin isolines like a topographic / weather-pressure map
 *   4. Bilinear upscale via drawImage
 *   5. CSS filter: blur(9px) contrast(1.15) saturate(1.3)
 *
 * Zoom handling:
 *   - `zoomanim`: CSS-scale the canvas in sync with the tile animation
 *     so it never freezes at the wrong size
 *   - `zoomend` + `moveend`: full pixel redraw
 *   - `zoomstart`: fade canvas to 0.3 opacity during zoom for clean UX
 */

import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

interface ScoredPoint { lat: number; lng: number; score: number; }
export interface IDWLayerProps { geojson: object; layerId: string; }

// ── Extract lat/lng/score from GeoJSON ────────────────────────
function extractPoints(geojson: object): ScoredPoint[] {
  const fc = geojson as { features?: Array<{ properties?: Record<string, unknown> }> };
  const out: ScoredPoint[] = [];
  for (const f of fc.features ?? []) {
    const p = f.properties;
    if (p && typeof p.lat === 'number' && typeof p.lng === 'number' && typeof p.score === 'number') {
      out.push({ lat: p.lat, lng: p.lng, score: p.score });
    }
  }
  return out;
}

// ── Color ramp — maximum perceptual contrast between tiers ────
// Each stop is a completely different hue family, not just a shade.
// Bad → purple → red → orange → yellow → cyan → green → teal
// This gives every quality tier its own unmistakable identity.
const STOPS: [number, [number, number, number]][] = [
  [0.00, [130,   0, 180]],  // vivid purple      — terrible
  [0.18, [220,   0,   0]],  // pure red          — very poor
  [0.34, [255,  80,   0]],  // deep orange       — poor
  [0.50, [255, 210,   0]],  // saturated yellow  — average
  [0.65, [ 80, 255, 120]],  // bright cyan-green — good
  [0.80, [  0, 220, 255]],  // electric cyan     — very good
  [0.90, [  0, 180,  80]],  // vivid green       — excellent
  [1.00, [  0, 120,  50]],  // deep green        — outstanding
];

function scoreToRgb(s: number): [number, number, number] {
  const v = Math.max(0, Math.min(1, s));
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [s0, c0] = STOPS[i], [s1, c1] = STOPS[i + 1];
    if (v <= s1) {
      const t = (v - s0) / (s1 - s0);
      return [
        Math.round(c0[0] + t * (c1[0] - c0[0])),
        Math.round(c0[1] + t * (c1[1] - c0[1])),
        Math.round(c0[2] + t * (c1[2] - c0[2])),
      ];
    }
  }
  return STOPS[STOPS.length - 1][1];
}

// ── Contour thresholds — isolines drawn at these score values ─
// Spaced to separate the 5 quality tiers clearly.
const CONTOUR_THRESHOLDS = [0.30, 0.45, 0.60, 0.75, 0.88];

// ── IDWLayer ──────────────────────────────────────────────────
export default function IDWLayer({ geojson, layerId }: IDWLayerProps) {
  const map = useMap();
  // Stable ref for the canvas so zoomanim can access it without re-closure
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const topLeftRef = useRef<L.Point>(L.point(0, 0));

  useEffect(() => {
    const points = extractPoints(geojson);
    if (points.length === 0) return;

    // ── Create canvas in overlayPane ──────────────────────────
    const canvas = L.DomUtil.create('canvas') as HTMLCanvasElement;
    canvas.style.cssText = [
      'position:absolute',
      'pointer-events:none',
      'transition:opacity 0.18s ease',
      // Final smoothing pass — blur softens pixels, contrast keeps
      // colors punchy, saturate makes the ramp pop on dark tiles
      'filter:blur(9px) contrast(1.6) saturate(2.2)',
    ].join(';');
    map.getPanes().overlayPane!.appendChild(canvas);
    canvasRef.current = canvas;

    const SCALE = 4;       // render at 1/4 res, upscale for fluid look
    const IDW_P = 1.8;     // IDW power — higher = sharper hotspot peaks
    const MAX_ALPHA = 0.38; // 38% max opacity → basemap clearly visible
    const BUF = 100;        // pixel buffer around viewport edge

    // ── Spatial grid bucketing for fast nearest-point lookup ──
    // Divide the projected canvas into BUCKET_N × BUCKET_N cells.
    // Each pixel only loops through points in its own cell + 8 neighbors
    // instead of all 99 points → ~10x speedup.
    const BUCKET_N = 8;
    type Bucket = Array<{ x: number; y: number; score: number }>;

    // ── Main draw function ─────────────────────────────────────
    const draw = () => {
      const mapSize = map.getSize();
      const totalW = mapSize.x + BUF * 2;
      const totalH = mapSize.y + BUF * 2;

      // Position canvas in layer space
      const topLeftLatLng = map.containerPointToLatLng(L.point(-BUF, -BUF));
      const topLeft = map.latLngToLayerPoint(topLeftLatLng);
      topLeftRef.current = topLeft;
      canvas.width = totalW;
      canvas.height = totalH;
      canvas.style.transform = '';
      canvas.style.transformOrigin = '';
      L.DomUtil.setPosition(canvas, topLeft);

      // Low-res canvas size
      const cW = Math.ceil(totalW / SCALE);
      const cH = Math.ceil(totalH / SCALE);

      // Project data points into canvas-local pixel coords
      const proj = points.map(pt => {
        const lp = map.latLngToLayerPoint([pt.lat, pt.lng]);
        return { x: (lp.x - topLeft.x) / SCALE, y: (lp.y - topLeft.y) / SCALE, score: pt.score };
      });

      // ── Adaptive influence radius ─────────────────────────
      // Use median nearest-neighbor distance × 1.6 so cells blend
      // naturally at any zoom level without over- or under-bleeding.
      const nnDists = proj.map(p => {
        let min = Infinity;
        for (const q of proj) {
          if (q === p) continue;
          const d = Math.hypot(p.x - q.x, p.y - q.y);
          if (d < min) min = d;
        }
        return min;
      }).sort((a, b) => a - b);
      const radius = Math.max(10, Math.min(nnDists[Math.floor(nnDists.length / 2)] * 1.6, 130));

      // ── Build spatial buckets ─────────────────────────────
      const buckets: Bucket[][] = Array.from({ length: BUCKET_N }, () =>
        Array.from({ length: BUCKET_N }, () => [])
      );
      for (const p of proj) {
        const bx = Math.max(0, Math.min(BUCKET_N - 1, Math.floor(p.x / cW * BUCKET_N)));
        const by = Math.max(0, Math.min(BUCKET_N - 1, Math.floor(p.y / cH * BUCKET_N)));
        buckets[by][bx].push(p);
      }

      const getBucketNeighbors = (px: number, py: number): Bucket => {
        const bx = Math.max(0, Math.min(BUCKET_N - 1, Math.floor(px / cW * BUCKET_N)));
        const by = Math.max(0, Math.min(BUCKET_N - 1, Math.floor(py / cH * BUCKET_N)));
        const out: Bucket = [];
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            const nx = bx + dx, ny = by + dy;
            if (nx >= 0 && nx < BUCKET_N && ny >= 0 && ny < BUCKET_N) {
              out.push(...buckets[ny][nx]);
            }
          }
        }
        return out;
      };

      // ── IDW pixel loop ────────────────────────────────────
      const imageData = new ImageData(cW, cH);
      const px = imageData.data;
      // scoreGrid stores interpolated score per pixel (for contour pass)
      const scoreGrid = new Float32Array(cW * cH);

      for (let py = 0; py < cH; py++) {
        for (let qx = 0; qx < cW; qx++) {
          const nearby = getBucketNeighbors(qx, py);
          let wSum = 0, sSum = 0, aMax = 0;

          for (const pt of nearby) {
            const dist = Math.hypot(qx - pt.x, py - pt.y);
            if (dist < 0.01) { wSum = 1; sSum = pt.score; aMax = 1; break; }
            if (dist > radius * 2.8) continue;
            const w = 1 / Math.pow(dist, IDW_P);
            wSum += w;
            sSum += w * pt.score;
            // Alpha: smooth Gaussian-like falloff — full at center, zero at 2×radius
            const a = Math.exp(-(dist * dist) / (2 * (radius * 0.75) ** 2));
            if (a > aMax) aMax = a;
          }

          if (wSum > 0 && aMax > 0.018) {
            const score = sSum / wSum;
            scoreGrid[py * cW + qx] = score;
            const [r, g, b] = scoreToRgb(score);
            const idx = (py * cW + qx) * 4;
            // Alpha shaped by data density: Gaussian falloff from nearest point
            const alpha = Math.min(aMax, MAX_ALPHA);
            px[idx] = r; px[idx + 1] = g; px[idx + 2] = b;
            px[idx + 3] = Math.round(alpha * 255);
          }
        }
      }

      // ── Contour line pass ─────────────────────────────────
      // For each pixel, check if any 4-neighbor crosses a threshold.
      // If so, blend a thin bright/dark isoline into the pixel.
      // This creates the topographic / pressure-map texture.
      for (const thresh of CONTOUR_THRESHOLDS) {
        for (let py = 1; py < cH - 1; py++) {
          for (let qx = 1; qx < cW - 1; qx++) {
            const s = scoreGrid[py * cW + qx];
            if (s === 0) continue;

            // Check 4 cardinal neighbors for threshold crossing
            const neighbors = [
              scoreGrid[(py - 1) * cW + qx],
              scoreGrid[(py + 1) * cW + qx],
              scoreGrid[py * cW + (qx - 1)],
              scoreGrid[py * cW + (qx + 1)],
            ].filter(n => n > 0);

            if (neighbors.length === 0) continue;

            const crosses = neighbors.some(n =>
              (s < thresh && n >= thresh) || (s >= thresh && n < thresh)
            );

            if (crosses) {
              const idx = (py * cW + qx) * 4;
              // Existing alpha must be nonzero to draw the contour
              if (px[idx + 3] > 0) {
                // Bright thin isoline: blend toward white-ish at 35% opacity
                // Creates that luminous contour-line look
                const blend = 0.35;
                px[idx]     = Math.round(px[idx]     * (1 - blend) + 230 * blend);
                px[idx + 1] = Math.round(px[idx + 1] * (1 - blend) + 230 * blend);
                px[idx + 2] = Math.round(px[idx + 2] * (1 - blend) + 230 * blend);
                // Slightly boost alpha on contour pixels so they're visible
                px[idx + 3] = Math.min(255, px[idx + 3] + 25);
              }
            }
          }
        }
      }

      // ── Bilinear upscale ──────────────────────────────────
      const off = document.createElement('canvas');
      off.width = cW; off.height = cH;
      off.getContext('2d')!.putImageData(imageData, 0, 0);
      const ctx = canvas.getContext('2d')!;
      ctx.clearRect(0, 0, totalW, totalH);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(off, 0, 0, cW, cH, 0, 0, totalW, totalH);

      canvas.style.opacity = '1';
    };

    // ── Zoom animation sync ───────────────────────────────────
    // During Leaflet's zoom animation, CSS-transform the canvas so it
    // scales in sync with the tiles instead of freezing at old size.
    const onZoomAnim = (e: L.ZoomAnimEvent) => {
      const scale = map.getZoomScale(e.zoom, map.getZoom());
      // The zoom origin in container coordinates
      const origin = map.latLngToContainerPoint(e.center);
      // Shift origin to canvas-local coordinates
      const tl = topLeftRef.current;
      const canvasOriginX = origin.x - tl.x;
      const canvasOriginY = origin.y - tl.y;
      canvas.style.transformOrigin = `${canvasOriginX}px ${canvasOriginY}px`;
      canvas.style.transform = `scale(${scale})`;
    };

    // Fade canvas during zoom, restore after
    const onZoomStart = () => { canvas.style.opacity = '0.25'; };

    // Debounced redraw — prevents rapid-fire redraws during mouse-wheel zoom
    let rafId = 0;
    const scheduleDraw = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(draw);
    };

    map.on('zoomanim', onZoomAnim as L.LeafletEventHandlerFn);
    map.on('zoomstart', onZoomStart);
    map.on('zoomend moveend resize', scheduleDraw);

    draw();

    return () => {
      cancelAnimationFrame(rafId);
      map.off('zoomanim', onZoomAnim as L.LeafletEventHandlerFn);
      map.off('zoomstart', onZoomStart);
      map.off('zoomend moveend resize', scheduleDraw);
      canvas.remove();
      canvasRef.current = null;
    };
  }, [map, geojson, layerId]);

  return null;
}