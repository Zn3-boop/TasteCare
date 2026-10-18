import { useCallback, useState } from 'react'
import { qlooSearch, qlooRecommend, qlooCrossDomain, type QlooEntity } from '../api'
import { useTasteMemory } from './useTasteMemory'

type Busy = { setLoading: (v: boolean) => void; setError: (e: string) => void }

/**
 * Tastes / Discover tab state and actions (search, recommend, cross-domain bridge).
 */
export function useTastes({ setLoading, setError }: Busy) {
  const memory = useTasteMemory()
  const [domain, setDomain] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<QlooEntity[]>([])
  // Default anchor so the Taste Bridge constellation + preheat can light up the
  // moment Qloo connects. 'seed-*' ids are placeholder names; resolveSeeds maps
  // them to real Qloo UUIDs before any API call.
  const [seeds, setSeeds] = useState<QlooEntity[]>([
    { id: 'seed-frank-sinatra', name: 'Frank Sinatra', type: 'artist', domain: 'music' },
  ])
  const [recs, setRecs] = useState<QlooEntity[]>([])
  const [crossRes, setCrossRes] = useState<Record<string, QlooEntity[]>>({})

  // Quick-pill / default anchors are names, not Qloo UUIDs. Resolve any
  // 'seed-*' placeholder through /qloo/search so the Taste Bridge and Tastes
  // recommend flow always receive real taste-graph anchors (the Discover tab's
  // "Play Maria's Journey" + the first-screen hero preheat both rely on this).
  const resolveSeeds = useCallback(async (seedList: QlooEntity[]): Promise<QlooEntity[]> => {
    const out: QlooEntity[] = []
    for (const s of seedList) {
      if (s.id && !s.id.startsWith('seed-')) { out.push(s); continue }
      try {
        const hits = await qlooSearch(s.name, s.domain || undefined, 3)
        const hit = hits.find(h => h.id) || hits[0]
        out.push(hit && hit.id ? { ...s, id: hit.id, type: hit.type || s.type, score: hit.score } : s)
      } catch { out.push(s) }
    }
    return out
  }, [])

  const doSearch = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true); setError('')
    try { setResults(await qlooSearch(query, domain || undefined, 15)) } catch (e) { setError(String(e)) }
    setLoading(false)
  }, [query, domain, setLoading, setError])

  const doRecommend = useCallback(async () => {
    if (!seeds.length) return
    setLoading(true); setError('')
    const resolved = await resolveSeeds(seeds)
    const allIds = [...memory.entityIds, ...resolved.map(s => s.id)].filter((v, i, a) => a.indexOf(v) === i)
    try { const r = await qlooRecommend(allIds, domain || undefined, 12); setRecs(r.recommendations || []) } catch (e) { setError(String(e)) }
    setLoading(false)
  }, [seeds, resolveSeeds, memory.entityIds, domain, setLoading, setError])

  const doCross = useCallback(async () => {
    if (!seeds.length) return
    setLoading(true); setError('')
    const resolved = await resolveSeeds(seeds)
    const allIds = [...memory.entityIds, ...resolved.map(s => s.id)].filter((v, i, a) => a.indexOf(v) === i)
    try { setCrossRes((await qlooCrossDomain(allIds)).results || {}) } catch (e) { setError(String(e)) }
    setLoading(false)
  }, [seeds, resolveSeeds, memory.entityIds, setLoading, setError])

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
