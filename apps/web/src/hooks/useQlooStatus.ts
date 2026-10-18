import { useEffect, useState } from 'react'
import { qlooStatus } from '../api'

export type QlooStatus = {
  enabled: boolean
  api_key_set: boolean
  base_url?: string
  data_source?: 'live' | 'preview' | null
}

/**
 * Qloo 连接状态 — 挂载时探测一次 /api/v1/qloo/status。
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
