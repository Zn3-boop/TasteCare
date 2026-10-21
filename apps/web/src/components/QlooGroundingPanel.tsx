// Qloo Grounding Evidence — the visible proof that the agent used the Qloo taste
// graph in this turn's reasoning, not guesses. Rendered under each agent reply in
// AgentTab. The live/preview badge mirrors TasteBridge so the no-key demo never
// masquerades preview data as Qloo output. When the backend ships structured
// details (taste_entity_details / taste_recommendations / taste_location), the
// panel renders real thumbnails, the user's city, and recommendation cards —
// not just name chips and a raw text payload.
import { sx } from './sx'
import type { QlooEntityDetail } from '../api'
import { uniqueBy } from '../utils/list'
import { SafeImg } from './SafeImg'

type Props = {
  tasteEntities: string[]
  tasteDataSource: string
  qlooContext?: unknown
  tasteEntityDetails?: QlooEntityDetail[]
  tasteRecommendations?: QlooEntityDetail[]
  tasteLocation?: string
}

export function QlooGroundingPanel({
  tasteEntities,
  tasteDataSource,
  qlooContext,
  tasteEntityDetails,
  tasteRecommendations,
  tasteLocation,
}: Props) {
  const live = tasteDataSource === 'live'
  const accent = live ? '#059669' : '#F59E0B'

  // Backend chat responses have repeatedly shipped duplicate taste_entities /
  // entity_details (profile_likes leaking into grounding produces exact-string
  // duplicates — see server tests). React 19 crashes on duplicate list keys,
  // so dedupe every list before rendering and key with a unique composite.
  const entityList = uniqueBy(tasteEntityDetails || [], ent => ent.entity_id || ent.name || '')
  const tasteNameList = uniqueBy(tasteEntities || [], ent => ent)
  const recList = uniqueBy(tasteRecommendations || [], r => r.entity_id || r.name || '')

  // Grounding score helper: prefer the real Qloo match score, fall back to the
  // Qloo popularity when that is what the backend surfaced. Returns null when
  // neither exists so the UI never invents a percentage.
  const entScore = (ent: QlooEntityDetail | undefined): number | null => {
    const s = ent?.score ?? ent?.popularity ?? null
    return typeof s === 'number' && Number.isFinite(s) ? Math.round(s * 100) : null
  }

  return (
    <div style={{ marginTop: 8, width: '100%', maxWidth: 340, ...sx.card, padding: 12, border: `1px solid ${live ? '#05966944' : '#B4530944'}`, background: live ? '#0596690c' : '#7C2D120c' }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase' as const, color: accent, marginBottom: 6 }}>
        {live ? '● Live Qloo data' : tasteDataSource === '' ? '○ No Qloo data' : '⚠ Demo preview data'}
      </div>

      {tasteLocation ? (
        <div style={{ marginBottom: 8, fontSize: 11, color: '#E5E7EB' }}>
          <span style={{ background: '#111827', border: `1px solid ${accent}55`, padding: '3px 9px', borderRadius: 999 }}>
            📍 {tasteLocation}
          </span>
        </div>
      ) : null}

      <div style={{ fontSize: 12, fontWeight: 700, color: '#E5E7EB', marginBottom: 6, lineHeight: 1.4 }}>
        Qloo cultural taste entities used in this reply
      </div>

      <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 8 }}>
        {/* Qloo grounding evidence, expanded by default: put "why this comes from Qloo" in front of the judge */}
        {tasteEntities.length > 0 ? (
          entityList.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6 }}>
              {entityList.map((ent, idx) => (
                <span
                  key={ent.entity_id || `${ent.name}-${idx}`}
                  title={ent.domain ? `${ent.name} · ${ent.domain} · Qloo match ${entScore(ent)}` : `${ent.name} · Qloo match ${entScore(ent)}`}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: '#111827', border: `1px solid ${accent}55`, color: '#E5E7EB', padding: '3px 6px 3px 3px', borderRadius: 999, fontSize: 11 }}
                >
                  {ent.image ? (
                    <SafeImg
                      src={ent.image}
                      alt={ent.name}
                      fallbackStyle={{ width: 22, height: 22, borderRadius: '50%' }}
                      fallbackChar={ent.name}
                    />
                  ) : null}
                  <span>{ent.name}</span>
                  {ent.domain ? <span style={{ color: '#6B7280', fontSize: 10 }}>{ent.domain}</span> : null}
                  {entScore(ent) != null && (
                    <span style={{ fontSize: 10, fontWeight: 800, color: accent, background: `${accent}18`, padding: '2px 6px', borderRadius: 999 }}>
                      {entScore(ent)}%
                    </span>
                  )}
                </span>
              ))}
            </div>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 5 }}>
              {tasteNameList.map((ent) => (
                <span key={ent} style={{ background: '#111827', border: `1px solid ${accent}55`, color: '#E5E7EB', padding: '3px 9px', borderRadius: 999, fontSize: 11 }}>
                  {ent}
                </span>
              ))}
            </div>
          )
        ) : (
          <div style={{ fontSize: 11, color: '#9CA3AF', fontStyle: 'italic' }}>
            No Qloo entities resolved for this reply — showing the raw payload below.
          </div>
        )}
      </div>

      {tasteRecommendations && tasteRecommendations.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#E5E7EB', marginBottom: 6 }}>
            Qloo-grounded recommendations
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recList.slice(0, 6).map((r, i) => (
              <div
                key={r.entity_id || `${r.name || 'rec'}-${i}`}
                style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#111827', border: '1px solid #1F2937', borderRadius: 10, padding: 6 }}
              >
                {r.image ? (
                  <SafeImg
                    src={r.image}
                    alt={r.name}
                    fallbackStyle={{ width: 34, height: 34, borderRadius: 8 }}
                    fallbackChar={r.name}
                  />
                ) : (
                  <div style={{ width: 34, height: 34, borderRadius: 8, background: '#1F2937', display: 'flex', alignItems: 'center', justifyContent: 'center', color: accent, fontSize: 13, fontWeight: 700 }}>
                    {(r.name || '?')[0]}
                  </div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: '#E5E7EB', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {r.name}
                  </div>
                  {r.domain ? <div style={{ fontSize: 10, color: '#9CA3AF' }}>{r.domain}</div> : null}
                </div>
                {entScore(r) != null ? (
                  <div style={{ fontSize: 10, fontWeight: 800, color: accent, background: `${accent}18`, padding: '2px 6px', borderRadius: 999 }}>
                    {entScore(r)}%
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}

      <details open style={{ marginTop: 8 }}>
        <summary style={{ fontSize: 11, color: '#9CA3AF', cursor: 'pointer', fontWeight: 700 }}>
          {live ? '◈ Why Qloo — grounding (expanded)' : 'Raw Qloo context payload'}
        </summary>
        <pre style={{ fontSize: 10, color: '#D1D5DB', background: '#0b1020', border: '1px solid #1F2937', borderRadius: 8, padding: 8, overflow: 'auto', maxHeight: 160, whiteSpace: 'pre-wrap' as const, margin: '8px 0 0' }}>
          {typeof qlooContext === 'string' ? qlooContext : JSON.stringify(qlooContext, null, 2)}
        </pre>
      </details>
    </div>
  )
}
