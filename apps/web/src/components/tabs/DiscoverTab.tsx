import { useEffect, useMemo, useRef, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { QlooEntity } from '../../api'
import { DOMAINS, DOMAIN_COLORS, PREVIEW_BRIDGE, BRIDGE_DOMAIN_ORDER, EMPTY_STATE_EXAMPLES, type DomainStatus } from '../../constants'
import { EntityCard } from '../ui'
import { sx } from '../sx'
import { uniqueBy } from '../../utils/list'
import { TasteBridge, type BridgeZone } from '../TasteBridge'
import { QlooStatusStrip } from '../QlooStatusStrip'

type Props = {
  seeds: QlooEntity[]
  setSeeds: Dispatch<SetStateAction<QlooEntity[]>>
  crossRes: Record<string, QlooEntity[]>
  doCross: () => void
  loading: boolean
  qlooEnabled: boolean
  animateText?: boolean
  /** reveal-on-arrival — nodes/edges animate in whenever the user runs a search. */
  reveal?: boolean
  /** Current persona name, so the Journey strip follows whoever is selected. */
  personaName?: string
  /** Current persona's own taste anchors — drawn as the innermost 'personal'
   *  ring of the bridge so a created person's habits are visible (custom only). */
  personaHabits?: string[]
}

export function DiscoverTab(props: Props) {
  const { seeds, setSeeds, crossRes, doCross, loading, qlooEnabled, animateText = false, reveal = false, personaName = 'Maria', personaHabits = [] } = props

  const [domainStatuses, setDomainStatuses] = useState<Record<string, DomainStatus>>({})
  // Raw per-domain results panel: default COLLAPSED; auto-expands once a fetch
  // actually lands results (feedback: raw lists should be one click away, not
  // permanently open — but must reveal themselves right after a successful run).
  const [rawOpen, setRawOpen] = useState(false)
  const rawFetchPendingRef = useRef(false)

  // Live data only when Qloo is connected AND cross-domain results are present.
  // Otherwise fall back to the clearly-labelled demo preview pool.
  const hasLive = qlooEnabled && Object.keys(crossRes).some(k => (crossRes[k] || []).length > 0)

  // ---- Persona Journey: one compact strip under the constellation -------------
  // The steps mirror EXACTLY what the Taste Bridge draws (BRIDGE_DOMAIN_ORDER),
  // so the strip and the graph can never drift apart. Content is dynamic: a live
  // Qloo cross-domain result when a key is set (step.isLive=true), otherwise the
  // clearly-labelled PREVIEW_BRIDGE pool. No Maria-only constants anymore — the
  // strip follows whichever persona is selected.
  const runJourney = () => {
    // Collapse the raw panel before a new run; it re-opens when results land.
    rawFetchPendingRef.current = true
    setRawOpen(false)
    doCross()
  }

  // Auto-run Maria's journey when the bridge tab FIRST opens with Qloo connected —
  // no click needed (feedback #10: cross-domain front and center) and surfaces a
  // LIVE constellation via the default Frank Sinatra anchor. Ref-guarded so a
  // mid-session toggle of qlooEnabled never triggers a duplicate fetch.
  const journeyAutoRanRef = useRef(false)
  const wasEnabledRef = useRef(false)
  useEffect(() => {
    if (qlooEnabled && !wasEnabledRef.current && !journeyAutoRanRef.current) {
      journeyAutoRanRef.current = true
      if (seeds.length) {
        doCross()
      }
    }
    wasEnabledRef.current = qlooEnabled
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qlooEnabled])

  // Auto-expand the raw per-domain panel only AFTER a live fetch actually
  // returns results — never on stale/preview data, and never while collapsed by
  // the user before their click finished. The ref is set by runJourney and the
  // Fetch button, then cleared once crossRes has fresh non-empty domains.
  useEffect(() => {
    if (rawFetchPendingRef.current) {
      const hasFresh = Object.keys(crossRes).some(k => (crossRes[k] || []).length > 0)
      if (hasFresh) {
        rawFetchPendingRef.current = false
        setRawOpen(true)
      }
    }
  }, [crossRes])

  const journeyHasLive = hasLive && Object.keys(crossRes).length > 0
  // Persona-literal recap of the bridge: first result in each of the bridge's
  // domains (music → dining → film → travel → fashion → podcast → book), with
  // persona-appropriate phrasing. Single source of truth = BRIDGE_DOMAIN_ORDER,
  // so this can never disagree with the constellation above it.
  const JOURNEY_STEP_META: Record<string, { icon: string; label: string }> = {
    music: { icon: '🎵', label: 'loves' },
    dining: { icon: '🍽️', label: 'dines at' },
    film: { icon: '🎬', label: 'watches' },
    travel: { icon: '✈️', label: 'travels to' },
    fashion: { icon: '👗', label: 'wears' },
    podcast: { icon: '🎙️', label: 'listens to' },
    book: { icon: '📚', label: 'reads' },
  }
  const journeySteps = BRIDGE_DOMAIN_ORDER
    .map(domain => {
      const liveName = journeyHasLive ? (crossRes[domain]?.[0]?.name ?? '') : ''
      const previewName = PREVIEW_BRIDGE[domain]?.[0]?.name ?? ''
      const name = liveName || previewName
      if (!name) return null
      const meta = JOURNEY_STEP_META[domain] || { icon: '🔗', label: 'relates to' }
      return { domain, icon: meta.icon, label: meta.label, name, isLive: Boolean(liveName) }
    })
    .filter((s): s is NonNullable<typeof s> => s !== null)

  const zones = useMemo<BridgeZone[]>(() => {
    // The persona's own taste anchors ride the innermost 'personal' ring (custom
    // personas) so habits entered in the PersonaPicker are visible on the bridge
    // before any live data arrives. Deduped + stable keys (React 19 key limit).
    const personalZone: BridgeZone[] = personaHabits.length
      ? [{
          domain: 'personal',
          nodes: uniqueBy(personaHabits, h => h.trim().toLowerCase()).map(name => ({
            entity_id: `habit-${name.trim().toLowerCase()}`,
            name: name.trim(),
            why: 'Entered when creating this persona',
            popularity: 0.5,
          })),
        }]
      : []
    if (hasLive) {
      return [
        ...personalZone,
        ...BRIDGE_DOMAIN_ORDER
          .filter(d => (crossRes[d] || []).length > 0)
          .map(d => ({
            domain: d,
            // Live Qloo cross-domain payloads can contain the SAME entity_id twice
            // in one domain (see TasteBridge) — dedupe so the bridge rings never
            // receive duplicate SVG keys.
            nodes: uniqueBy(crossRes[d] || [], e => e.id || e.name).map(e => ({
              entity_id: e.id || `${d}-${e.name}`,
              name: e.name,
              popularity: e.score ?? undefined,
            })),
          })),
      ]
    }
    return [
      ...personalZone,
      ...BRIDGE_DOMAIN_ORDER
        .filter(d => (PREVIEW_BRIDGE[d] || []).length > 0)
        .map(d => ({
          domain: d,
          nodes: PREVIEW_BRIDGE[d].map(n => ({
            entity_id: `preview-${n.name}`,
            name: n.name,
            why: n.why,
            popularity: n.popularity,
          })),
        })),
    ]
  }, [hasLive, crossRes, personaHabits])

  const centerLabel = seeds.length ? seeds.map(s => s.name).join(' · ') : personaName
  const dataSource = hasLive ? 'live' : 'preview'
  const crossEntityCount = Object.values(crossRes).reduce((sum, arr) => sum + (arr?.length ?? 0), 0)

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #05966944', background: 'linear-gradient(135deg, #05966910, #111827)' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#059669', marginBottom: 8 }}>Cross-Domain Discovery</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          <strong style={{ color: '#E5E7EB' }}>The thing only Qloo can do:</strong> bridge your taste across domains. Love a filmmaker → here's the dining &amp; fashion you'd probably love too. No LLM can do this without a taste graph.
        </p>
      </div>

      {/* Persona Journey — one strip, mirrors the bridge exactly */}
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #C77DFF44', background: 'linear-gradient(135deg, #C77DFF12, #111827)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' as const, marginBottom: 12 }}>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#C77DFF', marginBottom: 4 }}>{personaName}'s Taste Journey</h3>
            <p style={{ fontSize: 12, color: '#9CA3AF', lineHeight: 1.5, maxWidth: 560 }}>
              One taste anchor radiating across every cultural domain — the personal story behind the constellation. Each step is the bridge&apos;s own live-or-preview result.
            </p>
          </div>
          <button
            onClick={() => runJourney()}
            disabled={loading}
            style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #C77DFF, #8B5CF6)', boxShadow: '0 4px 14px #C77DFF44', opacity: loading ? 0.6 : 1, whiteSpace: 'nowrap' as const }}
          >
            {loading ? '⏳ Building journey…' : journeyHasLive ? '▶ Replay Journey (live)' : `▶ Play ${personaName}'s Journey`}
          </button>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'stretch', flexWrap: 'wrap' as const }}>
          {journeySteps.map((step, i) => (
            <div key={step.domain} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {i > 0 && <div style={{ color: '#4B5563', fontSize: 18, fontWeight: 700 }}>→</div>}
              <div style={{ flex: '1 1 130px', minWidth: 120, padding: '10px 12px', borderRadius: 10, background: '#0B1220', border: `1px solid ${DOMAIN_COLORS[step.domain] || '#374151'}44` }}>
                <div style={{ fontSize: 18, marginBottom: 4 }}>{step.icon}</div>
                <div style={{ fontSize: 10, color: '#6B7280', textTransform: 'uppercase' as const, letterSpacing: 0.4 }}>{step.domain}</div>
                <div style={{ fontSize: 12, color: '#D1D5DB', marginTop: 2, fontWeight: 600 }}>{personaName} {step.label}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: step.isLive ? '#6EE7B7' : '#FCD34D', marginTop: 3 }}>{step.name}</div>
                {!step.isLive && <div style={{ fontSize: 9, color: '#6B7280', marginTop: 3 }}>{qlooEnabled ? 'connecting…' : 'preview'}</div>}
              </div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 10.5, color: '#6B7280', marginTop: 10, fontStyle: 'italic' }}>
          {journeyHasLive
            ? 'Each step is a real cross-domain result from Qloo\'s taste graph (live).'
            : qlooEnabled
              ? 'Qloo is connected — run the journey to replace this preview with live cross-domain results.'
              : 'Demo preview — set QLOO_API_KEY to see live cross-domain recommendations.'}
        </div>
      </div>

      <QlooStatusStrip
        loading={loading}
        matched={loading ? null : (crossEntityCount > 0 ? crossEntityCount : null)}
        queryLabel="Qloo Taste Graph across domains"
        detail={hasLive ? 'live cross-domain bridging' : 'demo preview bridging'}
      />
      <TasteBridge centerLabel={centerLabel} zones={zones} dataSource={dataSource} loading={loading} domainStatuses={domainStatuses} animateText={animateText} reveal={reveal} qlooEnabled={qlooEnabled} />
      <div style={{ marginTop: 20, ...sx.card }}>
        {seeds.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <label style={sx.label}>Taste anchors (add from the Tastes tab)</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const }}>
              {uniqueBy(seeds, s => s.id || s.name).map(s => (
                <span key={s.id || `${s.name}-${seeds.indexOf(s)}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: '#1F2937', padding: '5px 10px', borderRadius: 8, fontSize: 12, color: '#E5E7EB', border: '1px solid #374151' }}>
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
              {qlooEnabled ? (
                <>Qloo is <strong style={{ color: '#34D399' }}>connected</strong> — add taste anchors, then fetch live cross-domain bridges below.</>
              ) : (
                <>The constellation above is <strong style={{ color: '#FCD34D' }}>demo preview</strong>. Search in the 💡 Tastes tab, add anchors, then fetch live cross-domain bridges.</>
              )}
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
        <button onClick={() => { rawFetchPendingRef.current = true; setRawOpen(false); doCross(); setDomainStatuses(() => { const next: Record<string, DomainStatus> = {}; Object.keys(crossRes).forEach(k => { next[k] = 'loading' }); return next }) }} disabled={loading || !seeds.length} style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #059669, #047857)', boxShadow: '0 4px 14px #05966944', marginBottom: 6, opacity: loading || !seeds.length ? 0.5 : 1 }}>
          {loading ? '…' : '🔗 Fetch Live Cross-Domain Bridges'}
        </button>
        <p style={{ fontSize: 11, color: '#6B7280', marginTop: 0, marginBottom: 16, lineHeight: 1.5 }}>
          Queries Qloo&apos;s cross-domain insights once per anchor and re-centers the constellation above — every domain in the bridge is resolved from your seeds, not from the demo pool. <strong style={{ color: '#9CA3AF' }}>View raw results by domain</strong> below expands the full per-domain lists.
        </p>

        <details open={rawOpen} onToggle={e => setRawOpen(e.currentTarget.open)}>
          <summary style={{ fontSize: 12, color: '#9CA3AF', cursor: 'pointer', marginBottom: 8 }}>View raw results by domain</summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {Object.entries(crossRes).map(([d, ents]) => (
              <div key={d}>
                <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 8, textTransform: 'capitalize' as const, color: DOMAIN_COLORS[d] || '#E5E7EB' }}>
                  {DOMAINS.find(x => x.key === d)?.label || d}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {uniqueBy(ents, e => e.id || e.name).map((e, i) => <EntityCard key={e.id || `${e.name}-${i}`} entity={e} rank={i + 1} />)}
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