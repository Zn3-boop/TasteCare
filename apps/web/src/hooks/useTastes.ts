import { useCallback, useState } from 'react'
import { qlooSearch, qlooRecommend, qlooCrossDomain, type QlooEntity } from '../api'
import { useTasteMemory } from './useTasteMemory'
import { SENIOR_PERSONA } from '../constants'

type Busy = { setLoading: (v: boolean) => void; setError: (e: string) => void }

// Taste anchors persist across reloads (feedback: anchors added in the Tastes tab
// vanished on refresh — they must survive so the Taste Bridge keeps rendering the
// judge's own additions). Restored on boot; empty/saved lists fall back to the
// classic Frank Sinatra default so the bridge still lights up out of the box.
const SEEDS_KEY = 'tastecare.tastes.seeds.v1'

function loadPersistedSeeds(): QlooEntity[] {
  try {
    const raw = localStorage.getItem(SEEDS_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as unknown
      if (Array.isArray(parsed) && parsed.length) {
        const list = parsed.filter((s): s is QlooEntity => !!s && typeof s === 'object' && typeof s.name === 'string')
        // React 19 crashes on duplicate list keys: a corrupted/legacy store may
        // contain the same seed twice (same id OR same name, e.g. "Jazz" saved as
        // two different seed-* ids). Dedupe by id, then by lowercased name.
        const seenIds = new Set<string>()
        const seenNames = new Set<string>()
        const out: QlooEntity[] = []
        for (const s of list) {
          const k = s.id && !s.id.startsWith('seed-') ? s.id : s.name.toLowerCase()
          if (seenIds.has(k) || seenNames.has(s.name.toLowerCase())) continue
          if (s.id) seenIds.add(s.id)
          seenNames.add(s.name.toLowerCase())
          out.push(s)
        }
        return out.slice(0, 8)
      }
    }
  } catch { /* corrupted storage → fall through to default */ }
  return []
}

/**
 * Persistence-aware seeds setter: writes every seeds change to localStorage from
 * inside the setter (single writer, no extra effect → no double-writes/races).
 * Passing a fresh array OR a functional updater both work, matching the original
 * Dispatch<SetStateAction<QlooEntity[]>> contract callers already rely on.
 */
function persistSeeds(next: QlooEntity[]) {
  try { localStorage.setItem(SEEDS_KEY, JSON.stringify(next.slice(0, 8))) } catch { /* quota/private mode */ }
}

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
  // Persisted anchor list wins on boot (feedback: songs added in the Tastes tab
  // must survive a page refresh and keep rendering on the bridge); otherwise we
  // start with the classic Frank Sinatra default for the out-of-the-box look.
  const [seeds, setSeedsState] = useState<QlooEntity[]>(() => {
    const saved = loadPersistedSeeds()
    if (saved.length) return saved
    // 没有持久化锚点时，用默认 persona（Maria / SENIOR_PERSONA）的完整锚点列表，
    // 而不是单个 Frank Sinatra —— 味觉桥初始就显示全部口味标签
    // （Frank Sinatra, Bob Dylan, Italian cuisine, Jazz, Classic Hollywood films），
    // 与 Tastes tab 的 persona-like 输入保持一致。
    return SENIOR_PERSONA.likes
      .split(',').map(s => s.trim()).filter(Boolean)
      .map((name, i) => ({ id: `seed-${i}-${name}`, name, type: 'taste' as const, domain: '' as const }))
  })

  // The persistence-aware setter both callers (plain value OR functional updater)
  // and the raw state setter share. Reshaped so type stays compatible with the
  // old Dispatch<SetStateAction<QlooEntity[]>> the tabs receive as a prop.
  const setSeeds: React.Dispatch<React.SetStateAction<QlooEntity[]>> = useCallback(
    (updater) => {
      setSeedsState(prev => {
        const next = typeof updater === 'function' ? (updater as (p: QlooEntity[]) => QlooEntity[])(prev) : updater
        persistSeeds(next)
        return next
      })
    },
    [],
  )
  const [recs, setRecs] = useState<QlooEntity[]>([])
  const [crossRes, setCrossRes] = useState<Record<string, QlooEntity[]>>({})
  // Set true once a recommend request completes (success or error), so the
  // Tastes tab can show a friendly empty-state instead of a silent blank list.
  const [recommendTried, setRecommendTried] = useState(false)

  // Shared: merge memory + resolved seed ids, dedupe, and DROP anything that is
  // still a 'seed-*' placeholder or an empty id — invalid ids sent to /qloo/
  // recommend return empty lists (Bug fix root cause #1).
  const collectIds = useCallback((resolved: QlooEntity[]): string[] => {
    const valid = resolved.map(s => s.id).filter((id): id is string => !!id && !id.startsWith('seed-'))
    return [...memory.entityIds, ...valid].filter((v, i, a) => a.indexOf(v) === i)
  }, [memory.entityIds])

  // Quick-pill / default anchors are names, not Qloo UUIDs. Resolve any
  // 'seed-*' placeholder through /qloo/search so the Taste Bridge and Tastes
  // recommend flow always receive real taste-graph anchors (the Discover tab's
  // "Play Maria's Journey" + the first-screen hero preheat both rely on this).
  // Each seed is resolved independently with its own try/catch — an unresolvable
  // anchor is dropped, never allowed to poison the whole request with a fake id.
  const resolveSeeds = useCallback(async (seedList: QlooEntity[]): Promise<QlooEntity[]> => {
    const out: QlooEntity[] = []
    for (const s of seedList) {
      if (s.id && !s.id.startsWith('seed-')) { out.push(s); continue }
      try {
        const hits = await qlooSearch(s.name, s.domain || undefined, 3)
        const hit = hits.find(h => h.id) || hits[0]
        if (hit && hit.id) {
          out.push({ ...s, id: hit.id, type: hit.type || s.type, score: hit.score })
        } else {
          // Resolution failed: skip this seed instead of forwarding 'seed-*'.
          console.warn('[useTastes] seed unresolved, dropping:', s.name)
        }
      } catch (e) {
        console.warn('[useTastes] seed resolve error, dropping:', s.name, e)
      }
    }
    return out
  }, [])

  const doSearch = useCallback(async (domainOverride?: string) => {
    if (!query.trim()) return
    // Override lets the Tastes domain pills re-run the SAME query against a new
    // domain immediately (state is async — the override avoids a stale read).
    const d = domainOverride ?? domain
    console.log('[useTastes:doSearch]', { domain: d, query: query.trim() })
    setLoading(true); setError('')
    try { setResults(await qlooSearch(query, d || undefined, 15)) } catch (e) { setError(String(e)); console.warn('[useTastes:doSearch:error]', e) }
    setLoading(false)
  }, [query, domain, setLoading, setError])

  const doRecommend = useCallback(async (domainOverride?: string) => {
    if (!seeds.length) return
    const d = domainOverride ?? domain
    console.log('[useTastes:doRecommend]', { domainOverride: d, seeds: seeds.map(s => s.name) })
    setLoading(true); setError('')
    setRecommendTried(true)
    const resolved = await resolveSeeds(seeds)
    const allIds = collectIds(resolved)
    console.log('[useTastes:doRecommend] ids', { domain: d, allIds })
    try {
      const r = await qlooRecommend(allIds, d || undefined, 12)
      const list = r.recommendations || []
      console.log('[useTastes:doRecommend:ok]', { domain: d, count: list.length })
      setRecs(list)
    } catch (e) {
      setError(String(e)); console.warn('[useTastes:doRecommend:error]', e)
    }
    setLoading(false)
  }, [seeds, resolveSeeds, collectIds, domain, setLoading, setError])

  const doCross = useCallback(async () => {
    if (!seeds.length) return
    setLoading(true); setError('')
    const resolved = await resolveSeeds(seeds)
    const allIds = collectIds(resolved)
    console.log('[useTastes:doCross]', { allIds })
    try { setCrossRes((await qlooCrossDomain(allIds)).results || {}) } catch (e) { setError(String(e)); console.warn('[useTastes:doCross:error]', e) }
    setLoading(false)
  }, [seeds, resolveSeeds, collectIds, setLoading, setError])

  // Click-to-act ~ persona-bound reuse. doCrossFrom / doRecommendFrom run the
  // SAME flows as doCross / doRecommend but against an explicit anchor list
  // (e.g. the active persona's taste anchors), so the Taste Bridge and the
  // Tastes tab can re-center on whoever is selected — not only Maria.
  const doCrossFrom = useCallback(async (anchorList: QlooEntity[]) => {
    if (!anchorList.length) return
    setLoading(true); setError('')
    const resolved = await resolveSeeds(anchorList)
    const allIds = collectIds(resolved)
    console.log('[useTastes:doCrossFrom]', { allIds })
    try { setCrossRes((await qlooCrossDomain(allIds)).results || {}) } catch (e) { setError(String(e)); console.warn('[useTastes:doCrossFrom:error]', e) }
    setLoading(false)
  }, [resolveSeeds, collectIds, setLoading, setError])

  // Click a profile anchor → recommend for THAT anchor (+ everything already in
  // memory from past searches). Also records the anchor into the profile list.
  const doRecommendFrom = useCallback(async (anchor: QlooEntity) => {
    // Dedupe case-insensitively by NAME as well as id — two different seed-* ids
    // for the same name would otherwise render as duplicate list keys in the
    // Tastes/Discover seed chips (React 19 crashes on duplicates).
    setSeeds(prev => (prev.some(x => (x.id === anchor.id) || (x.name.toLowerCase() === anchor.name.toLowerCase()))
      ? prev
      : [...prev, anchor]))
    setLoading(true); setError('')
    setRecommendTried(true)
    console.log('[useTastes:doRecommendFrom]', { anchor: anchor.name, domain })
    const resolved = await resolveSeeds([anchor])
    const allIds = collectIds(resolved)
    try {
      const r = await qlooRecommend(allIds, domain || undefined, 12)
      setRecs(r.recommendations || [])
    } catch (e) {
      setError(String(e)); console.warn('[useTastes:doRecommendFrom:error]', e)
    }
    setLoading(false)
  }, [setSeeds, resolveSeeds, collectIds, domain, setLoading, setError])

  return {
    domain, setDomain,
    query, setQuery,
    results, setResults,
    seeds, setSeeds,
    recs, setRecs,
    crossRes, setCrossRes,
    recommendTried, setRecommendTried,
    doSearch, doRecommend, doCross, doCrossFrom, doRecommendFrom,
  }
}
