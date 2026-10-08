// Presentational UI primitives for the TasteCare web demo.
// Pure components — no state, no side effects. Imported by the tab components.

import type { QlooEntity, TasteCareRecommendation } from '../api'
import {
  DOMAIN_COLORS, CONSTRAINT_META, EN_WARNING, EN_CONSTRAINT_LABEL, EN_CONSTRAINT_ICON,
} from '../constants'

export const sx = {
  card: { borderRadius: 14, border: '1px solid #1F2937', background: '#111827', padding: 20 },
  input: { width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #374151', background: '#0b1020', color: '#E5E7EB', fontSize: 14, outline: 'none', transition: 'border-color 0.2s' },
  btnPrimary: { padding: '12px 24px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 700, background: 'linear-gradient(135deg, #FF6B35, #E85D26)', color: '#fff', boxShadow: '0 4px 14px #FF6B3544', transition: 'transform 0.15s, box-shadow 0.15s' },
  btnSecondary: { padding: '10px 20px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600, background: '#1F2937', color: '#9CA3AF', transition: 'background 0.15s' },
  label: { fontSize: 12, color: '#9CA3AF', marginBottom: 6, display: 'block', fontWeight: 500, letterSpacing: 0.3 },
  skeleton: { borderRadius: 8, background: 'linear-gradient(90deg, #1F2937 25%, #374151 50%, #1F2937 75%)', backgroundSize: '200% 100%', animation: 'shimmer 1.5s infinite' },
}

export function SkeletonRow() {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '12px 16px', borderRadius: 10, background: '#111827', border: '1px solid #1F2937' }}>
      <div style={{ width: 32, height: 32, ...sx.skeleton }} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ width: '60%', height: 14, ...sx.skeleton }} />
        <div style={{ width: '40%', height: 10, ...sx.skeleton }} />
      </div>
    </div>
  )
}

// G1a: honest score display. `source` is pluggable — if a real Qloo affinity
// score is ever wired, swap the source prop and the UI stays unchanged.
export function ScoreBadge({ value, source = 'qloo-popularity' }: { value?: number; source?: string }) {
  if (value == null) return null
  const label = source === 'qloo-affinity' ? 'Qloo affinity' : 'Qloo popularity'
  return (
    <span style={{ fontSize: 11, color: '#9CA3AF' }}>
      {Math.round(value * 100)}% · {label}
    </span>
  )
}

export function EntityCard({ entity, rank, onClick }: { entity: QlooEntity; rank?: number; onClick?: () => void }) {
  const color = DOMAIN_COLORS[entity.domain || ''] || '#6B7280'
  const pct = entity.score ? Math.round(entity.score * 100) : null
  return (
    <div onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderRadius: 10, background: '#111827', border: `1px solid ${color}18`, cursor: onClick ? 'pointer' : 'default', transition: 'background 0.15s' }}>
      {rank != null && <span style={{ fontSize: 11, color: '#6B7280', fontWeight: 700, minWidth: 20 }}>#{rank}</span>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#E5E7EB', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entity.name}</div>
        <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>{entity.type}{entity.domain ? ` · ${entity.domain}` : ''}</div>
      </div>
      {pct !== null && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color }}>{pct}%</span>
          <div style={{ width: 44, height: 3, borderRadius: 2, background: '#1F2937', overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', borderRadius: 2, background: color }} />
          </div>
        </div>
      )}
    </div>
  )
}

export function TasteCareCard({ rec, rank, activeConstraints = [] }: { rec: TasteCareRecommendation; rank?: number; activeConstraints?: string[] }) {
  const health = rec.health
  const warnings = (health?.warnings || []).map((w) => EN_WARNING[w] || w)
  const wLower = warnings.join(' ').toLowerCase()
  const constraintFail = (c: string) =>
    (c === 'soft_chewable' && (wLower.includes('hard') || wLower.includes('crunchy'))) ||
    (c === 'low_sodium' && wLower.includes('sodium')) ||
    (c === 'low_sugar' && wLower.includes('sugar')) ||
    (c === 'medications' && (wLower.includes('medication') || wLower.includes('grapefruit') || wLower.includes('vitamin') || wLower.includes('alcohol') || wLower.includes('tyramine') || wLower.includes('licorice')))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '14px 18px', borderRadius: 12, background: health?.passes ? '#0D1F17' : '#111827', border: `1px solid ${health?.passes ? '#065F4644' : '#FF6B3522'}`, overflow: 'hidden' }}>
      <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
        {rec.image ? (
          <div style={{ width: 104, height: 72, borderRadius: 8, overflow: 'hidden', flexShrink: 0, background: 'linear-gradient(135deg,#1F2937,#374151)' }}>
            <img src={rec.image} alt={rec.name} loading="lazy" onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
          </div>
        ) : (
          <div style={{ width: 104, height: 72, borderRadius: 8, flexShrink: 0, background: 'linear-gradient(135deg,#FF6B3518,#1F2937)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26 }}>🍽️</div>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {rank != null && <span style={{ fontSize: 11, color: '#6B7280', fontWeight: 700 }}>#{rank}</span>}
            <div style={{ fontSize: 15, fontWeight: 600, color: '#E5E7EB', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rec.name}</div>
          </div>
          <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}><ScoreBadge value={rec.fit ?? rec.popularity} source={rec.fit_source === 'qloo-affinity' ? 'qloo-affinity' : 'qloo-popularity'} /></div>
          {rec.description && <div style={{ fontSize: 12, color: '#D1D5DB', marginTop: 6, lineHeight: 1.5 }}>{rec.description}</div>}
          {rec.address && <div style={{ fontSize: 11, color: '#6B7280', marginTop: 4 }}>📍 {rec.address}</div>}
        </div>
        {health?.passes != null && (
          <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 8, background: health.passes ? '#065F46' : '#7F1D1D', color: health.passes ? '#6EE7B7' : '#FCA5A5', whiteSpace: 'nowrap', flexShrink: 0 }}>{health.passes ? '✓ Fits constraints' : '⚠ Review'}</span>
        )}
      </div>
      {rec.tags && rec.tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {rec.tags.slice(0, 6).map((t, i) => <span key={i} style={{ fontSize: 10, color: '#9CA3AF', background: '#1F2937', padding: '2px 8px', borderRadius: 6 }}>{t}</span>)}
        </div>
      )}
      {activeConstraints.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {activeConstraints.map((c) => {
            const meta = CONSTRAINT_META.find((m) => m.key === c)
            const fail = constraintFail(c)
            const label = EN_CONSTRAINT_LABEL[c] || meta?.label || c
            return (
              <span key={c} title={meta?.hint} style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6, background: fail ? '#7F1D1D33' : '#065F4633', color: fail ? '#FCA5A5' : '#6EE7B7' }}>
                {fail ? '✗' : '✓'} {EN_CONSTRAINT_ICON[c] || '🔍'} {label}
              </span>
            )
          })}
        </div>
      )}
      {warnings.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {warnings.map((w, i) => <span key={i} style={{ fontSize: 11, color: '#FCA5A5' }}>⚠ {w}</span>)}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, borderTop: '1px solid #1F2937', paddingTop: 8 }}>
        <div style={{ fontSize: 11.5, lineHeight: 1.5, color: '#E5E7EB' }}>
          <span style={{ fontWeight: 700, color: '#FF6B35' }}>✨ Cultural match:</span>{' '}
          {rec.cultural_match || 'Grounded in your cultural tastes via the Qloo taste graph.'}
        </div>
        <div style={{ fontSize: 11.5, lineHeight: 1.5, color: health?.passes ? '#6EE7B7' : '#FCA5A5' }}>
          <span style={{ fontWeight: 700, color: '#3B82F6' }}>🛡️ Safety check:</span>{' '}
          {rec.safety_validation || (health?.passes ? 'All active constraints passed.' : 'Review needed for your active health constraints.')}
        </div>
      </div>
    </div>
  )
}
