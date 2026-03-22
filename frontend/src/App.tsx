import { useState, useCallback } from 'react'
import MapView from '@/MapView'
import { LayersPanel } from '@/components/Sidebar'
import { AnalysisPanel } from '@/components/AnalysisPanel'
import { ChatWidget } from '@/components/ChatWidget'
import { Database, MapPin } from 'lucide-react'

interface ActiveOverlays {
  carbonEmissions: boolean
  wildfireRisk: boolean
  floodZone: boolean
  seismicHazard: boolean
}

export default function App() {
  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number
    lng: number
  } | null>(null)

  const [activeOverlays, setActiveOverlays] = useState<ActiveOverlays>({
    carbonEmissions: true,
    wildfireRisk: false,
    floodZone: true,
    seismicHazard: false,
  })

  const handleLocationSelect = useCallback(
    (lat: number, lng: number) => setSelectedLocation({ lat, lng }),
    [],
  )

  const toggleOverlay = useCallback(
    (key: keyof ActiveOverlays) =>
      setActiveOverlays((prev) => ({ ...prev, [key]: !prev[key] })),
    [],
  )

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-background">

      {/* ── Full-screen map ───────────────────────────────────── */}
      <div className="absolute inset-0">
        <MapView
          selectedLocation={selectedLocation}
          onLocationSelect={handleLocationSelect}
          activeOverlays={activeOverlays}
        />
      </div>

      {/* ── Floating header bar ───────────────────────────────── */}
      <header className="absolute top-0 left-0 right-0 z-[1000] flex items-center justify-between px-5 py-3 bg-background/60 backdrop-blur-xl border-b border-border/40">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center">
              <Database className="w-4 h-4 text-primary" />
            </div>
            <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-foreground leading-none">DataSiteAI</h1>
            <p className="text-[10px] text-muted-foreground leading-none mt-0.5">Site Selection Platform</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {selectedLocation ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary/60 backdrop-blur border border-border/50">
              <MapPin className="w-3.5 h-3.5 text-primary" />
              <span className="text-xs font-mono text-foreground">
                {selectedLocation.lat.toFixed(4)}° N, {Math.abs(selectedLocation.lng).toFixed(4)}° W
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary/40 border border-border/30">
              <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 animate-pulse" />
              <span className="text-xs text-muted-foreground">Click map to select a site</span>
            </div>
          )}
        </div>
      </header>

      {/* ── Floating layers card — bottom left ───────────────── */}
      <div className="absolute bottom-6 left-4 z-[1000]">
        <LayersPanel activeOverlays={activeOverlays} onToggle={toggleOverlay} />
      </div>

      {/* ── Floating analysis panel — right side ─────────────── */}
      <div
        className={`absolute top-[56px] right-4 bottom-4 z-[1000] transition-all duration-300 ease-out ${
          selectedLocation
            ? 'opacity-100 translate-x-0'
            : 'opacity-0 translate-x-6 pointer-events-none'
        }`}
      >
        <AnalysisPanel selectedLocation={selectedLocation} />
      </div>

      {/* ── AI chat widget — bottom right ────────────────────── */}
      <ChatWidget locationContext={selectedLocation} />
    </div>
  )
}
