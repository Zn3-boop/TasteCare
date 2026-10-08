import { useCallback, useState } from 'react'

/**
 * Search history persisted to localStorage (P3).
 * Dedupes entries, most-recent first, capped at `limit`.
 */
export function useSearchHistory(key: string, limit = 6) {
  const [history, setHistory] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw ? (JSON.parse(raw) as string[]) : []
    } catch { return [] }
  })

  const add = useCallback((entry: string) => {
    const e = entry.trim()
    if (!e) return
    setHistory(h => {
      const next = [e, ...h.filter(x => x !== e)].slice(0, limit)
      try { localStorage.setItem(key, JSON.stringify(next)) } catch { /* storage full/blocked */ }
      return next
    })
  }, [key, limit])

  const clear = useCallback(() => {
    try { localStorage.removeItem(key) } catch { /* noop */ }
    setHistory([])
  }, [key])

  return { history, add, clear }
}