const EQUALIZER_BARS = [
  { x: 0, y: 40, h: 40 }, { x: 8, y: 35, h: 45 }, { x: 16, y: 28, h: 52 },
  { x: 24, y: 25, h: 55 }, { x: 32, y: 30, h: 50 }, { x: 40, y: 38, h: 42 },
  { x: 48, y: 45, h: 35 }, { x: 56, y: 42, h: 38 }, { x: 64, y: 32, h: 48 },
  { x: 72, y: 25, h: 55 }, { x: 80, y: 22, h: 58 }, { x: 88, y: 28, h: 52 },
  { x: 96, y: 36, h: 44 }, { x: 104, y: 42, h: 38 }, { x: 112, y: 45, h: 35 },
  { x: 120, y: 40, h: 40 }, { x: 128, y: 30, h: 50 }, { x: 136, y: 24, h: 56 },
  { x: 144, y: 26, h: 54 }, { x: 152, y: 34, h: 46 }, { x: 160, y: 42, h: 38 },
  { x: 168, y: 46, h: 34 }, { x: 176, y: 42, h: 38 }, { x: 184, y: 34, h: 46 },
  { x: 192, y: 26, h: 54 }, { x: 200, y: 22, h: 58 }, { x: 208, y: 26, h: 54 },
  { x: 216, y: 34, h: 46 }, { x: 224, y: 42, h: 38 }, { x: 232, y: 45, h: 35 },
  { x: 240, y: 40, h: 40 }, { x: 248, y: 32, h: 48 }, { x: 256, y: 25, h: 55 },
  { x: 264, y: 24, h: 56 }, { x: 272, y: 30, h: 50 }, { x: 280, y: 38, h: 42 },
  { x: 288, y: 44, h: 36 }, { x: 296, y: 42, h: 38 }, { x: 304, y: 35, h: 45 },
  { x: 312, y: 28, h: 52 },
]

export function WaveBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* Base gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950" />

      {/* Wave graphics — top right */}
      <svg
        className="absolute -right-20 top-20 h-64 w-96 opacity-20"
        viewBox="0 0 400 200"
        fill="none"
      >
        <defs>
          <linearGradient id="wave1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3b82f6" />
            <stop offset="50%" stopColor="#06b6d4" />
            <stop offset="100%" stopColor="#a5f3fc" />
          </linearGradient>
        </defs>
        <path d="M0,100 Q50,60 100,100 T200,100 T300,100 T400,100" stroke="url(#wave1)" strokeWidth="1.5" fill="none" opacity="1" />
        <path d="M0,108 Q50,68 100,108 T200,108 T300,108 T400,108" stroke="url(#wave1)" strokeWidth="1.5" fill="none" opacity="0.85" />
        <path d="M0,116 Q50,76 100,116 T200,116 T300,116 T400,116" stroke="url(#wave1)" strokeWidth="1.5" fill="none" opacity="0.7" />
        <path d="M0,124 Q50,84 100,124 T200,124 T300,124 T400,124" stroke="url(#wave1)" strokeWidth="1.5" fill="none" opacity="0.55" />
        <path d="M0,132 Q50,92 100,132 T200,132 T300,132 T400,132" stroke="url(#wave1)" strokeWidth="1.5" fill="none" opacity="0.4" />
      </svg>

      {/* Equalizer bars — bottom right */}
      <svg
        className="absolute -bottom-10 right-1/4 h-32 w-80 opacity-15"
        viewBox="0 0 320 80"
        fill="none"
      >
        <defs>
          <linearGradient id="bars1" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#1e40af" />
            <stop offset="100%" stopColor="#60a5fa" />
          </linearGradient>
        </defs>
        {EQUALIZER_BARS.map((bar, i) => (
          <rect key={i} x={bar.x} y={bar.y} width="3" height={bar.h} fill="url(#bars1)" rx="1.5" />
        ))}
      </svg>

      {/* Concentric circles — top left */}
      <svg
        className="absolute -left-32 top-1/3 h-80 w-80 opacity-10"
        viewBox="0 0 200 200"
        fill="none"
      >
        <defs>
          <linearGradient id="circle1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>
        </defs>
        <circle cx="100" cy="100" r="30" stroke="url(#circle1)" strokeWidth="1" fill="none" opacity="1" />
        <circle cx="100" cy="100" r="45" stroke="url(#circle1)" strokeWidth="1" fill="none" opacity="0.85" />
        <circle cx="100" cy="100" r="60" stroke="url(#circle1)" strokeWidth="1" fill="none" opacity="0.7" />
        <circle cx="100" cy="100" r="75" stroke="url(#circle1)" strokeWidth="1" fill="none" opacity="0.55" />
        <circle cx="100" cy="100" r="90" stroke="url(#circle1)" strokeWidth="1" fill="none" opacity="0.4" />
      </svg>

      {/* Flowing lines — center top */}
      <svg
        className="absolute left-1/2 top-10 h-48 w-72 -translate-x-1/2 opacity-10"
        viewBox="0 0 300 150"
        fill="none"
      >
        <defs>
          <linearGradient id="flow1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#818cf8" />
            <stop offset="50%" stopColor="#38bdf8" />
            <stop offset="100%" stopColor="#34d399" />
          </linearGradient>
        </defs>
        <path d="M0,75 C75,40 150,110 225,75 S300,40 300,75" stroke="url(#flow1)" strokeWidth="1.5" fill="none" opacity="0.8" />
        <path d="M0,87 C75,52 150,122 225,87 S300,52 300,87" stroke="url(#flow1)" strokeWidth="1.5" fill="none" opacity="0.68" />
        <path d="M0,99 C75,64 150,134 225,99 S300,64 300,99" stroke="url(#flow1)" strokeWidth="1.5" fill="none" opacity="0.56" />
        <path d="M0,111 C75,76 150,146 225,111 S300,76 300,111" stroke="url(#flow1)" strokeWidth="1.5" fill="none" opacity="0.44" />
        <path d="M0,123 C75,88 150,158 225,123 S300,88 300,123" stroke="url(#flow1)" strokeWidth="1.5" fill="none" opacity="0.32" />
      </svg>

      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `
            linear-gradient(to right, rgb(148 163 184) 1px, transparent 1px),
            linear-gradient(to bottom, rgb(148 163 184) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />
    </div>
  )
}
