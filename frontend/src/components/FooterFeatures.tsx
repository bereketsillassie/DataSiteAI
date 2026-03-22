import { Gauge, Map, Sparkles } from 'lucide-react'

const features = [
  {
    icon: Gauge,
    title: 'Instant Site Scoring',
    description: 'Get comprehensive site ratings in milliseconds with our proprietary AI algorithms.',
  },
  {
    icon: Map,
    title: 'Live Infrastructure Mapping',
    description: 'Real-time visualization of power grids, fiber routes, and utility connections.',
  },
  {
    icon: Sparkles,
    title: 'AI-Powered Insights',
    description: 'Machine learning models trained on thousands of successful data center deployments.',
  },
]

export function FooterFeatures() {
  return (
    <div className="grid gap-6 md:grid-cols-3">
      {features.map((feature) => (
        <div
          key={feature.title}
          className="group rounded-xl border border-slate-800/60 bg-slate-900/50 p-6 transition-all hover:border-slate-700/80 hover:bg-slate-900/80"
        >
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/10 to-blue-600/10 transition-colors group-hover:from-cyan-500/20 group-hover:to-blue-600/20">
            <feature.icon className="h-5 w-5 text-cyan-400" />
          </div>
          <h3 className="mb-2 text-base font-semibold text-slate-200">{feature.title}</h3>
          <p className="text-sm leading-relaxed text-slate-500">{feature.description}</p>
        </div>
      ))}
    </div>
  )
}
