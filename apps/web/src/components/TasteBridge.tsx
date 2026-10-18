// Taste Bridge — a full-screen cross-domain constellation.
// Renders the "thing only Qloo can do": one taste anchor radiating into multiple
// cultural domains, node size encodes affinity, and edges carry a "why"
// relationship. This is a pure presentational component: it receives a
// ready-to-draw graph and labels it honestly (`live` vs `preview`) so the no-key
// demo never masquerades demo data as Qloo output.

import { useMemo, useState } from 'react'
import { DOMAIN_COLORS, type DomainStatus, DOMAIN_LIST } from '../constants'
import { sx } from './sx'

export type BridgeZone = {
  domain: string
  nodes: { entity_id: string; name: string; why?: string; popularity?: number | null }[]
}

type Props = {
  centerLabel: string
  centerSub?: string
  zones: BridgeZone[]
  dataSource: 'live' | 'preview'
  loading?: boolean
  domainStatuses?: Record<string, DomainStatus>
  onNodeClick?: (node: { entity_id: string; name: string; domain: string; why?: string }) => void
}

const VIEW_W = 780
const VIEW_H = 620
const CX = VIEW_W / 2
const CY = VIEW_H / 2
const MIN_R = 112
const MAX_R = 250

type LayoutNode = {
  entity_id: string
  name: string
  domain: string
  color: string
  x: number
  y: number
  r: number
  why?: string
  popularity?: number | null
}

function domainBadge(status: DomainStatus, domain: string) {
  const map = {
    done: { icon: '✓', color: '#6EE7B7', bg: '#065F46' },
    loading: { icon: '⏳', color: '#FCD34D', bg: '#78350F' },
    idle: { icon: '·', color: '#6B7280', bg: '#1F2937' },
  }[status]
  return (
    <span style={{ fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 6, background: map.bg, color: map.color, fontWeight: 600 }}>
      {map.icon} {domain}
    </span>
  )
}

export function TasteBridge({ centerLabel, zones, dataSource, loading, domainStatuses, onNodeClick }: Props) {
  const [hovered, setHovered] = useState<LayoutNode | null>(null)
  const [selected, setSelected] = useState<LayoutNode | null>(null)

  const nodes = useMemo<LayoutNode[]>(() => {
    const active = (zones || []).filter(z => z.nodes && z.nodes.length > 0)
    const out: LayoutNode[] = []
    const nDomains = active.length
    const rStep = nDomains > 1 ? (MAX_R - MIN_R) / Math.max(1, nDomains - 1) : 0
    active.forEach((zone, dIdx) => {
      const color = DOMAIN_COLORS[zone.domain] || '#6B7280'
      const theta = (dIdx / Math.max(1, nDomains)) * Math.PI * 2 - Math.PI / 2
      const R = nDomains > 1 ? MIN_R + dIdx * rStep : MIN_R
      zone.nodes.forEach((n, i) => {
        const m = zone.nodes.length
        // fan the domain's nodes around its spoke so they don't overlap.
        const ny = (i - (m - 1) / 2) * 13
        const alpha = theta + Math.atan2(ny, R)
        const rr = Math.sqrt(R * R + ny * ny)
        const baseR = 6 + (n.popularity ?? 0.5) * 6
        out.push({
          entity_id: n.entity_id || `${zone.domain}-${n.name}`,
          name: n.name,
          domain: zone.domain,
          color,
          x: CX + Math.cos(alpha) * rr,
          y: CY + Math.sin(alpha) * rr,
          r: Math.max(5, Math.min(13, baseR)),
          why: n.why,
          popularity: n.popularity,
        })
      })
    })
    return out
  }, [zones])

  const detail = hovered || selected

  if (!nodes.length) {
    return (
      <div style={{ ...sx.card, textAlign: 'center', padding: 40, color: '#6B7280', fontSize: 14 }}>
        <div style={{ fontSize: 34, marginBottom: 8 }}>🌌</div>
        No cross-domain connections yet. {dataSource === 'live'
          ? 'Connect QLOO_API_KEY or run a cross-domain search.'
          : 'Add taste anchors (💡 Tastes tab) to see the constellation.'}
      </div>
    )
  }

  return (
    <div style={{ ...sx.card, border: `1px solid ${dataSource === 'live' ? '#05966944' : '#B4530944'}`, background: `linear-gradient(160deg, ${dataSource === 'live' ? '#0596690c' : '#7C2D120c'}, #0b1020)` }}>
      <div style={{ marginBottom: 14 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: dataSource === 'live' ? '#059669' : '#F59E0B', marginBottom: 6 }}>
          🌌 Taste Bridge
        </h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          One taste anchor, <strong style={{ color: dataSource === 'live' ? '#6EE7B7' : '#FCD34D' }}>radiating across every cultural domain</strong>. No LLM can draw these
          bridges without a taste graph — this is the core of Qloo's advantage.
        </p>
        {dataSource === 'preview' && (
          <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, background: '#7C2D1222', border: '1px solid #B4530944' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#FCD34D' }}>⚠ Demo preview data</span>
            <span style={{ fontSize: 11, color: '#D1D5DB' }}> — Qloo isn't connected yet. Add <code style={{ background: '#111827', padding: '1px 5px', borderRadius: 4 }}>QLOO_API_KEY</code> to load live cross-domain results.</span>
          </div>
        )}
        {dataSource === 'live' && (
          <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, background: '#065F4622', border: '1px solid #05966944' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#6EE7B7' }}>● Live Qloo data</span>
            <span style={{ fontSize: 11, color: '#D1D5DB' }}> — edges are taste-graph affinity from Qloo. Hover a node for its domain.</span>
          </div>
        )}
      </div>

      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} style={{ width: '100%', height: 'auto', background: '#0b1020', borderRadius: 12, border: '1px solid #1F2937' }}>
        {nodes.map(n => (
          <line key={`e-${n.entity_id}`} x1={CX} y1={CY} x2={n.x} y2={n.y}
            stroke={n.color} strokeOpacity={0.35} strokeWidth={1.4} />
        ))}
        {[MIN_R, (MIN_R + MAX_R) / 2, MAX_R].map(r => (
          <circle key={r} cx={CX} cy={CY} r={r} fill="none" stroke="#1F2937" strokeWidth={1} strokeDasharray="3 5" />
        ))}
        <circle cx={CX} cy={CY} r={30} fill="#FF6B35" fillOpacity={0.18} stroke="#FF6B35" strokeWidth={2} />
        <text x={CX} y={CY + 4} textAnchor="middle" fill="#fff" fontSize="10" fontWeight={700}>{centerLabel.length > 14 ? centerLabel.slice(0, 13) + '…' : centerLabel}</text>
        {nodes.map(n => (
          <g key={n.entity_id} style={{ cursor: 'pointer' }}
            onMouseEnter={() => { setHovered(n); onNodeClick?.(n) }}
            onMouseLeave={() => setHovered(null)}
            onClick={() => setSelected(n)}>
            <circle cx={n.x} cy={n.y} r={n.r * 1.7} fill="transparent" />
            <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} fillOpacity={0.85} stroke="#fff" strokeOpacity={0.6} strokeWidth={1.2} />
            <text x={n.x} y={n.y + n.r + 11} textAnchor="middle" fontSize="9.5" fill="#D1D5DB">{n.name.length > 20 ? n.name.slice(0, 19) + '…' : n.name}</text>
          </g>
        ))}
      </svg>

      <div style={{ display: 'flex', gap: 24, marginTop: 14, flexWrap: 'wrap' as const }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#9CA3AF', marginBottom: 8 }}>Domain progress</div>
          <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 5, marginBottom: 12 }}>
            {DOMAIN_LIST.map(d => (
              <span key={d}>{domainBadge(domainStatuses?.[d] ?? (zones.some(z => z.domain === d) ? 'done' : 'idle'), d)}</span>
            ))}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#9CA3AF', marginBottom: 8 }}>Domain legend</div>
          <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6 }}>
            {zones.filter(z => z.nodes.length).map(z => (
              <span key={z.domain} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#E5E7EB', padding: '3px 10px', borderRadius: 8, background: '#111827', border: '1px solid #374151' }}>
                <span style={{ width: 9, height: 9, borderRadius: 50, background: DOMAIN_COLORS[z.domain] || '#6B7280' }} />
                <span style={{ textTransform: 'capitalize' as const }}>{z.domain}</span>
              </span>
            ))}
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 240 }}>
          {detail ? (
            <div style={{ borderRadius: 10, border: `1px solid ${detail.color}44`, background: '#111827', padding: '12px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 50, background: detail.color }} />
                <span style={{ fontSize: 14, fontWeight: 700, color: '#E5E7EB' }}>{detail.name}</span>
                <span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'capitalize' as const }}>· {detail.domain}</span>
              </div>
              <div style={{ fontSize: 12, color: '#D1D5DB', lineHeight: 1.6 }}>{detail.why || `Culturally adjacent to “${centerLabel}” in the ${detail.domain} taste graph.`}</div>
              {detail.popularity != null && (
                <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 6 }}>Popularity {Math.round(detail.popularity * 100)}%</div>
              )}
            </div>
          ) : (
            <div style={{ fontSize: 12, color: '#6B7280', fontStyle: 'italic' }}>
              Hover or click a node to see why this cultural connection exists.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}