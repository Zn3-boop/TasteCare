import { useCallback, useState } from 'react'
import { qlooSearch, qlooRecommend, qlooCrossDomain, type QlooEntity } from '../api'

type Busy = { setLoading: (v: boolean) => void; setError: (e: string) => void }

/**
 * Tastes / Discover tab 的状态与动作（搜索、推荐、跨域桥）。
 */
export function useTastes({ setLoading, setError }: Busy) {
  const [domain, setDomain] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<QlooEntity[]>([])
  const [seeds, setSeeds] = useState<QlooEntity[]>([])
  const [recs, setRecs] = useState<QlooEntity[]>([])
  const [crossRes, setCrossRes] = useState<Record<string, QlooEntity[]>>({})

  const doSearch = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true); setError('')
    try { setResults(await qlooSearch(query, domain || undefined, 15)) } catch (e) { setError(String(e)) }
    setLoading(false)
  }, [query, domain, setLoading, setError])

  const doRecommend = useCallback(async () => {
    if (!seeds.length) return
    setLoading(true); setError('')
    try { const r = await qlooRecommend(seeds.map(s => s.id), domain || undefined, 12); setRecs(r.recommendations || []) } catch (e) { setError(String(e)) }
    setLoading(false)
  }, [seeds, domain, setLoading, setError])

  const doCross = useCallback(async () => {
    if (!seeds.length) return
    setLoading(true); setError('')
    try { setCrossRes((await qlooCrossDomain(seeds.map(s => s.id))).results || {}) } catch (e) { setError(String(e)) }
    setLoading(false)
  }, [seeds, setLoading, setError])

  return {
    domain, setDomain,
    query, setQuery,
    results, setResults,
    seeds, setSeeds,
    recs, setRecs,
    crossRes, setCrossRes,
    doSearch, doRecommend, doCross,
  }
}
