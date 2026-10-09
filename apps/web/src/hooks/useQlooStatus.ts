import { useEffect, useState } from 'react'
import { qlooStatus } from '../api'

export type QlooStatus = { enabled: boolean; api_key_set: boolean }

/**
 * Qloo 连接状态 — 挂载时探测一次 /api/v1/qloo/status。
 */
export function useQlooStatus() {
  const [status, setStatus] = useState<QlooStatus | null>(null)
  useEffect(() => { qlooStatus().then(setStatus) }, [])
  return { status, setStatus }
}
