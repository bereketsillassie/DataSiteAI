import { Button } from '@/components/ui/button'
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
import type { AnalyzeResponse } from '@/lib/api'

// ── Props ──────────────────────────────────────────────────────
interface AnalysisPanelProps {
  selectedLocation: { lat: number; lng: number } | null
  currentAnalysis: AnalyzeResponse | null
  isAnalyzing: boolean
  analysisError: string | null
  onAnalyze: () => void
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
export function AnalysisPanel({
  selectedLocation,
  currentAnalysis,
  isAnalyzing,
  analysisError,
  onAnalyze,
}: AnalysisPanelProps) {
  const topCell = currentAnalysis?.grid_cells?.[0] ?? null

  const compositeScore = pct(topCell?.composite_score?.composite)
  const powerScore     = topCell?.scores?.['power'] ?? 0
  const connectScore   = topCell?.scores?.['connectivity'] ?? 0
  const climateScore   = topCell?.scores?.['climate'] ?? 0

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const powerMetrics      = (topCell?.metrics?.power as any) ?? {}
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const climateMetrics    = (topCell?.metrics?.climate as any) ?? {}
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const connectMetrics    = (topCell?.metrics?.connectivity as any) ?? {}

  const avgSummerTempC = climateMetrics.avg_summer_temp_c as number | undefined
  const tempDisplay = avgSummerTempC != null ? `${celsiusToFahrenheit(avgSummerTempC)}°F` : '—'

  const renewablePct = powerMetrics.renewable_energy_pct as number | undefined
  const carbonDisplay = renewablePct != null
    ? (renewablePct >= 0.5 ? 'Low' : renewablePct >= 0.25 ? 'Med' : 'High')
    : '—'

  const reliabilityDisplay = powerMetrics.grid_reliability_index != null
    ? `${Math.round((powerMetrics.grid_reliability_index as number) * 100)}%`
    : '—'

  const ixKm = connectMetrics.nearest_ix_point_km as number | undefined
  const latencyDisplay = ixKm != null ? `${Math.round(ixKm)}km` : '—'

  const showAnalyzeButton = selectedLocation && !isAnalyzing && !currentAnalysis

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
        {showAnalyzeButton && (
          <Button
            onClick={onAnalyze}
            size="sm"
            className="w-full mt-3 h-8 text-xs"
          >
            Analyze Site
          </Button>
        )}
      </div>

      {/* ── Loading ──────────────────────────────────────────── */}
      {isAnalyzing && (
        <div className="rounded-2xl bg-background/70 backdrop-blur-xl border border-border/50 shadow-2xl shadow-black/30 p-4 flex items-center gap-3">
          <Loader2 className="w-4 h-4 text-primary animate-spin flex-shrink-0" />
          <p className="text-xs text-muted-foreground">Scoring location…</p>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────── */}
      {analysisError && (
        <div className="rounded-2xl bg-background/70 backdrop-blur-xl border border-amber-500/20 shadow-2xl shadow-black/30 p-4 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            {analysisError}. Check that the backend is running on port 8000.
          </p>
        </div>
      )}

      {/* ── Score data ───────────────────────────────────────── */}
      {!isAnalyzing && topCell && (
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
