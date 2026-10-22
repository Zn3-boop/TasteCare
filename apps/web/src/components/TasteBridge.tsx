// Taste Bridge — a full-screen cross-domain constellation.
// Renders the "thing only Qloo can do": one taste anchor radiating into multiple
// cultural domains, node size encodes affinity, and edges carry a "why"
// relationship. This is a pure presentational component: it receives a
// ready-to-draw graph and labels it honestly (`live` vs `preview`) so the no-key
// demo never masquerades demo data as Qloo output.
// `compact` renders JUST the constellation (no header / legend / detail panel)
// so the first-screen hero can embed the exact same graph.

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
  compact?: boolean
  /**
   * Whether the backend reports Qloo enabled. When a key IS set but live
   * cross-domain results are still empty (preheat failed / request in flight),
   * the banner must say "connected" instead of the misleading "isn't connected
   * yet" — the rest of the app is live and judges shouldn't think the key is
   * missing.
   */
  qlooEnabled?: boolean
  /**
   * 终版契约③: 自定义人物用"文字节点星图"（200ms 交错淡入 + 慢速描边），
   * Maria 预置继续用原有动画。Custom personas get text-labeled nodes that
   * stagger in and slow-draw their edges; the built-in Maria profile reuses the
   * original constellation look so the judges see one consistent demo default.
   */
  animateText?: boolean
  /**
   * 终版契约③补充: reveal — animate node/edge ARRIVAL (staggered 200ms pop-in +
   * slow edge draw) whenever the graph data changes, e.g. right after the USER's
   * own cross-domain search. Independent of `animateText` (which only controls
   * the text-labeled node style for custom personas) — Maria's dot constellation
   * also assembles progressively now.
   */
  reveal?: boolean
}

const VIEW_W = 780
const VIEW_H = 620
const CX = VIEW_W / 2
const CY = VIEW_H / 2
const MIN_R = 112
const MAX_R = 250

// Word-boundary wrap for the CENTER label, max two lines. A hard mid-word slice
// ("Federico Fell…") looks broken AND gets mangled by browser auto-translate
// (translators read the clipped fragment "Fell" as the verb → "费德里科跌倒了").
// Whole words only; a single over-long word is the only case that ellipsizes.
function wrapCenterLabel(label: string, maxPerLine: number): string[] {
  const words = label.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return ['']
  if (words.length === 1) {
    const w = words[0]
    return [w.length > maxPerLine ? `${w.slice(0, maxPerLine - 1)}…` : w]
  }
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    const cand = cur ? `${cur} ${w}` : w
    if (cand.length <= maxPerLine) { cur = cand; continue }
    if (cur) { lines.push(cur); cur = '' }
    lines.push(w.length > maxPerLine ? `${w.slice(0, maxPerLine - 1)}…` : w)
    if (lines.length >= 2) break
  }
  if (cur && lines.length < 2) lines.push(cur)
  return lines.length >= 2 ? lines.slice(0, 2) : lines
}

// Word-boundary truncation for NODE labels: keep whole words up to `max` chars,
// then "…" — never split a word mid-way (same translation-safety rationale).
function truncateLabel(name: string, max: number): string {
  const t = name.trim()
  if (t.length <= max) return t
  const words = t.split(/\s+/).filter(Boolean)
  let out = ''
  for (const w of words) {
    const cand = out ? `${out} ${w}` : w
    if (cand.length > max) break
    out = cand
  }
  return out.length >= 4 ? `${out}…` : `${t.slice(0, max - 1)}…`
}

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

export function TasteBridge({ centerLabel, centerSub, zones, dataSource, domainStatuses, onNodeClick, compact = false, animateText = false, reveal = false, qlooEnabled = false }: Props) {
  const revealActive = reveal || animateText
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
      // Live Qloo cross-domain payloads can contain the SAME entity_id twice in
      // one domain. Duplicate SVG keys make React mis-reconcile and crash with
      // "Failed to execute 'removeChild' on 'Node'" — dedupe per zone so every
      // node id is unique (guaranteed unique composite keys below as well).
      const seen = new Set<string>()
      zone.nodes.forEach((n, i) => {
        const uid = n.entity_id || `${zone.domain}-${n.name}`
        if (seen.has(uid)) return
        seen.add(uid)
        const m = zone.nodes.length
        // fan the domain's nodes around its spoke so they don't overlap.
        const ny = (i - (m - 1) / 2) * 13
        const alpha = theta + Math.atan2(ny, R)
        const rr = Math.sqrt(R * R + ny * ny)
        const baseR = 6 + (n.popularity ?? 0.5) * 6
        out.push({
          entity_id: uid,
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

  // Boost SVG text sizes in compact mode so the constellation stays readable when
  // the 780-unit viewBox renders at a narrow hero-column width (~440px).
  const graph = nodes.length > 0 ? (
    <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} style={{ width: '100%', height: 'auto', background: '#0b1020', borderRadius: 12, border: '1px solid #1F2937', display: 'block' }}>
      {/* 终版契约③: custom-persona text-node mode draws edges slowly + staggers
          nodes in 200ms apart; the built-in Maria profile keeps edges static. */}
      {nodes.map((n, i) => (
        <line
          key={`e-${n.domain}:${n.entity_id}`} x1={CX} y1={CY} x2={n.x} y2={n.y}
          stroke={n.color} strokeOpacity={0.35} strokeWidth={1.4}
          className={revealActive ? 'tb-edge-draw' : undefined}
          style={revealActive ? { animationDelay: `${i * 120}ms` } : undefined}
        />
      ))}
      {[MIN_R, (MIN_R + MAX_R) / 2, MAX_R].map(r => (
        <circle key={r} cx={CX} cy={CY} r={r} fill="none" stroke="#1F2937" strokeWidth={1} strokeDasharray="3 5" />
      ))}
      <circle cx={CX} cy={CY} r={30} fill="#FF6B35" fillOpacity={0.18} stroke="#FF6B35" strokeWidth={2} />
      {(() => {
        const lines = wrapCenterLabel(centerLabel, compact ? 16 : 34)
        const fs = compact ? (lines.length > 1 ? 13 : 18) : 10
        const lh = compact ? (lines.length > 1 ? 15 : 0) : 12
        const startY = CY + 4 - ((lines.length - 1) * lh) / 2
        return (
          <g>
            <title>{centerLabel}</title>
            {lines.map((ln, i) => (
              <text key={`c${i}`} x={CX} y={startY + i * lh} textAnchor="middle" fill="#fff" fontSize={fs} fontWeight={700}>{ln}</text>
            ))}
          </g>
        )
      })()}
      {nodes.map((n, i) => (
        <g key={`n-${n.domain}:${n.entity_id}`} onMouseEnter={() => { setHovered(n); onNodeClick?.(n) }}
          onMouseLeave={() => setHovered(null)}
          onClick={() => setSelected(n)}
          className={revealActive ? 'tb-node-in' : undefined}
          style={revealActive ? { animationDelay: `${i * 200}ms` } : undefined}>
          <circle cx={n.x} cy={n.y} r={n.r * 1.7} fill="transparent" />
          {animateText ? (
            <g>
              <circle cx={n.x} cy={n.y} r={n.r + 16} fill={n.color} fillOpacity={0.14} stroke={n.color} strokeOpacity={0.8} strokeWidth={1.4} />
              <text x={n.x} y={n.y + (compact ? n.r + 16 : n.r + 9)} textAnchor="middle" fontSize={compact ? 14 : 9} fontWeight={700} fill="#F3F4F6">{truncateLabel(n.name, compact ? 24 : 22)}</text>
            </g>
          ) : (
            <g>
              <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} fillOpacity={0.85} stroke="#fff" strokeOpacity={0.6} strokeWidth={1.2} />
              <text x={n.x} y={n.y + n.r + 11} textAnchor="middle" fontSize={compact ? 17 : 9.5} fill="#D1D5DB">{truncateLabel(n.name, 20)}</text>
            </g>
          )}
        </g>
      ))}
    </svg>
  ) : null

  if (compact) {
    return graph || (
      <div style={{ padding: 28, textAlign: 'center', color: '#6B7280', fontSize: 12, fontStyle: 'italic' }}>
        🌌 Add taste anchors to see the constellation.
      </div>
    )
  }

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
        {centerSub && (
          <p style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>{centerSub}</p>
        )}
        {dataSource === 'preview' && (
          <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, background: '#7C2D1222', border: '1px solid #B4530944' }}>
            {qlooEnabled ? (
              <>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#6EE7B7' }}>● Qloo connected</span>
                <span style={{ fontSize: 11, color: '#D1D5DB' }}> — no live cross-domain results yet; showing the clearly-labelled demo preview constellation.</span>
              </>
            ) : (
              <>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#FCD34D' }}>⚠ Demo preview data</span>
                <span style={{ fontSize: 11, color: '#D1D5DB' }}> — Qloo isn't connected yet. Add <code style={{ background: '#111827', padding: '1px 5px', borderRadius: 4 }}>QLOO_API_KEY</code> to load live cross-domain results.</span>
              </>
            )}
          </div>
        )}
        {dataSource === 'live' && (
          <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, background: '#065F4622', border: '1px solid #05966944' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#6EE7B7' }}>● Live Qloo data</span>
            <span style={{ fontSize: 11, color: '#D1D5DB' }}> — edges are taste-graph affinity from Qloo. Hover a node for its domain.</span>
          </div>
        )}
      </div>

      {graph}

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
                <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 6 }}>
                  Popularity {Math.round(Math.min(1, Math.max(0, detail.popularity)) * 100)}% (Qloo score, 0–1)
                </div>
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