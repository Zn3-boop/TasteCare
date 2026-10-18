import { useEffect, useMemo, useRef, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { QlooEntity } from '../../api'
import { DOMAINS, DOMAIN_COLORS, PREVIEW_BRIDGE, BRIDGE_DOMAIN_ORDER, EMPTY_STATE_EXAMPLES, MARIA_JOURNEY, type DomainStatus } from '../../constants'
import { getEntityDetails, type EntityDetails } from '../../api'
import { EntityCard } from '../ui'
import { sx } from '../sx'
import { TasteBridge, type BridgeZone } from '../TasteBridge'

type Props = {
  seeds: QlooEntity[]
  setSeeds: Dispatch<SetStateAction<QlooEntity[]>>
  crossRes: Record<string, QlooEntity[]>
  doCross: () => void
  loading: boolean
  qlooEnabled: boolean
}

export function DiscoverTab(props: Props) {
  const { seeds, setSeeds, crossRes, doCross, loading, qlooEnabled } = props

  const [domainStatuses, setDomainStatuses] = useState<Record<string, DomainStatus>>({})
  const [selectedNode, setSelectedNode] = useState<{ entity_id: string; name: string; domain: string; why?: string } | null>(null)
  const [entityDetails, setEntityDetails] = useState<EntityDetails | null>(null)
  const [detailsLoading, setDetailsLoading] = useState(false)

  // Live data only when Qloo is connected AND cross-domain results are present.
  // Otherwise fall back to the clearly-labelled demo preview pool.
  const hasLive = qlooEnabled && Object.keys(crossRes).some(k => (crossRes[k] || []).length > 0)

  // ---- Maria's Journey: semi-dynamic cross-domain storyline -------------------
  // Fixed persona + fixed path skeleton (🎵→🍽️→🎬→✈️→👗) + fixed seeds; the CONTENT
  // of each step is dynamic (live crossRes with a key, PREVIEW_BRIDGE without).
  // Two-phase trigger: set the Sinatra seed, then fire doCross() after the seed
  // lands in state (doCross closes over the current seeds).
  const [playJourney, setPlayJourney] = useState(false)
  const doCrossRef = useRef(doCross)
  doCrossRef.current = doCross
  useEffect(() => {
    if (playJourney && seeds.some(s => s.name === 'Frank Sinatra')) {
      doCrossRef.current()
      setPlayJourney(false)
    }
  }, [playJourney, seeds])

  const journeyHasLive = hasLive && Object.keys(crossRes).length > 0
  const journeySteps = MARIA_JOURNEY.map(step => {
    const liveName = journeyHasLive ? (crossRes[step.domain]?.[0]?.name ?? '') : ''
    const previewName = PREVIEW_BRIDGE[step.domain]?.[0]?.name ?? ''
    return {
      ...step,
      name: liveName || previewName,
      isLive: Boolean(liveName),
    }
  })

  const zones = useMemo<BridgeZone[]>(() => {
    if (hasLive) {
      return BRIDGE_DOMAIN_ORDER
        .filter(d => (crossRes[d] || []).length > 0)
        .map(d => ({
          domain: d,
          nodes: crossRes[d].map(e => ({
            entity_id: e.id || `${d}-${e.name}`,
            name: e.name,
            popularity: e.score ?? undefined,
          })),
        }))
    }
    return BRIDGE_DOMAIN_ORDER
      .filter(d => (PREVIEW_BRIDGE[d] || []).length > 0)
      .map(d => ({
        domain: d,
        nodes: PREVIEW_BRIDGE[d].map(n => ({
          entity_id: `preview-${n.name}`,
          name: n.name,
          why: n.why,
          popularity: n.popularity,
        })),
      }))
  }, [hasLive, crossRes])

  const centerLabel = seeds.length ? seeds.map(s => s.name).join(' · ') : 'Frank Sinatra'
  const dataSource = hasLive ? 'live' : 'preview'

  const handleNodeClick = async (node: { entity_id: string; name: string; domain: string; why?: string }) => {
    setSelectedNode(node)
    if (node.entity_id.startsWith('preview-')) {
      setEntityDetails(null)
      return
    }
    setDetailsLoading(true)
    try { const d = await getEntityDetails(node.entity_id); setEntityDetails(d) } catch { /* ignore */ }
    setDetailsLoading(false)
  }

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #05966944', background: 'linear-gradient(135deg, #05966910, #111827)' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#059669', marginBottom: 8 }}>Cross-Domain Discovery</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          <strong style={{ color: '#E5E7EB' }}>The thing only Qloo can do:</strong> bridge your taste across domains. Love a filmmaker → here's the dining &amp; fashion you'd probably love too. No LLM can do this without a taste graph.
        </p>
      </div>

      {/* Maria's Taste Journey — fixed persona + fixed path skeleton, dynamic content */}
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #C77DFF44', background: 'linear-gradient(135deg, #C77DFF12, #111827)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' as const, marginBottom: 12 }}>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#C77DFF', marginBottom: 4 }}>Maria's Taste Journey</h3>
            <p style={{ fontSize: 12, color: '#9CA3AF', lineHeight: 1.5, maxWidth: 560 }}>
              One taste anchor radiating across five cultural domains — the personal story behind the constellation. Path is fixed; each step's content is <strong style={{ color: '#E5E7EB' }}>{journeyHasLive ? 'live Qloo data' : 'demo preview'}</strong>.
            </p>
          </div>
          <button
            onClick={() => {
              setSeeds(prev => prev.some(s => s.name === 'Frank Sinatra') ? prev : [...prev, { id: 'seed-frank-sinatra', name: 'Frank Sinatra', type: 'artist', domain: 'music' }])
              setPlayJourney(true)
            }}
            disabled={loading}
            style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #C77DFF, #8B5CF6)', boxShadow: '0 4px 14px #C77DFF44', opacity: loading ? 0.6 : 1, whiteSpace: 'nowrap' as const }}
          >
            {loading ? '⏳ Building journey…' : journeyHasLive ? '▶ Replay Journey (live)' : '▶ Play Maria\'s Journey'}
          </button>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'stretch', flexWrap: 'wrap' as const }}>
          {journeySteps.map((step, i) => (
            <div key={step.domain} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {i > 0 && <div style={{ color: '#4B5563', fontSize: 18, fontWeight: 700 }}>→</div>}
              <div style={{ flex: '1 1 130px', minWidth: 120, padding: '10px 12px', borderRadius: 10, background: '#0B1220', border: `1px solid ${DOMAIN_COLORS[step.domain] || '#374151'}44` }}>
                <div style={{ fontSize: 18, marginBottom: 4 }}>{step.icon}</div>
                <div style={{ fontSize: 10, color: '#6B7280', textTransform: 'uppercase' as const, letterSpacing: 0.4 }}>{step.domain}</div>
                <div style={{ fontSize: 12, color: '#D1D5DB', marginTop: 2 }}>{step.label}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: step.isLive ? '#6EE7B7' : '#FCD34D', marginTop: 3 }}>{step.name || step.seed}</div>
                {!step.isLive && <div style={{ fontSize: 9, color: '#6B7280', marginTop: 3 }}>preview</div>}
              </div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 10.5, color: '#6B7280', marginTop: 10, fontStyle: 'italic' }}>
          {journeyHasLive
            ? 'Each step is a real cross-domain result from Qloo\'s taste graph (live).'
            : 'Demo preview — set QLOO_API_KEY to see live cross-domain recommendations.'}
        </div>
      </div>

      <TasteBridge centerLabel={centerLabel} zones={zones} dataSource={dataSource} loading={loading} domainStatuses={domainStatuses} onNodeClick={handleNodeClick} />

      <div style={{ marginTop: 20, ...sx.card }}>
        {seeds.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <label style={sx.label}>Taste anchors (add from the Tastes tab)</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const }}>
              {seeds.map(s => (
                <span key={s.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: '#1F2937', padding: '5px 10px', borderRadius: 8, fontSize: 12, color: '#E5E7EB', border: '1px solid #374151' }}>
                  {s.name}
                  <button onClick={() => setSeeds(p => p.filter(x => x.id !== s.id))} style={{ background: 'none', border: 'none', color: '#9CA3AF', cursor: 'pointer', fontSize: 14, lineHeight: 1 }}>×</button>
                </span>
              ))}
            </div>
          </div>
        )}
        {seeds.length === 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ textAlign: 'center', padding: 16, color: '#6B7280', fontSize: 13, marginBottom: 12 }}>
              The constellation above is <strong style={{ color: '#FCD34D' }}>demo preview</strong>. Search in the 💡 Tastes tab, add anchors, then fetch live cross-domain bridges.
            </div>
            <div style={{ padding: '12px 16px', borderRadius: 10, background: '#111827', border: '1px solid #1F2937' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#9CA3AF', marginBottom: 8 }}>Try these seeds to get started:</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {EMPTY_STATE_EXAMPLES.map(ex => (
                  <button key={ex} onClick={() => { setSeeds(prev => prev.some(s => s.name.toLowerCase() === ex.toLowerCase()) ? prev : [...prev, { id: `seed-${ex}`, name: ex, type: 'taste', domain: '' }]) }} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 8, background: '#1F2937', color: '#D1D5DB', border: '1px solid #374151', cursor: 'pointer' }}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
        <button onClick={() => { doCross(); setDomainStatuses(prev => { const next: Record<string, DomainStatus> = {}; Object.keys(crossRes).forEach(k => { next[k] = 'loading' }); return next }) }} disabled={loading || !seeds.length} style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #059669, #047857)', boxShadow: '0 4px 14px #05966944', marginBottom: 16, opacity: loading || !seeds.length ? 0.5 : 1 }}>
          {loading ? '…' : '🔗 Fetch Live Cross-Domain Bridges'}
        </button>

        <details>
          <summary style={{ fontSize: 12, color: '#9CA3AF', cursor: 'pointer', marginBottom: 8 }}>View raw results by domain</summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {Object.entries(crossRes).map(([d, ents]) => (
              <div key={d}>
                <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 8, textTransform: 'capitalize' as const, color: DOMAIN_COLORS[d] || '#E5E7EB' }}>
                  {DOMAINS.find(x => x.key === d)?.label || d}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {ents.map((e, i) => <EntityCard key={e.id} entity={e} rank={i + 1} />)}
                  {ents.length === 0 && <div style={{ fontSize: 12, color: '#6B7280', fontStyle: 'italic' }}>No results in this domain</div>}
                </div>
              </div>
            ))}
            {Object.keys(crossRes).length === 0 && (
              <div style={{ fontSize: 12, color: '#6B7280', fontStyle: 'italic' }}>No live results yet.</div>
            )}
          </div>
        </details>
      </div>
    </section>
  )
}