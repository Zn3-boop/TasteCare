import { useState, useEffect, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

export interface QlooEntity {
  id: string
  name: string
  type?: string
  domain?: string
  score?: number
  popularity?: number
}

export interface QlooStatus {
  enabled: boolean
  api_key_set: boolean
  base_url?: string
}

export function useQloo() {
  const [status, setStatus] = useState<QlooStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshStatus = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/qloo/status`)
      if (resp.ok) {
        const data = await resp.json()
        setStatus(data)
      }
    } catch {
      setStatus({ enabled: false, api_key_set: false })
    }
  }, [])

  useEffect(() => { refreshStatus() }, [refreshStatus])

  const search = useCallback(async (query: string, domain?: string, limit?: number): Promise<QlooEntity[]> => {
    setLoading(true); setError(null)
    try {
      const resp = await fetch(`${API_BASE}/qloo/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, domain, limit: limit || 10 }),
      })
      if (!resp.ok) throw new Error(`Search failed: ${resp.status}`)
      const data = await resp.json()
      return data.results || []
    } catch (e) {
      setError(String(e))
      return []
    } finally { setLoading(false) }
  }, [])

  const recommend = useCallback(async (seedEntityIds: string[], targetDomain?: string, limit?: number) => {
    setLoading(true); setError(null)
    try {
      const resp = await fetch(`${API_BASE}/qloo/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seed_entity_ids: seedEntityIds, target_domain: targetDomain, limit: limit || 10 }),
      })
      if (!resp.ok) throw new Error(`Recommend failed: ${resp.status}`)
      return await resp.json()
    } catch (e) {
      setError(String(e))
      return { recommendations: [] }
    } finally { setLoading(false) }
  }, [])

  const crossDomain = useCallback(async (seedEntityIds: string[], domains?: string[]) => {
    setLoading(true); setError(null)
    try {
      const resp = await fetch(`${API_BASE}/qloo/cross-domain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seed_entity_ids: seedEntityIds, domains }),
      })
      if (!resp.ok) throw new Error(`Cross-domain failed: ${resp.status}`)
      return await resp.json()
    } catch (e) {
      setError(String(e))
      return { results: {} }
    } finally { setLoading(false) }
  }, [])

  return { status, loading, error, search, recommend, crossDomain, refreshStatus }
}