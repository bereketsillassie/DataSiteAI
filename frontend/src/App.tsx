import { useState, useCallback } from 'react'
import MapView from '@/MapView'
import { LayersPanel } from '@/components/Sidebar'
import { AnalysisPanel } from '@/components/AnalysisPanel'
import { ChatWidget } from '@/components/ChatWidget'
import { Database, MapPin } from 'lucide-react'
import { runAnalysis, fetchLayer, detectState, type AnalyzeResponse } from '@/lib/api'

export default function App() {
  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number
    lng: number
  } | null>(null)

  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [currentAnalysis, setCurrentAnalysis] = useState<AnalyzeResponse | null>(null)
  const [activeLayerIds, setActiveLayerIds] = useState<Set<string>>(new Set())
  const [cachedLayers, setCachedLayers] = useState<Map<string, object>>(new Map())
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  const handleLocationSelect = useCallback((lat: number, lng: number) => {
    setSelectedLocation({ lat, lng })
    setCurrentAnalysis(null)
    setAnalysisError(null)
    setActiveLayerIds(new Set())
    setCachedLayers(new Map())
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (!selectedLocation) return
    setIsAnalyzing(true)
    setAnalysisError(null)
    try {
      const delta = 0.45
      const result = await runAnalysis({
        bbox: {
          min_lat: selectedLocation.lat - delta,
          min_lng: selectedLocation.lng - delta,
          max_lat: selectedLocation.lat + delta,
          max_lng: selectedLocation.lng + delta,
        },
        state: detectState(selectedLocation.lat, selectedLocation.lng),
        grid_resolution_km: 5,
        min_acres: 20,
        max_acres: 500,
        include_listings: true,
      })
      setCurrentAnalysis(result)
      const optimal = await fetchLayer(result.analysis_id, 'optimal')
      setCachedLayers(new Map([['optimal', optimal]]))
      setActiveLayerIds(new Set(['optimal']))
    } catch (e: unknown) {
      setAnalysisError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setIsAnalyzing(false)
    }
  }, [selectedLocation])

  const toggleLayer = useCallback(async (layerId: string) => {
    if (activeLayerIds.has(layerId)) {
      setActiveLayerIds((prev) => { const s = new Set(prev); s.delete(layerId); return s })
    } else {
      let geojson = cachedLayers.get(layerId)
      if (!geojson && currentAnalysis) {
        try {
          geojson = await fetchLayer(currentAnalysis.analysis_id, layerId)
          setCachedLayers((prev) => new Map(prev).set(layerId, geojson!))
        } catch { return }
      }
      if (geojson) setActiveLayerIds((prev) => new Set(prev).add(layerId))
    }
  }, [activeLayerIds, cachedLayers, currentAnalysis])

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-background">

      {/* ── Full-screen map ───────────────────────────────────── */}
      <div className="absolute inset-0">
        <MapView
          selectedLocation={selectedLocation}
          onLocationSelect={handleLocationSelect}
          activeLayerIds={activeLayerIds}
          cachedLayers={cachedLayers}
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
        <LayersPanel
          activeLayerIds={activeLayerIds}
          onToggle={(id) => void toggleLayer(id)}
          hasAnalysis={currentAnalysis !== null}
        />
      </div>

      {/* ── Floating analysis panel — right side ─────────────── */}
      <div
        className={`absolute top-[56px] right-4 bottom-4 z-[1000] transition-all duration-300 ease-out ${
          selectedLocation
            ? 'opacity-100 translate-x-0'
            : 'opacity-0 translate-x-6 pointer-events-none'
        }`}
      >
        <AnalysisPanel
          selectedLocation={selectedLocation}
          currentAnalysis={currentAnalysis}
          isAnalyzing={isAnalyzing}
          analysisError={analysisError}
          onAnalyze={() => void handleAnalyze()}
        />
      </div>

      {/* ── AI chat widget — bottom right ────────────────────── */}
      <ChatWidget locationContext={selectedLocation} />
    </div>
  )
}
