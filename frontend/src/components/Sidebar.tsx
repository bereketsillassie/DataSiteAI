import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Zap, Droplets, Mountain, Wind, Wifi, TrendingUp, Leaf, Star, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'

const LAYERS = [
  { id: 'optimal',       label: 'Optimal Score',    icon: Star,       color: 'text-yellow-400'  },
  { id: 'power',         label: 'Power & Energy',   icon: Zap,        color: 'text-yellow-300'  },
  { id: 'water',         label: 'Water & Flood',    icon: Droplets,   color: 'text-blue-400'    },
  { id: 'geological',    label: 'Geology & Terrain',icon: Mountain,   color: 'text-orange-400'  },
  { id: 'climate',       label: 'Climate & Weather',icon: Wind,       color: 'text-cyan-400'    },
  { id: 'connectivity',  label: 'Connectivity',     icon: Wifi,       color: 'text-green-400'   },
  { id: 'economic',      label: 'Economic',         icon: TrendingUp, color: 'text-emerald-400' },
  { id: 'environmental', label: 'Environmental',    icon: Leaf,       color: 'text-lime-400'    },
]

interface LayersPanelProps {
  activeLayerIds: Set<string>
  onToggle: (id: string) => void
}

export function LayersPanel({ activeLayerIds, onToggle }: LayersPanelProps) {
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
        {LAYERS.map(({ id, label, icon: Icon, color }) => (
          <OverlayToggle
            key={id}
            icon={<Icon className="w-3.5 h-3.5" />}
            label={label}
            color={color}
            checked={activeLayerIds.has(id)}
            onCheckedChange={() => onToggle(id)}
          />
        ))}
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