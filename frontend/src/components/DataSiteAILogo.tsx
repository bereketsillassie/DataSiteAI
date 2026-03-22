export function DataSiteAILogo({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 120 100"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="rackGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#1e40af" />
          <stop offset="50%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#1d4ed8" />
        </linearGradient>
        <linearGradient id="rackHighlight" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
          <stop offset="50%" stopColor="#60a5fa" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.2" />
        </linearGradient>
        <linearGradient id="nodeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#34d399" />
          <stop offset="100%" stopColor="#10b981" />
        </linearGradient>
        <radialGradient id="centerNode" cx="30%" cy="30%">
          <stop offset="0%" stopColor="#6ee7b7" />
          <stop offset="100%" stopColor="#059669" />
        </radialGradient>
        <filter id="rackShadow" x="-20%" y="-10%" width="140%" height="130%">
          <feDropShadow dx="2" dy="4" stdDeviation="3" floodColor="#1e3a5f" floodOpacity="0.4" />
        </filter>
        <filter id="innerGlow">
          <feGaussianBlur in="SourceAlpha" stdDeviation="1" result="blur" />
          <feOffset in="blur" dx="0" dy="1" result="offsetBlur" />
          <feComposite in="SourceGraphic" in2="offsetBlur" operator="over" />
        </filter>
      </defs>

      {/* Network connection lines */}
      <line x1="40" y1="18" x2="60" y2="8" stroke="url(#nodeGradient)" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="80" y1="18" x2="60" y2="8" stroke="url(#nodeGradient)" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="40" y1="18" x2="60" y2="28" stroke="url(#nodeGradient)" strokeWidth="2" strokeLinecap="round" opacity="0.8" />
      <line x1="80" y1="18" x2="60" y2="28" stroke="url(#nodeGradient)" strokeWidth="2" strokeLinecap="round" opacity="0.8" />

      {/* Outer nodes */}
      <circle cx="40" cy="18" r="5" fill="url(#nodeGradient)" />
      <circle cx="40" cy="18" r="3" fill="#6ee7b7" opacity="0.5" />
      <circle cx="80" cy="18" r="5" fill="url(#nodeGradient)" />
      <circle cx="80" cy="18" r="3" fill="#6ee7b7" opacity="0.5" />

      {/* Top center node */}
      <circle cx="60" cy="8" r="4" fill="url(#nodeGradient)" />
      <circle cx="60" cy="8" r="2" fill="#a7f3d0" opacity="0.6" />

      {/* Center hub node */}
      <circle cx="60" cy="28" r="6" fill="url(#centerNode)" />
      <circle cx="60" cy="28" r="3.5" fill="#6ee7b7" opacity="0.4" />

      {/* Server Rack 1 — Left */}
      <g filter="url(#rackShadow)">
        <rect x="18" y="40" width="24" height="55" rx="3" fill="url(#rackGradient)" />
        <rect x="18" y="40" width="6" height="55" rx="3" fill="url(#rackHighlight)" />
        <rect x="22" y="46" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="22" y="54" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
        <rect x="22" y="62" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="22" y="70" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
        <rect x="22" y="78" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="22" y="86" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
      </g>

      {/* Server Rack 2 — Center (taller) */}
      <g filter="url(#rackShadow)">
        <rect x="48" y="38" width="24" height="57" rx="3" fill="url(#rackGradient)" />
        <rect x="48" y="38" width="6" height="57" rx="3" fill="url(#rackHighlight)" />
        <rect x="52" y="44" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="52" y="52" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
        <rect x="52" y="60" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="52" y="68" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
        <rect x="52" y="76" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="52" y="84" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
      </g>

      {/* Server Rack 3 — Right */}
      <g filter="url(#rackShadow)">
        <rect x="78" y="40" width="24" height="55" rx="3" fill="url(#rackGradient)" />
        <rect x="78" y="40" width="6" height="55" rx="3" fill="url(#rackHighlight)" />
        <rect x="82" y="46" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="82" y="54" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
        <rect x="82" y="62" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="82" y="70" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
        <rect x="82" y="78" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.4" />
        <rect x="82" y="86" width="16" height="4" rx="1" fill="#60a5fa" opacity="0.35" />
      </g>

      {/* Dashed connection lines from hub to racks */}
      <line x1="60" y1="34" x2="30" y2="40" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" strokeDasharray="2 2" />
      <line x1="60" y1="34" x2="60" y2="38" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" strokeDasharray="2 2" />
      <line x1="60" y1="34" x2="90" y2="40" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" strokeDasharray="2 2" />
    </svg>
  )
}
