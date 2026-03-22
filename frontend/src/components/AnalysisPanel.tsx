import { useState, useEffect } from 'react'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import {
  MapPin,
  Zap,
  Thermometer,
  Wifi,
  Cloud,
  Loader2,
  AlertCircle,
  BarChart3,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ── API Types ──────────────────────────────────────────────────
interface AnalyzeResponse {
  grid_cells: ScoreBundle[]
}

interface ScoreBundle {
  composite_score: { composite: number }
  scores: Record<string, number>
  metrics: {
    power?: { electricity_rate_cents_per_kwh?: number; renewable_energy_pct?: number; grid_reliability_index?: number }
    climate?: { avg_summer_temp_c?: number; annual_cooling_degree_days?: number }
    connectivity?: { nearest_ix_point_km?: number }
    environmental?: { air_quality_index?: number }
  }
}

interface AnalysisPanelProps {
  selectedLocation: { lat: number; lng: number } | null
}

// ── Helpers ────────────────────────────────────────────────────
function pct(score: number | undefined): number {
  return Math.round((score ?? 0) * 100)
}

function celsiusToFahrenheit(c: number): number {
  return Math.round(c * 9 / 5 + 32)
}

function qualityLabel(score: number): string {
  if (score >= 0.85) return 'Excellent'
  if (score >= 0.70) return 'Good'
  if (score >= 0.50) return 'Fair'
  return 'Poor'
}

function qualityVariant(score: number): 'default' | 'secondary' | 'outline' {
  if (score >= 0.70) return 'default'
  if (score >= 0.50) return 'secondary'
  return 'outline'
}

// ── Component ──────────────────────────────────────────────────
export function AnalysisPanel({ selectedLocation }: AnalysisPanelProps) {
  const [siteData, setSiteData] = useState<ScoreBundle | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    if (!selectedLocation) {
      setSiteData(null)
      setHasError(false)
      return
    }

    const { lat, lng } = selectedLocation
    const delta = 0.05

    const fetchScores = async () => {
      setIsLoading(true)
      setHasError(false)
      setSiteData(null)

      try {
        // Reverse-geocode to get US state code
        const geoRes = await fetch(
          `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`,
          { headers: { 'Accept-Language': 'en' } },
        )
        const geoData: { address?: { 'ISO3166-2-lvl4'?: string } } = await geoRes.json()
        const iso = geoData?.address?.['ISO3166-2-lvl4'] ?? ''
        const stateCode = iso.startsWith('US-') ? iso.slice(3) : ''

        if (!stateCode) {
          setHasError(true)
          return
        }

        const res = await fetch('http://127.0.0.1:8001/api/v1/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            bbox: {
              min_lat: lat - delta,
              min_lng: lng - delta,
              max_lat: lat + delta,
              max_lng: lng + delta,
            },
            state: stateCode,
            grid_resolution_km: 5.0,
            include_listings: false,
          }),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data: AnalyzeResponse = await res.json()
        setSiteData(data.grid_cells?.[0] ?? null)
      } catch {
        setHasError(true)
      } finally {
        setIsLoading(false)
      }
    }

    void fetchScores()
  }, [selectedLocation])

  const compositeScore = pct(siteData?.composite_score?.composite)
  const powerScore     = siteData?.scores?.['power'] ?? 0
  const connectScore   = siteData?.scores?.['connectivity'] ?? 0
  const climateScore   = siteData?.scores?.['climate'] ?? 0

  const avgSummerTempC = siteData?.metrics?.climate?.avg_summer_temp_c
  const tempDisplay = avgSummerTempC != null ? `${celsiusToFahrenheit(avgSummerTempC)}°F` : '—'
  const renewablePct = siteData?.metrics?.power?.renewable_energy_pct
  const carbonDisplay = renewablePct != null
    ? (renewablePct >= 0.5 ? 'Low' : renewablePct >= 0.25 ? 'Med' : 'High')
    : '—'
  const reliabilityDisplay = siteData?.metrics?.power?.grid_reliability_index != null
    ? `${Math.round((siteData.metrics.power.grid_reliability_index ?? 0) * 100)}%`
    : '—'
  const ixKm = siteData?.metrics?.connectivity?.nearest_ix_point_km
  const latencyDisplay = ixKm != null ? `${Math.round(ixKm)}km` : '—'

  return (
    <div className="w-72 flex flex-col gap-3 overflow-y-auto max-h-full">

      {/* ── Header card ─────────────────────────────────────── */}
      <div className="rounded-2xl bg-background/70 backdrop-blur-xl border border-border/50 shadow-2xl shadow-black/30 p-4">
        <div className="flex items-center gap-2 mb-1">
          <BarChart3 className="w-4 h-4 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Site Analysis
          </span>
        </div>
        {selectedLocation && (
          <div className="flex items-center gap-1.5 mt-2">
            <MapPin className="w-3.5 h-3.5 text-primary flex-shrink-0" />
            <span className="text-xs font-mono text-foreground/80">
              {selectedLocation.lat.toFixed(5)}°, {selectedLocation.lng.toFixed(5)}°
            </span>
          </div>
        )}
      </div>

      {/* ── Loading ──────────────────────────────────────────── */}
      {isLoading && (
        <div className="rounded-2xl bg-background/70 backdrop-blur-xl border border-border/50 shadow-2xl shadow-black/30 p-4 flex items-center gap-3">
          <Loader2 className="w-4 h-4 text-primary animate-spin flex-shrink-0" />
          <p className="text-xs text-muted-foreground">Scoring location…</p>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────── */}
      {hasError && (
        <div className="rounded-2xl bg-background/70 backdrop-blur-xl border border-amber-500/20 shadow-2xl shadow-black/30 p-4 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            Could not score this location. Try clicking within the continental US, or check that the backend is running on port 8001.
          </p>
        </div>
      )}

      {/* ── Score data ───────────────────────────────────────── */}
      {!isLoading && siteData && (
        <>
          {/* Score bars */}
          <div className="rounded-2xl bg-background/70 backdrop-blur-xl border border-border/50 shadow-2xl shadow-black/30 p-4 space-y-4">
            <StatItem
              label="Suitability Score"
              value={compositeScore}
              max={100}
              suffix="/100"
              badge={qualityLabel(compositeScore / 100)}
              badgeVariant={qualityVariant(compositeScore / 100)}
            />
            <StatItem
              label="Power Grid"
              value={pct(powerScore)}
              max={100}
              badge={qualityLabel(powerScore)}
              badgeVariant={qualityVariant(powerScore)}
            />
            <StatItem
              label="Connectivity"
              value={pct(connectScore)}
              max={100}
              badge={qualityLabel(connectScore)}
              badgeVariant={qualityVariant(connectScore)}
            />
            <StatItem
              label="Cooling Efficiency"
              value={pct(climateScore)}
              max={100}
              suffix="%"
              badge={qualityLabel(climateScore)}
              badgeVariant={qualityVariant(climateScore)}
            />
          </div>

          {/* Quick stats grid */}
          <div className="grid grid-cols-2 gap-2">
            <QuickStat icon={<Zap className="w-4 h-4" />}         label="Grid Uptime"  value={reliabilityDisplay} />
            <QuickStat icon={<Thermometer className="w-4 h-4" />} label="Avg Summer"   value={tempDisplay} />
            <QuickStat icon={<Wifi className="w-4 h-4" />}        label="Nearest IX"   value={latencyDisplay} />
            <QuickStat icon={<Cloud className="w-4 h-4" />}       label="Carbon"       value={carbonDisplay} />
          </div>
        </>
      )}
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────

function StatItem({
  label,
  value,
  max,
  suffix = '',
  badge,
  badgeVariant = 'default',
}: {
  label: string
  value: number
  max: number
  suffix?: string
  badge?: string
  badgeVariant?: 'default' | 'secondary' | 'outline'
}) {
  const percentage = (value / max) * 100

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-foreground">
            {value}{suffix}
          </span>
          {badge && (
            <Badge
              variant={badgeVariant}
              className={cn(
                'text-[10px] px-1.5 py-0',
                badgeVariant === 'default' && 'bg-emerald-500/20 text-emerald-700 border-emerald-500/30 dark:text-emerald-400',
              )}
            >
              {badge}
            </Badge>
          )}
        </div>
      </div>
      <Progress value={percentage} className="h-1" />
    </div>
  )
}

function QuickStat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="rounded-xl bg-background/70 backdrop-blur-xl border border-border/50 shadow-lg shadow-black/20 p-3">
      <div className="flex items-center gap-1.5 text-primary mb-1">{icon}</div>
      <p className="text-[10px] text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold text-foreground">{value}</p>
    </div>
  )
}
