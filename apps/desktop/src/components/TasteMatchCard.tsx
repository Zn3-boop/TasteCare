import type { QlooEntity } from '../hooks/useQloo'

const DOMAIN_COLORS: Record<string, string> = {
  music: '#1DB954', film: '#E50914', dining: '#FF6B35',
  fashion: '#C77DFF', travel: '#00B4D8', podcast: '#FFB703', book: '#8B5CF6',
}

interface TasteMatchCardProps {
  entity: QlooEntity
  rank?: number
  onClick?: () => void
}

export default function TasteMatchCard({ entity, rank, onClick }: TasteMatchCardProps) {
  const color = DOMAIN_COLORS[entity.domain || ''] || '#6B7280'
  const pct = entity.score ? Math.round(entity.score * 100) : null

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
        borderRadius: 8, background: '#111827', border: `1px solid ${color}22`,
        cursor: onClick ? 'pointer' : 'default', marginBottom: 4,
      }}
    >
      {rank && <span style={{ fontSize: 11, color: '#6B7280', fontWeight: 600 }}>#{rank}</span>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#E5E7EB', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entity.name}</div>
        <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 2 }}>
          {entity.type}{entity.domain ? ` · ${entity.domain}` : ''}
        </div>
      </div>
      {pct !== null && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color }}>{pct}%</span>
          <div style={{ width: 36, height: 3, borderRadius: 2, background: '#1F2937', overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', borderRadius: 2, background: color }} />
          </div>
        </div>
      )}
    </div>
  )
}