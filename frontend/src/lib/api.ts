const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8001'

export interface AnalyzeRequest {
  bbox: { min_lat: number; min_lng: number; max_lat: number; max_lng: number }
  state: string
  grid_resolution_km?: number
  min_acres?: number
  max_acres?: number
  include_listings?: boolean
}

export interface ScoreBundle {
  location: { lat: number; lng: number; cell_polygon: object }
  composite_score: {
    composite: number
    weighted_contributions: Record<string, number>
    weights_used: Record<string, number>
  }
  scores: Record<string, number>
  metrics: Record<string, unknown>
}

export interface AnalyzeResponse {
  analysis_id: string
  grid_cells: ScoreBundle[]
  listings: unknown[]
  layers_available: string[]
  layer_urls: Record<string, string>
  metadata: {
    grid_cells_analyzed: number
    processing_time_ms: number
    weights_used: Record<string, number>
  }
}

export async function runAnalysis(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) throw new Error(`Analysis failed: ${res.status}`)
  return res.json()
}

export async function fetchLayer(analysisId: string, layerId: string): Promise<object> {
  const res = await fetch(`${API_BASE}/api/v1/layers/${layerId}?analysis_id=${analysisId}`)
  if (!res.ok) throw new Error(`Layer fetch failed: ${res.status}`)
  return res.json()
}

export async function sendChatMessage(payload: {
  message: string
  history: { role: string; content: string }[]
  location_context: { lat: number; lng: number } | null
}): Promise<{ reply: string }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function detectState(lat: number, lng: number): string {
  if (33.8 <= lat && lat <= 36.6 && -84.3 <= lng && lng <= -75.5) return 'NC'
  if (37.0 <= lat && lat <= 39.5 && -83.7 <= lng && lng <= -75.2) return 'VA'
  if (25.8 <= lat && lat <= 36.5 && -106.7 <= lng && lng <= -93.5) return 'TX'
  if (30.4 <= lat && lat <= 35.0 && -85.6 <= lng && lng <= -80.8) return 'GA'
  if (34.9 <= lat && lat <= 36.7 && -90.3 <= lng && lng <= -81.6) return 'TN'
  if (36.9 <= lat && lat <= 41.0 && -109.1 <= lng && lng <= -102.0) return 'CO'
  if (31.3 <= lat && lat <= 37.0 && -114.8 <= lng && lng <= -109.0) return 'AZ'
  if (24.5 <= lat && lat <= 31.0 && -87.6 <= lng && lng <= -80.0) return 'FL'
  if (37.0 <= lat && lat <= 42.0 && -80.5 <= lng && lng <= -74.0) return 'PA'
  if (40.5 <= lat && lat <= 45.0 && -79.8 <= lng && lng <= -71.9) return 'NY'
  return 'NC'
}

export const LAYER_CATEGORIES = [
  { id: 'power',         label: 'Power & Energy',       color: 'text-yellow-400' },
  { id: 'water',         label: 'Water & Flood Risk',   color: 'text-blue-400'   },
  { id: 'geological',    label: 'Geology & Terrain',    color: 'text-purple-400' },
  { id: 'climate',       label: 'Climate & Weather',    color: 'text-orange-400' },
  { id: 'connectivity',  label: 'Connectivity',         color: 'text-cyan-400'   },
  { id: 'economic',      label: 'Economic',             color: 'text-green-400'  },
  { id: 'environmental', label: 'Environmental Impact', color: 'text-emerald-400'},
] as const
