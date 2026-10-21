import type { Dispatch, SetStateAction } from 'react'
import type { QlooEntity } from '../../api'
import { DOMAINS } from '../../constants'
import { EntityCard, SkeletonRow } from '../ui'
import { sx } from '../sx'
import { uniqueBy } from '../../utils/list'

type Props = {
  domain: string
  setDomain: (v: string) => void
  query: string
  setQuery: (v: string) => void
  results: QlooEntity[]
  seeds: QlooEntity[]
  setSeeds: Dispatch<SetStateAction<QlooEntity[]>>
  recs: QlooEntity[]
  /** Optional domain override re-runs the query under a new taste domain (pills). */
  doSearch: (domain?: string) => void
  doRecommend: (domain?: string) => void
  /** Click-to-recommend: run the recommend flow for ONE profile anchor. */
  doRecommendFrom: (seed: QlooEntity) => void
  personaName?: string
  loading: boolean
  /** Latest request error message (from useTastes) — rendered as a banner. */
  error?: string
  /** True once a recommend request completed; gates the friendly empty-state. */
  recommendTried?: boolean
}

export function TastesTab(props: Props) {
  const { domain, setDomain, query, setQuery, results, seeds, setSeeds, recs, doSearch, doRecommend, doRecommendFrom, personaName = 'Maria', loading, error = '', recommendTried = false } = props

  // Qloo search/recommend can return the same entity_id twice (cross-domain
  // payloads especially). React 19 crashes on duplicate keys — dedupe all lists
  // and key with a composite so reconciliation can never see a collision.
  const seedList = uniqueBy(seeds, s => s.id || s.name)
  const resultList = uniqueBy(results, e => e.id || e.name)
  const recList = uniqueBy(recs, e => e.id || e.name)

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#E5E7EB', marginBottom: 8 }}>{personaName}'s Taste Profile</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          This is the taste profile that drives the whole demo — <strong style={{ color: '#E5E7EB' }}>click any anchor to instantly recommend</strong> for it. A generic LLM can&apos;t do this: it doesn&apos;t know that a Nolan fan would love specific restaurants.
        </p>
        <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 8, background: '#8B5CF622', border: '1px solid #8B5CF655' }}>
          <span style={{ fontSize: 12, color: '#E5E7EB', lineHeight: 1.55 }}>
            <strong style={{ color: '#C77DFF' }}>Not the same as Senior Dining.</strong>{' '}
            <strong>Tastes → Dining</strong> here is pure Qloo culture affinity — what the taste graph pairs with your anchors, with no health constraints applied.{' '}
            <strong>Senior Dining</strong> takes the same cultural match and then filters every candidate against this person&apos;s health reality (low sodium, easy-to-chew, medication-aware).
          </span>
        </div>
        <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 8, background: '#05966914', border: '1px solid #05966944' }}>
          <span style={{ fontSize: 12, color: '#E5E7EB', lineHeight: 1.6 }}>
            <strong style={{ color: '#6EE7B7' }}>How to demo:</strong>{' '}
            <strong>Search</strong> discovers new cultural entities — ① type anything you like (a food, artist, film…), ② pick a domain (All / 🎵 Music / 🍽️ Dining…), ③ press Search, then click any result to add it as a taste anchor and instantly recommend for it.{' '}
            <strong>Recommend</strong> is different: it runs Qloo cross-domain suggestions from <em>all</em> your saved anchors combined (no new search needed).{' '}
            <span style={{ color: '#6EE7B7' }}>Search = find new things to add to the taste profile; Recommend = generate matches from what you already kept.</span>{' '}
            Clicking an anchor also re-centers the <strong>Taste Bridge</strong> on that search.
          </span>
        </div>
        <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, background: '#33333333', border: '1px solid #44444455' }}>
          <span style={{ fontSize: 11, color: '#9CA3AF', lineHeight: 1.5 }}>
            🔒 Your anchors are saved locally — they survive a page refresh and keep rendering on the Taste Bridge. They reset only when you switch to a different persona in the top picker (that restores that person&apos;s baseline taste profile).
          </span>
        </div>
      </div>
      {error && (
        <div role="alert" style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 10, border: '1px solid #7F1D1D', background: '#7F1D1D22', color: '#FCA5A5', fontSize: 13, lineHeight: 1.5 }}>
          <strong>⚠ Request failed:</strong> {error}
        </div>
      )}
      <div style={{ marginBottom: 6 }}>
        <label style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', letterSpacing: 0.5 }}>TASTE DOMAIN — click to instantly re-filter search results &amp; recommendations</label>
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
        {DOMAINS.map(d => (
          <button
            key={d.key}
            onClick={() => {
              setDomain(d.key)
              // Make the pills real: re-run BOTH active queries under the new domain
              // immediately (doSearch/doRecommend accept an explicit domain so the
              // async state update can't stale-read the previous filter).
              const q = query.trim()
              if (q) void doSearch(d.key)
              if (seeds.length) void doRecommend(d.key)
            }}
            style={{ padding: '5px 12px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: domain === d.key ? 600 : 400, background: domain === d.key ? '#3B82F6' : '#1F2937', color: domain === d.key ? '#fff' : '#9CA3AF', opacity: loading ? 0.7 : 1 }}
          >
            {d.label}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && doSearch()} placeholder="Search artists, movies, restaurants…" style={{ ...sx.input, flex: 1 }} />
        <button onClick={() => void doSearch()} disabled={loading} style={{ ...sx.btnSecondary, background: '#3B82F6', color: '#fff' }}>{loading ? '…' : 'Search'}</button>
      </div>
      {seedList.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <label style={sx.label}>Taste anchors — click one to recommend for it</label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {seedList.map(s => (
              <span key={s.id || s.name} style={{ display: 'inline-flex', alignItems: 'center', gap: 2, background: '#1F2937', padding: '3px 4px 3px 12px', borderRadius: 8, fontSize: 12, color: '#E5E7EB', border: '1px solid #8B5CF655' }}>
                <button onClick={() => doRecommendFrom(s)} title="Recommend for this anchor" style={{ background: 'none', border: 'none', color: '#E5E7EB', cursor: 'pointer', fontSize: 12, fontWeight: 700, padding: '2px 6px', borderRadius: 6 }}>{s.name}</button>
                <button onClick={() => setSeeds(p => p.filter(x => x.id !== s.id))} title="Remove from profile" style={{ background: 'none', border: 'none', color: '#9CA3AF', cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: '2px 6px' }}>×</button>
              </span>
            ))}
          </div>
        </div>
      )}
      <button onClick={() => void doRecommend()} disabled={loading || !seeds.length} style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #8B5CF6, #7C3AED)', boxShadow: '0 4px 14px #8B5CF644', marginBottom: 16, opacity: loading || !seeds.length ? 0.5 : 1 }}>
        {loading ? '…' : '💡 Recommend for all profile anchors'}
      </button>
      {loading && (
        <div style={{ marginBottom: 16 }}>
          <label style={sx.label}>Querying the Qloo taste graph…</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </div>
        </div>
      )}
      {!loading && resultList.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <label style={sx.label}>Search results (click to add to profile &amp; recommend)</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {resultList.map((e, i) => <EntityCard key={e.id || `${e.name}-${i}`} entity={e} rank={i + 1} onClick={() => doRecommendFrom(e)} />)}
          </div>
        </div>
      )}
      {!loading && recList.length > 0 && (
        <div>
          <label style={{ ...sx.label, color: '#8B5CF6', fontWeight: 600 }}>Recommended for the clicked anchor (Qloo cultural fit)</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recList.map((e, i) => <EntityCard key={e.id || `${e.name}-${i}`} entity={e} rank={i + 1} />)}
          </div>
        </div>
      )}
      {!loading && !error && recommendTried && recList.length === 0 && (
        <div style={{ marginTop: 4, padding: '14px 16px', borderRadius: 10, border: '1px dashed #374151', background: '#0b1020', textAlign: 'center' }}>
          <div style={{ fontSize: 24, marginBottom: 6 }}>🫥</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#E5E7EB', marginBottom: 4 }}>No strong Qloo matches this time</div>
          <div style={{ fontSize: 12, color: '#9CA3AF', lineHeight: 1.6 }}>
            The taste graph returned nothing for these anchors in the current domain. Try another domain pill above, add more anchors, or search + click a result to seed recommendations.
          </div>
        </div>
      )}
    </section>
  )
}