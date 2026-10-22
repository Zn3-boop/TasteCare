import { useEffect, useState } from 'react'
import { qlooStatus } from '../api'

export type QlooStatus = {
  enabled: boolean
  api_key_set: boolean
  base_url?: string
  data_source?: 'live' | 'preview' | null
}

/**
 * Qloo connection status — probes /api/v1/qloo/status once on mount.
 */
export function useQlooStatus() {
  const [status, setStatus] = useState<QlooStatus | null>(null)
  useEffect(() => {
    qlooStatus().then(setStatus)
    const id = setInterval(() => qlooStatus().then(setStatus), 30_000)
    return () => clearInterval(id)
  }, [])
  return { status, setStatus }
}
