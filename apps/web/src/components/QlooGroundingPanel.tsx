// Qloo Grounding Evidence — the visible proof that the agent used the Qloo taste
// graph in this turn's reasoning, not guesses. Rendered under each agent reply in
// AgentTab. The live/preview badge mirrors TasteBridge so the no-key demo never
// masquerades preview data as Qloo output.
import { sx } from './ui'

type Props = {
  tasteEntities: string[]
  tasteDataSource: string
  qlooContext?: unknown
}

export function QlooGroundingPanel({ tasteEntities, tasteDataSource, qlooContext }: Props) {
  const live = tasteDataSource === 'live'
  const accent = live ? '#059669' : '#F59E0B'

  return (
    <div style={{ marginTop: 8, width: '100%', maxWidth: 340, ...sx.card, padding: 12, border: `1px solid ${live ? '#05966944' : '#B4530944'}`, background: live ? '#0596690c' : '#7C2D120c' }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase' as const, color: accent, marginBottom: 6 }}>
        {live ? '● Live Qloo data' : '⚠ Demo preview data'}
      </div>

      <div style={{ fontSize: 12, fontWeight: 700, color: '#E5E7EB', marginBottom: 6, lineHeight: 1.4 }}>
        Qloo cultural taste entities used in this reply
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 5 }}>
        {tasteEntities.map((ent) => (
          <span key={ent} style={{ background: '#111827', border: '1px solid #374151', color: '#E5E7EB', padding: '3px 9px', borderRadius: 999, fontSize: 11 }}>
            {ent}
          </span>
        ))}
      </div>

      <details style={{ marginTop: 8 }}>
        <summary style={{ fontSize: 11, color: '#9CA3AF', cursor: 'pointer' }}>Raw Qloo context payload</summary>
        <pre style={{ fontSize: 10, color: '#D1D5DB', background: '#0b1020', border: '1px solid #1F2937', borderRadius: 8, padding: 8, overflow: 'auto', maxHeight: 160, whiteSpace: 'pre-wrap' as const, margin: 0 }}>
          {typeof qlooContext === 'string' ? qlooContext : JSON.stringify(qlooContext, null, 2)}
        </pre>
      </details>
    </div>
  )
}
