// TasteBridgeHero — the first-screen spotlight for the cross-domain constellation.
// Puts the "thing only Qloo can do" in front of the judge before any click:
// one anchor → music · dining · film · fashion · travel. Reuses the exact
// <TasteBridge> renderer (live crossRes when Qloo is connected, the clearly
// labelled PREVIEW_BRIDGE pool otherwise) so the story is honest in both modes.

import { useMemo } from 'react'
import type { QlooEntity } from '../api'
import { PREVIEW_BRIDGE, BRIDGE_DOMAIN_ORDER, DOMAINS, DOMAIN_COLORS } from '../constants'
import { TasteBridge, type BridgeZone } from './TasteBridge'
import { sx } from './sx'
import { uniqueBy } from '../utils/list'

type Props = {
  anchor: string
  crossRes: Record<string, QlooEntity[]>
  qlooEnabled: boolean
  onExplore: () => void
  personaName?: string
  /** The current persona's own taste anchors (from the PersonaPicker) — rendered
   *  as the innermost 'personal' ring so a created person's habits are visible
   *  on the bridge even before any live Qloo data arrives (feedback). Maria's
   *  preset keeps the original look, so App passes `[]` for her. */
  personaHabits?: string[]
  animateText?: boolean
  /** Reveal-on-arrival: progressive node/edge assembly when the graph data changes. */
  reveal?: boolean
}

export function TasteBridgeHero({ anchor, crossRes, qlooEnabled, onExplore, personaName = 'Maria', personaHabits = [], animateText = false, reveal = false }: Props) {
  const hasLive = qlooEnabled && Object.keys(crossRes).some(k => (crossRes[k] || []).length > 0)

  const zones = useMemo<BridgeZone[]>(() => {
    // The persona's own habits always ride the innermost ring (custom personas),
    // so "what I entered when creating this person" is never lost to live/preview
    // cross-domain results. Deduped — an anchor typed twice must not create two
    // nodes with the same SVG key (React 19 crashes on duplicate keys).
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

  const dataSource: 'live' | 'preview' = hasLive ? 'live' : 'preview'
  const centerLabel = (anchor || personaName).trim()
  const seen = zones.filter(z => z.nodes.length).map(z => z.domain)

  return (
    <div style={{
      ...sx.card, marginBottom: 20, padding: 18,
      border: `1px solid ${hasLive ? '#05966944' : '#C77DFF55'}`,
      background: 'linear-gradient(135deg, #C77DFF14, #0b1020)',
    }}>
      <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' as const }}>
        <div style={{ flex: '1 1 280px', minWidth: 250 }}>
          <div style={{ fontSize: 10, letterSpacing: 2.5, textTransform: 'uppercase' as const, color: '#C77DFF', fontWeight: 800, marginBottom: 8 }}>
            ◉ Cross-Domain Discovery
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.25, margin: '0 0 8px', color: '#E5E7EB' }}>
            One taste anchor.
            <br />
            <span style={{ background: 'linear-gradient(135deg, #C77DFF, #00B4D8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              A universe of cultures.
            </span>
          </h2>
          <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.65, margin: 0 }}>
            Music → dining → film → fashion → travel. <strong style={{ color: '#E5E7EB' }}>TasteBridge</strong> radiates one anchor across Qloo's{' '}
            <strong style={{ color: '#E5E7EB' }}>250M+ entity taste graph</strong> — the cross-domain matching no LLM can do without it.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6, marginTop: 12 }}>
            {seen.map(d => (
              <span key={d} style={{ fontSize: 11, padding: '3px 10px', borderRadius: 8, background: '#111827', border: `1px solid ${DOMAIN_COLORS[d] || '#374151'}66`, color: '#D1D5DB' }}>
                {DOMAINS.find(x => x.key === d)?.label || (d === 'personal' ? '❤️ Personal taste' : d)}
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 14, flexWrap: 'wrap' as const }}>
            <button
              onClick={onExplore}
              style={{ padding: '11px 20px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 700, background: 'linear-gradient(135deg, #8B5CF6, #059669)', color: '#fff', boxShadow: '0 4px 16px #8B5CF655', transition: 'transform 0.15s, box-shadow 0.15s' }}
            >
              🌌 Launch the Taste Bridge →
            </button>
            {hasLive ? (
              <span
                title="Recommendations are grounded in the live Qloo taste graph (not mock data)"
                style={{
                  fontSize: 12.5, fontWeight: 800, letterSpacing: 0.4,
                  color: '#052E16', background: '#6EE7B7',
                  padding: '6px 14px', borderRadius: 999,
                  border: '1px solid #A7F3D0',
                  boxShadow: '0 0 16px #6EE7B766',
                }}
              >
                ● Live Qloo data
              </span>
            ) : qlooEnabled ? (
              <span
                title="QLOO_API_KEY is set — live bridge results are on the way (search the 💡 Tastes tab or run a cross-domain fetch to populate)"
                style={{
                  fontSize: 12.5, fontWeight: 800, letterSpacing: 0.4,
                  color: '#052E16', background: '#34D399',
                  padding: '6px 14px', borderRadius: 999,
                  border: '1px solid #6EE7B7',
                  boxShadow: '0 0 12px #34D39944',
                }}
              >
                ● Qloo connected — building live bridge
              </span>
            ) : (
              <span
                title="QLOO_API_KEY is not set — showing the clearly-labelled demo preview"
                style={{
                  fontSize: 12.5, fontWeight: 800, letterSpacing: 0.4,
                  color: '#3B2006', background: '#FCD34D',
                  padding: '6px 14px', borderRadius: 999,
                  border: '1px solid #FDE68A',
                  boxShadow: '0 0 12px #FCD34D55',
                }}
              >
                ⚠ Demo preview
              </span>
            )}
          </div>
          <div style={{ fontSize: 10, fontStyle: 'italic', color: '#6B7280', marginTop: 6 }}>
            central anchor: “{centerLabel}” — bound to {personaName}
          </div>
        </div>

        <div style={{ flex: '1 1 320px', minWidth: 280 }}>
          <div
            onClick={onExplore}
            role="button"
            tabIndex={0}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onExplore() } }}
            title="Open the interactive Taste Bridge"
            style={{ cursor: 'pointer' }}
          >
            <TasteBridge compact centerLabel={centerLabel} zones={zones} dataSource={dataSource} animateText={animateText} reveal={reveal} qlooEnabled={qlooEnabled} />
          </div>
        </div>
      </div>
    </div>
  )
}