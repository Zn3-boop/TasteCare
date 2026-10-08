import { useState } from 'react'
import { useQloo, type QlooEntity } from '../hooks/useQloo'

const DOMAINS = [
  { key: '', label: 'All' },
  { key: 'music', label: '🎵 Music' },
  { key: 'film', label: '🎬 Film' },
  { key: 'dining', label: '🍽️ Dining' },
  { key: 'fashion', label: '👗 Fashion' },
  { key: 'travel', label: '✈️ Travel' },
  { key: 'book', label: '📚 Books' },
]

const DOMAIN_COLORS: Record<string, string> = {
  music: '#1DB954', film: '#E50914', dining: '#FF6B35',
  fashion: '#C77DFF', travel: '#00B4D8', podcast: '#FFB703', book: '#8B5CF6',
}

export default function CulturePanel() {
  const { status, loading, error, search, recommend, crossDomain, refreshStatus } = useQloo()
  const [activeTab, setActiveTab] = useState<'search' | 'recommend' | 'discover'>('search')
  const [query, setQuery] = useState('')
  const [domain, setDomain] = useState('')
  const [results, setResults] = useState<QlooEntity[]>([])
  const [seeds, setSeeds] = useState<QlooEntity[]>([])
  const [recs, setRecs] = useState<QlooEntity[]>([])
  const [crossRes, setCrossRes] = useState<Record<string, QlooEntity[]>>({})

  const doSearch = async () => {
    const r = await search(query, domain || undefined, 15)
    setResults(r)
  }

  const doRecommend = async () => {
    if (!seeds.length) return
    const r = await recommend(seeds.map(s => s.id), domain || undefined, 12)
    setRecs(r.recommendations || [])
  }

  const doCross = async () => {
    if (!seeds.length) return
    const r = await crossDomain(seeds.map(s => s.id))
    setCrossRes(r.results || {})
  }

  const addSeed = (entity: QlooEntity) => {
    if (!seeds.find(s => s.id === entity.id)) {
      setSeeds(prev => [...prev, entity])
    }
  }

  return (
    <div style={{ padding: 16, height: '100%', overflow: 'auto', background: '#0A0A0A', color: '#E5E7EB' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700 }}>🎯 Cultural Intelligence</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: status?.enabled ? '#065F46' : '#374151', color: status?.enabled ? '#6EE7B7' : '#9CA3AF' }}>
            {status?.enabled ? 'Qloo ✓' : 'Qloo ✗'}
          </span>
          <button onClick={refreshStatus} style={{ background: 'none', border: 'none', color: '#9CA3AF', cursor: 'pointer', fontSize: 12 }}>↻</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {(['search', 'recommend', 'discover'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '5px 12px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12,
              fontWeight: activeTab === tab ? 600 : 400,
              background: activeTab === tab ? '#3B82F6' : '#1F2937',
              color: activeTab === tab ? '#fff' : '#9CA3AF',
            }}
          >
            {tab === 'search' ? '🔍 Search' : tab === 'recommend' ? '💡 Recommend' : '🌐 Discover'}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 12, flexWrap: 'wrap' }}>
        {DOMAINS.map(d => (
          <button key={d.key} onClick={() => setDomain(d.key)} style={{
            padding: '2px 8px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: 11,
            background: domain === d.key ? '#3B82F6' : '#1F2937', color: domain === d.key ? '#fff' : '#9CA3AF',
          }}>
            {d.label}
          </button>
        ))}
      </div>

      {error && <div style={{ color: '#F87171', fontSize: 11, marginBottom: 8 }}>{error}</div>}

      {activeTab === 'search' && (
        <div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
            <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && doSearch()} placeholder="Search artists, movies, restaurants..." style={{ flex: 1, padding: '8px 10px', borderRadius: 6, border: '1px solid #374151', background: '#111827', color: '#E5E7EB', fontSize: 13, outline: 'none' }} />
            <button onClick={doSearch} disabled={loading} style={{ padding: '8px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600, background: '#3B82F6', color: '#fff' }}>{loading ? '...' : 'Search'}</button>
          </div>
          {results.map((e, i) => (
            <div key={e.id} onClick={() => addSeed(e)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 6, background: '#111827', marginBottom: 4, cursor: 'pointer' }}>
              <span style={{ fontSize: 11, color: '#6B7280' }}>#{i + 1}</span>
              <span style={{ fontSize: 13, flex: 1 }}>{e.name}</span>
              {e.domain && <span style={{ fontSize: 10, color: DOMAIN_COLORS[e.domain] || '#6B7280' }}>{e.domain}</span>}
              {(e.score ?? e.popularity) !== undefined && <span style={{ fontSize: 11, color: '#3B82F6' }}>{Math.round((e.score ?? e.popularity!) * 100)}%</span>}
            </div>
          ))}
        </div>
      )}

      {activeTab === 'recommend' && (
        <div>
          {seeds.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4 }}>Seeds:</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {seeds.map(s => (
                  <span key={s.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 6px', borderRadius: 4, background: '#3B82F622', fontSize: 11, color: '#93C5FD' }}>
                    {s.name} <button onClick={() => setSeeds(p => p.filter(x => x.id !== s.id))} style={{ background: 'none', border: 'none', color: '#9CA3AF', cursor: 'pointer', fontSize: 11 }}>×</button>
                  </span>
                ))}
              </div>
            </div>
          )}
          <button onClick={doRecommend} disabled={loading || !seeds.length} style={{ padding: '8px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600, background: '#8B5CF6', color: '#fff', marginBottom: 12, width: '100%' }}>
            {loading ? '...' : 'Get Taste-Based Recommendations'}
          </button>
          {recs.map((e, i) => (
            <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 6, background: '#111827', marginBottom: 4 }}>
              <span style={{ fontSize: 11, color: '#6B7280' }}>#{i + 1}</span>
              <span style={{ fontSize: 13, flex: 1 }}>{e.name}</span>
              {e.domain && <span style={{ fontSize: 10, color: DOMAIN_COLORS[e.domain] || '#6B7280' }}>{e.domain}</span>}
              {(e.score ?? e.popularity) !== undefined && <span style={{ fontSize: 11, color: '#8B5CF6' }}>{Math.round((e.score ?? e.popularity!) * 100)}%</span>}
            </div>
          ))}
        </div>
      )}

      {activeTab === 'discover' && (
        <div>
          <button onClick={doCross} disabled={loading || !seeds.length} style={{ padding: '8px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600, background: '#059669', color: '#fff', marginBottom: 12, width: '100%' }}>
            {loading ? '...' : 'Discover Cross-Domain Connections'}
          </button>
          {Object.entries(crossRes).map(([d, ents]) => (
            <div key={d} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, textTransform: 'capitalize', color: DOMAIN_COLORS[d] || '#9CA3AF' }}>{d}</div>
              {ents.map((e, i) => (
                <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', borderRadius: 4, background: '#111827', marginBottom: 2 }}>
                  <span style={{ fontSize: 11, color: '#6B7280' }}>#{i + 1}</span>
                  <span style={{ fontSize: 12, flex: 1 }}>{e.name}</span>
                  {(e.score ?? e.popularity) !== undefined && <span style={{ fontSize: 10, color: '#059669' }}>{Math.round((e.score ?? e.popularity!) * 100)}%</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}