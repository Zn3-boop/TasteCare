import { useMemo } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { QlooEntity } from '../../api'
import { DOMAINS, DOMAIN_COLORS, PREVIEW_BRIDGE, BRIDGE_DOMAIN_ORDER } from '../../constants'
import { sx, EntityCard } from '../ui'
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

  // Live data only when Qloo is connected AND cross-domain results are present.
  // Otherwise fall back to the clearly-labelled demo preview pool.
  const hasLive = qlooEnabled && Object.keys(crossRes).some(k => (crossRes[k] || []).length > 0)

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

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #05966944', background: 'linear-gradient(135deg, #05966910, #111827)' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#059669', marginBottom: 8 }}>Cross-Domain Discovery</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          <strong style={{ color: '#E5E7EB' }}>The thing only Qloo can do:</strong> bridge your taste across domains. Love a filmmaker → here's the dining &amp; fashion you'd probably love too. No LLM can do this without a taste graph.
        </p>
      </div>

      <TasteBridge centerLabel={centerLabel} zones={zones} dataSource={dataSource} loading={loading} />

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
          <div style={{ textAlign: 'center', padding: 16, color: '#6B7280', fontSize: 13, marginBottom: 12 }}>
            The constellation above is <strong style={{ color: '#FCD34D' }}>demo preview</strong>. Search in the 💡 Tastes tab, add anchors, then fetch live cross-domain bridges.
          </div>
        )}
        <button onClick={doCross} disabled={loading || !seeds.length} style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #059669, #047857)', boxShadow: '0 4px 14px #05966944', marginBottom: 16, opacity: loading || !seeds.length ? 0.5 : 1 }}>
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