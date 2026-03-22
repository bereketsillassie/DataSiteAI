import { useState, useCallback, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import MapView from '@/MapView'
import { LayersPanel } from '@/components/Sidebar'
import { AnalysisPanel } from '@/components/AnalysisPanel'
import { ChatWidget } from '@/components/ChatWidget'
import { LandingPage } from '@/components/LandingPage'
import { DataSiteAILogo } from '@/components/DataSiteAILogo'
import { MapPin } from 'lucide-react'
import { runAnalysis, fetchLayer, detectState } from '@/lib/api'

interface ActiveOverlays {
  carbonEmissions: boolean
  wildfireRisk: boolean
  floodZone: boolean
  seismicHazard: boolean
}

export interface Listing {
  id: string
  address: string | null
  state: string
  county: string | null
  acres: number
  price_usd: number | null
  price_per_acre: number | null
  listing_url: string | null
  coordinates: { lat: number; lng: number }
  nearest_cell_scores: Record<string, number>
}

export default function App() {
  const [hasStarted, setHasStarted] = useState(false)

  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number
    lng: number
  } | null>(null)

  // ── Incoming UI state ───────────────────────────────────────
  const [activeOverlays, setActiveOverlays] = useState<ActiveOverlays>({
    carbonEmissions: true,
    wildfireRisk: false,
    floodZone: true,
    seismicHazard: false,
  })

  const [listings, setListings] = useState<Listing[]>([])

  // ── IDW layer state ─────────────────────────────────────────
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [activeLayerIds, setActiveLayerIds] = useState<Set<string>>(new Set())
  const [cachedLayers, setCachedLayers] = useState<Map<string, object>>(new Map())

  // Fetch nearby listings whenever a location is selected
  useEffect(() => {
    if (!selectedLocation) {
      setListings([])
      return
    }
    const { lat, lng } = selectedLocation
    const controller = new AbortController()

    fetch(
      `http://127.0.0.1:8001/api/v1/listings?lat=${lat}&lng=${lng}&radius_km=150&limit=30`,
      { signal: controller.signal },
    )
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((data) => setListings(data.listings ?? []))
      .catch(() => setListings([]))

    return () => controller.abort()
  }, [selectedLocation])

  const handleLocationSelect = useCallback(
    (lat: number, lng: number) => {
      setSelectedLocation({ lat, lng })
      setActiveLayerIds(new Set())
      setCachedLayers(new Map())
    },
    [],
  )

  const toggleOverlay = useCallback(
    (key: keyof ActiveOverlays) =>
      setActiveOverlays((prev) => ({ ...prev, [key]: !prev[key] })),
    [],
  )

  const handleAnalyze = useCallback(async (location: { lat: number; lng: number }) => {
    setIsAnalyzing(true)
    try {
      const delta = 0.45
      const result = await runAnalysis({
        bbox: {
          min_lat: location.lat - delta,
          min_lng: location.lng - delta,
          max_lat: location.lat + delta,
          max_lng: location.lng + delta,
        },
        state: detectState(location.lat, location.lng),
        grid_resolution_km: 5,
        min_acres: 20,
        max_acres: 500,
        include_listings: true,
      })
      const optimal = await fetchLayer(result.analysis_id, 'optimal')
      setCachedLayers(new Map([['optimal', optimal]]))
      setActiveLayerIds(new Set(['optimal']))
    } catch {
      // analysis failed silently — AnalysisPanel handles its own error display
    } finally {
      setIsAnalyzing(false)
    }
  }, [])

  // Auto-run IDW analysis when a location is selected
  useEffect(() => {
    if (selectedLocation) {
      void handleAnalyze(selectedLocation)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLocation])

  return (
    <AnimatePresence mode="wait">
      {!hasStarted ? (
        <motion.div
          key="landing"
          className="h-screen w-screen overflow-y-auto"
          exit={{ opacity: 0 }}
          transition={{ duration: 0.45, ease: 'easeInOut' }}
        >
          <LandingPage onGetStarted={() => setHasStarted(true)} />
        </motion.div>
      ) : (
        <motion.div
          key="dashboard"
          className="relative h-screen w-screen overflow-hidden bg-background"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.55, ease: 'easeOut' }}
        >
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
          <header className="absolute top-0 left-0 right-0 z-[1000] overflow-hidden">
            {/* Gradient backdrop */}
            <div className="absolute inset-0 bg-gradient-to-r from-slate-950/95 via-background/85 to-slate-950/95 backdrop-blur-xl border-b border-white/5" />

            {/* Subtle wave accent line at the bottom of the bar */}
            <svg
              className="absolute bottom-0 left-0 w-full h-[3px] opacity-50"
              preserveAspectRatio="none"
              viewBox="0 0 1200 6"
              fill="none"
            >
              <defs>
                <linearGradient id="headerWave" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="transparent" />
                  <stop offset="25%" stopColor="#3b82f6" stopOpacity="0.7" />
                  <stop offset="55%" stopColor="#06b6d4" stopOpacity="0.9" />
                  <stop offset="80%" stopColor="#6366f1" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="transparent" />
                </linearGradient>
              </defs>
              <path
                d="M0,3 Q150,1 300,3 T600,3 T900,3 T1200,3"
                stroke="url(#headerWave)"
                strokeWidth="1.5"
                fill="none"
              />
            </svg>

            {/* Header content */}
            <div className="relative flex items-center justify-between px-5 py-3">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <DataSiteAILogo className="w-9 h-9" />
                  <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 rounded-full animate-pulse shadow-sm shadow-emerald-400/50" />
                </div>
                <div>
                  <h1 className="text-sm font-semibold tracking-tight leading-none">
                    <span className="bg-gradient-to-r from-white via-slate-200 to-slate-300 bg-clip-text text-transparent">
                      DATASITE
                    </span>
                    <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                      AI
                    </span>
                  </h1>
                  <p className="text-[10px] text-muted-foreground leading-none mt-0.5 tracking-wide">
                    Site Selection Platform
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {selectedLocation ? (
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary/60 backdrop-blur border border-border/50">
                    <MapPin className="w-3.5 h-3.5 text-primary" />
                    <span className="text-xs font-mono text-foreground">
                      {selectedLocation.lat.toFixed(4)}° N,{' '}
                      {Math.abs(selectedLocation.lng).toFixed(4)}° W
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary/40 border border-border/30">
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 animate-pulse" />
                    <span className="text-xs text-muted-foreground">Click map to select a site</span>
                  </div>
                )}
              </div>
            </div>
          </header>

          {/* ── Quick Metrics bar — top right ────────────────────── */}
          <div className="absolute top-[60px] right-4 z-[900] mt-1">
            <div className="bg-background/75 backdrop-blur-xl border border-border/40 rounded-xl px-4 py-2 shadow-xl shadow-black/25 flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[9px] font-mono uppercase tracking-widest text-emerald-400">Online</span>
              </div>
              <div className="w-px h-3 bg-border/50" />
              <div className="flex items-center gap-1.5">
                <span className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Layers</span>
                <span className="text-sm font-bold font-mono text-cyan-400 tabular-nums">
                  {activeLayerIds.size}
                </span>
              </div>
              <div className="w-px h-3 bg-border/50" />
              <div className="flex items-center gap-1.5">
                <span className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Listings</span>
                <span className="text-sm font-bold font-mono text-emerald-400 tabular-nums">
                  {listings.length}
                </span>
              </div>
              <div className="w-px h-3 bg-border/50" />
              <div className="flex items-center gap-1.5">
                <span className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Model</span>
                <span className="text-[10px] font-mono text-primary font-semibold">Gemini 2.5F</span>
              </div>
              <div className="w-px h-3 bg-border/50" />
              <div className="flex items-center gap-1.5">
                <span className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Site</span>
                <span className="text-[10px] font-mono text-foreground/70 tabular-nums">
                  {selectedLocation
                    ? `${selectedLocation.lat.toFixed(2)}, ${selectedLocation.lng.toFixed(2)}`
                    : '—'}
                </span>
              </div>
              {isAnalyzing && (
                <>
                  <div className="w-px h-3 bg-border/50" />
                  <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                    <span className="text-[9px] font-mono uppercase tracking-widest text-cyan-400">Analyzing</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* ── Floating layers card — bottom left ───────────────── */}
          <div className="absolute bottom-6 left-4 z-[1000]">
            <LayersPanel activeOverlays={activeOverlays} onToggle={toggleOverlay} />
          </div>

          {/* ── Floating analysis panel — left side ──────────────── */}
          <div
            className={`absolute top-[112px] left-4 bottom-[248px] z-[1000] transition-all duration-300 ease-out ${
              selectedLocation
                ? 'opacity-100 translate-x-0'
                : 'opacity-0 -translate-x-6 pointer-events-none'
            }`}
          >
            <AnalysisPanel selectedLocation={selectedLocation} />
          </div>

          {/* ── AI chat widget — bottom right ────────────────────── */}
          <ChatWidget locationContext={selectedLocation} />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
