import { motion } from 'framer-motion'
import { DataSiteAILogo } from './DataSiteAILogo'
import { DashboardPreview } from './DashboardPreview'
import { FooterFeatures } from './FooterFeatures'
import { WaveBackground } from './WaveBackground'

interface LandingPageProps {
  onGetStarted: () => void
}

export function LandingPage({ onGetStarted }: LandingPageProps) {
  return (
    <div className="relative min-h-screen bg-slate-950">
      <WaveBackground />

      <div className="relative z-10 flex min-h-screen flex-col">
        {/* Hero */}
        <main className="flex flex-1 items-center">
          <div className="mx-auto w-full max-w-7xl px-6 py-20 lg:px-8">
            <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-20">

              {/* Left — text & CTA */}
              <motion.div
                className="flex flex-col items-start"
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
              >
                <div className="mb-10">
                  <DataSiteAILogo className="h-20 w-20" />
                </div>

                <h1 className="mb-3 text-5xl font-semibold tracking-tight lg:text-6xl">
                  <span className="bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                    DATASITE
                  </span>
                  <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                    AI
                  </span>
                </h1>

                <p className="mb-6 text-lg font-medium tracking-wide text-slate-400">
                  Intelligent Infrastructure Siting
                </p>

                <p className="mb-10 max-w-lg text-base leading-relaxed text-slate-500">
                  Analyze power grids, environmental risks, and fiber connectivity to identify
                  optimal data center locations. AI-powered insights delivered in milliseconds.
                </p>

                <button
                  onClick={onGetStarted}
                  className="group relative overflow-hidden rounded-full bg-gradient-to-r from-blue-500 to-cyan-500 px-8 py-3.5 font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:shadow-xl hover:shadow-blue-500/35 hover:scale-[1.02] active:scale-[0.99]"
                >
                  <span className="relative flex items-center gap-2 text-sm tracking-wide">
                    Get Started
                    <svg
                      className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                    </svg>
                  </span>
                </button>
              </motion.div>

              {/* Right — dashboard preview */}
              <motion.div
                className="flex justify-center lg:justify-end"
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.65, delay: 0.15, ease: 'easeOut' }}
              >
                <div className="w-full max-w-lg">
                  <DashboardPreview />
                </div>
              </motion.div>
            </div>
          </div>
        </main>

        {/* Footer features */}
        <footer className="border-t border-slate-800/50">
          <div className="mx-auto max-w-7xl px-6 py-16 lg:px-8">
            <FooterFeatures />
          </div>
        </footer>
      </div>
    </div>
  )
}
