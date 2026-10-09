import type { Dispatch, SetStateAction } from 'react'
import type { QlooEntity } from '../../api'
import { DOMAINS } from '../../constants'
import { EntityCard } from '../ui'
import { sx } from '../sx'

type Props = {
  domain: string
  setDomain: (v: string) => void
  query: string
  setQuery: (v: string) => void
  results: QlooEntity[]
  seeds: QlooEntity[]
  setSeeds: Dispatch<SetStateAction<QlooEntity[]>>
  recs: QlooEntity[]
  doSearch: () => void
  doRecommend: () => void
  loading: boolean
}

export function TastesTab(props: Props) {
  const { domain, setDomain, query, setQuery, results, seeds, setSeeds, recs, doSearch, doRecommend, loading } = props

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#E5E7EB', marginBottom: 8 }}>Taste-Based Recommendations</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          Start from anyone you love → get recommendations scored by <strong style={{ color: '#E5E7EB' }}>Qloo cultural fit</strong>. This is what a generic LLM cannot do: it doesn't know that a Nolan fan would love specific restaurants.
        </p>
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
        {DOMAINS.map(d => (
          <button key={d.key} onClick={() => setDomain(d.key)} style={{ padding: '5px 12px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: domain === d.key ? 600 : 400, background: domain === d.key ? '#3B82F6' : '#1F2937', color: domain === d.key ? '#fff' : '#9CA3AF' }}>{d.label}</button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && doSearch()} placeholder="Search artists, movies, restaurants…" style={{ ...sx.input, flex: 1 }} />
        <button onClick={doSearch} disabled={loading} style={{ ...sx.btnSecondary, background: '#3B82F6', color: '#fff' }}>{loading ? '…' : 'Search'}</button>
      </div>
      {seeds.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <label style={sx.label}>Taste anchors (click search results to add)</label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {seeds.map(s => (
              <span key={s.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: '#1F2937', padding: '5px 10px', borderRadius: 8, fontSize: 12, color: '#E5E7EB', border: '1px solid #374151' }}>
                {s.name}
                <button onClick={() => setSeeds(p => p.filter(x => x.id !== s.id))} style={{ background: 'none', border: 'none', color: '#9CA3AF', cursor: 'pointer', fontSize: 14, lineHeight: 1 }}>×</button>
              </span>
            ))}
          </div>
        </div>
      )}
      <button onClick={doRecommend} disabled={loading || !seeds.length} style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #8B5CF6, #7C3AED)', boxShadow: '0 4px 14px #8B5CF644', marginBottom: 16, opacity: loading || !seeds.length ? 0.5 : 1 }}>
        {loading ? '…' : '💡 Get Taste-Based Recommendations'}
      </button>
      {results.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <label style={sx.label}>Search results (click to add as taste anchor)</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {results.map((e, i) => <EntityCard key={e.id} entity={e} rank={i + 1} onClick={() => { if (!seeds.find(x => x.id === e.id)) setSeeds(p => [...p, e]) }} />)}
          </div>
        </div>
      )}
      {recs.length > 0 && (
        <div>
          <label style={{ ...sx.label, color: '#8B5CF6', fontWeight: 600 }}>Recommended for your taste profile</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recs.map((e, i) => <EntityCard key={e.id} entity={e} rank={i + 1} />)}
          </div>
        </div>
      )}
    </section>
  )
}