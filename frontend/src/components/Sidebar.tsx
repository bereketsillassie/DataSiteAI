import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
<<<<<<< HEAD
import { Zap, Droplets, Mountain, Thermometer, Wifi, BarChart3, Leaf, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'
import { LAYER_CATEGORIES } from '@/lib/api'

// ── Icon map — keyed to LAYER_CATEGORIES ids ──────────────────
const LAYER_ICONS: Record<string, React.ReactNode> = {
  power:         <Zap className="w-3.5 h-3.5" />,
  water:         <Droplets className="w-3.5 h-3.5" />,
  geological:    <Mountain className="w-3.5 h-3.5" />,
  climate:       <Thermometer className="w-3.5 h-3.5" />,
  connectivity:  <Wifi className="w-3.5 h-3.5" />,
  economic:      <BarChart3 className="w-3.5 h-3.5" />,
  environmental: <Leaf className="w-3.5 h-3.5" />,
}

interface LayersPanelProps {
  activeLayerIds: Set<string>
  onToggle: (id: string) => void
  hasAnalysis: boolean
}

export function LayersPanel({ activeLayerIds, onToggle, hasAnalysis }: LayersPanelProps) {
=======
import { Cloud, Flame, Droplets, Mountain, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ActiveOverlays {
  carbonEmissions: boolean
  wildfireRisk: boolean
  floodZone: boolean
  seismicHazard: boolean
}

interface LayersPanelProps {
  activeOverlays: ActiveOverlays
  onToggle: (key: keyof ActiveOverlays) => void
}

export function LayersPanel({ activeOverlays, onToggle }: LayersPanelProps) {
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
  return (
    <div className="w-56 rounded-2xl bg-background/70 backdrop-blur-xl border border-border/50 shadow-2xl shadow-black/30 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40">
        <Layers className="w-3.5 h-3.5 text-primary" />
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Overlays
        </span>
      </div>

      {/* Toggle rows */}
      <div className="p-3 space-y-1">
<<<<<<< HEAD
        {LAYER_CATEGORIES.map((cat) => (
          <OverlayToggle
            key={cat.id}
            icon={LAYER_ICONS[cat.id]}
            label={cat.label}
            color={cat.color}
            checked={activeLayerIds.has(cat.id)}
            onCheckedChange={() => hasAnalysis && onToggle(cat.id)}
          />
        ))}
=======
        <OverlayToggle
          icon={<Cloud className="w-3.5 h-3.5" />}
          label="Carbon Emissions"
          color="text-orange-400"
          checked={activeOverlays.carbonEmissions}
          onCheckedChange={() => onToggle('carbonEmissions')}
        />
        <OverlayToggle
          icon={<Flame className="w-3.5 h-3.5" />}
          label="Wildfire Risk"
          color="text-red-400"
          checked={activeOverlays.wildfireRisk}
          onCheckedChange={() => onToggle('wildfireRisk')}
        />
        <OverlayToggle
          icon={<Droplets className="w-3.5 h-3.5" />}
          label="Flood Zone"
          color="text-blue-400"
          checked={activeOverlays.floodZone}
          onCheckedChange={() => onToggle('floodZone')}
        />
        <OverlayToggle
          icon={<Mountain className="w-3.5 h-3.5" />}
          label="Seismic Hazard"
          color="text-purple-400"
          checked={activeOverlays.seismicHazard}
          onCheckedChange={() => onToggle('seismicHazard')}
        />
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
      </div>
    </div>
  )
}

function OverlayToggle({
  icon,
  label,
  color,
  checked,
  onCheckedChange,
}: {
  icon: React.ReactNode
  label: string
  color: string
  checked: boolean
  onCheckedChange: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-3 px-1 py-1.5 rounded-lg hover:bg-secondary/40 transition-colors group">
      <div className="flex items-center gap-2.5">
        <span className={cn('transition-colors', checked ? color : 'text-muted-foreground/40')}>
          {icon}
        </span>
        <Label
          htmlFor={label}
          className="text-xs font-medium text-foreground cursor-pointer select-none"
        >
          {label}
        </Label>
      </div>
      <Switch
        id={label}
        checked={checked}
        onCheckedChange={onCheckedChange}
        className="data-[state=checked]:bg-primary scale-75 origin-right"
      />
    </div>
  )
}
