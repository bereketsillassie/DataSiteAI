export function DashboardPreview() {
  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-slate-700/50 bg-slate-900/80 shadow-2xl shadow-black/50">
      {/* Window chrome */}
      <div className="flex items-center gap-2 border-b border-slate-700/50 bg-slate-800/50 px-4 py-3">
        <div className="flex gap-1.5">
          <div className="h-3 w-3 rounded-full bg-slate-600" />
          <div className="h-3 w-3 rounded-full bg-slate-600" />
          <div className="h-3 w-3 rounded-full bg-slate-600" />
        </div>
        <div className="ml-4 flex-1 rounded-md bg-slate-700/50 px-3 py-1">
          <span className="text-xs text-slate-400">app.datasiteai.com</span>
        </div>
      </div>

      {/* Dashboard content */}
      <div className="p-4">
        {/* Top stats bar */}
        <div className="mb-4 grid grid-cols-3 gap-3">
          <div className="rounded-lg bg-slate-800/50 p-3">
            <div className="mb-1 text-xs text-slate-500">Sites Analyzed</div>
            <div className="text-lg font-semibold text-white">2,847</div>
          </div>
          <div className="rounded-lg bg-slate-800/50 p-3">
            <div className="mb-1 text-xs text-slate-500">Avg Score</div>
            <div className="text-lg font-semibold text-cyan-400">84.2</div>
          </div>
          <div className="rounded-lg bg-slate-800/50 p-3">
            <div className="mb-1 text-xs text-slate-500">Risk Level</div>
            <div className="text-lg font-semibold text-emerald-400">Low</div>
          </div>
        </div>

        {/* Main chart area */}
        <div className="mb-4 rounded-lg bg-slate-800/30 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Site Suitability Over Time</span>
            <div className="flex gap-2">
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <span className="h-2 w-2 rounded-full bg-cyan-500" />Power
              </span>
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <span className="h-2 w-2 rounded-full bg-blue-500" />Network
              </span>
            </div>
          </div>

          <div className="relative h-32">
            <svg viewBox="0 0 400 100" className="h-full w-full" preserveAspectRatio="none">
              <line x1="0" y1="25" x2="400" y2="25" stroke="currentColor" className="text-slate-700/50" strokeWidth="1" />
              <line x1="0" y1="50" x2="400" y2="50" stroke="currentColor" className="text-slate-700/50" strokeWidth="1" />
              <line x1="0" y1="75" x2="400" y2="75" stroke="currentColor" className="text-slate-700/50" strokeWidth="1" />
              <defs>
                <linearGradient id="cyanGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgb(6, 182, 212)" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="rgb(6, 182, 212)" stopOpacity="0" />
                </linearGradient>
                <linearGradient id="blueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgb(59, 130, 246)" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="rgb(59, 130, 246)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M0,60 Q50,55 100,45 T200,35 T300,25 T400,20 L400,100 L0,100 Z" fill="url(#cyanGradient)" />
              <path d="M0,70 Q50,68 100,60 T200,50 T300,40 T400,35 L400,100 L0,100 Z" fill="url(#blueGradient)" />
              <path d="M0,60 Q50,55 100,45 T200,35 T300,25 T400,20" fill="none" stroke="rgb(6, 182, 212)" strokeWidth="2" />
              <path d="M0,70 Q50,68 100,60 T200,50 T300,40 T400,35" fill="none" stroke="rgb(59, 130, 246)" strokeWidth="2" />
              <circle cx="100" cy="45" r="3" fill="rgb(6, 182, 212)" />
              <circle cx="200" cy="35" r="3" fill="rgb(6, 182, 212)" />
              <circle cx="300" cy="25" r="3" fill="rgb(6, 182, 212)" />
            </svg>
          </div>
        </div>

        {/* Bottom section */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-slate-800/30 p-3">
            <div className="mb-2 text-xs font-medium text-slate-400">Location Score</div>
            <div className="flex items-end gap-1">
              {[26, 31, 33, 30, 35, 37, 34].map((h, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-sm bg-gradient-to-t from-blue-600 to-cyan-500"
                  style={{ height: `${h}px` }}
                />
              ))}
            </div>
          </div>
          <div className="rounded-lg bg-slate-800/30 p-3">
            <div className="mb-2 text-xs font-medium text-slate-400">Risk Analysis</div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Flood</span>
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-700">
                  <div className="h-full w-[15%] rounded-full bg-emerald-500" />
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Seismic</span>
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-700">
                  <div className="h-full w-[25%] rounded-full bg-emerald-500" />
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Fire</span>
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-700">
                  <div className="h-full w-[10%] rounded-full bg-emerald-500" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
