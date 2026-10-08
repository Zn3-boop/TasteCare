import { useState, useEffect, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

export interface TasteCareRecommendation {
  id: string
  name: string
  type?: string
  image?: string
  tags?: string[]
  popularity?: number
  health?: {
    passes: boolean
    labels: string[]
    warnings: string[]
  }
}

export interface TasteCareResult {
  recommendations: TasteCareRecommendation[]
  source?: string
  location?: string
  active_constraints?: string[]
  explanation?: string
  disclaimer?: string
}

export interface TasteCareStatus {
  enabled: boolean
  api_key_set: boolean
  base_url?: string
  supported_constraints?: string[]
  disclaimer?: string
}

export function useTasteCare() {
  const [status, setStatus] = useState<TasteCareStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshStatus = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/tastecare/status`)
      if (resp.ok) {
        setStatus(await resp.json())
      }
    } catch {
      setStatus({ enabled: false, api_key_set: false })
    }
  }, [])

  useEffect(() => { refreshStatus() }, [refreshStatus])

  const recommend = useCallback(async (input: {
    cultural_likes: string[]
    location?: string
    constraints?: Record<string, unknown>
    take?: number
  }): Promise<TasteCareResult> => {
    setLoading(true); setError(null)
    try {
      const resp = await fetch(`${API_BASE}/tastecare/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cultural_likes: input.cultural_likes,
          location: input.location || undefined,
          constraints: input.constraints || {},
          take: input.take || 12,
        }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => null)
        throw new Error(body?.detail || `Recommend failed: ${resp.status}`)
      }
      return await resp.json()
    } catch (e) {
      setError(String(e))
      return { recommendations: [] }
    } finally { setLoading(false) }
  }, [])

  return { status, loading, error, recommend, refreshStatus }
}