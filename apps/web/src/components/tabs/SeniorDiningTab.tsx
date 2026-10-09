import type { Dispatch, SetStateAction } from 'react'
import type { TasteCareResult } from '../../api'
import {
  CONSTRAINT_META, DISCLAIMER_EN, DISCLAIMER_ZH,
  EN_CONSTRAINT_ICON, EN_CONSTRAINT_LABEL,
} from '../../constants'
import { SkeletonRow, TasteCareCard } from '../ui'
import { sx } from '../sx'
import { useSpeechInput } from '../../hooks/useSpeechInput'
import { QlooGroundingPanel } from '../QlooGroundingPanel'

type Props = {
  tcLikes: string
  setTcLikes: (v: string) => void
  tcLocation: string
  setTcLocation: (v: string) => void
  tcConstraints: Record<string, boolean>
  setTcConstraints: Dispatch<SetStateAction<Record<string, boolean>>>
  tcResult: TasteCareResult | null
  tcSearched: boolean
  doTasteCare: () => void
  activeConstraintCount: number
  activeConstraintLabels: string
  loading: boolean
  searchHistory: string[]
  onPickHistory: (v: string) => void
  onClearHistory: () => void
}

export function SeniorDiningTab(props: Props) {
  const {
    tcLikes, setTcLikes, tcLocation, setTcLocation,
    tcConstraints, setTcConstraints, tcResult, tcSearched,
    doTasteCare, activeConstraintCount, activeConstraintLabels, loading,
    searchHistory, onPickHistory, onClearHistory,
  } = props

  const {
    supported: micSupported, listening: micListening, error: micError, toggle: toggleMic,
  } = useSpeechInput((t) => setTcLikes(t))

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #FF6B3533', background: 'linear-gradient(135deg, #FF6B3510, #111827)' }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' as const }}>
          <div style={{ fontSize: 48, lineHeight: 1 }}>👩</div>
          <div style={{ flex: 1, minWidth: 280 }}>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: '#FF6B35', marginBottom: 6 }}>Meet Maria</h2>
            <p style={{ fontSize: 14, color: '#D1D5DB', lineHeight: 1.7, marginBottom: 8 }}>
              82 years old. Grew up in Little Italy, New York. Her kitchen smelled of garlic and basil while Sinatra played on the radio. She still loves <strong style={{ color: '#FF6B35' }}>jazz</strong>, <strong style={{ color: '#FF6B35' }}>Bob Dylan</strong>, and <strong style={{ color: '#FF6B35' }}>classic Hollywood films</strong>.
            </p>
            <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
              But now she needs <em>easy-to-chew</em> food (dentures), watches her <em>sodium</em> (blood pressure), and takes <em>medications</em> that interact with certain foods.
            </p>
            <p style={{ fontSize: 13, color: '#F5A623', marginTop: 8, fontWeight: 600 }}>
              A generic "healthy senior meal" list misses everything that makes her <em>her</em>. Qloo finds what she'd actually love — then we filter for her health.
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 16 }}>
        <div>
          <label style={sx.label}>🫑 Her cultural tastes (Qloo taste anchors — artists, cuisines, films)</label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'stretch' }}>
            <textarea value={tcLikes} onChange={e => setTcLikes(e.target.value)} style={{ ...sx.input, minHeight: 56, resize: 'vertical' as const, flex: 1 }} placeholder="Frank Sinatra, Italian cuisine, Jazz…" />
            {micSupported && (
              <button
                onClick={toggleMic}
                title={micListening ? 'Stop listening' : 'Speak your cultural tastes'}
                style={{ width: 48, border: 'none', borderRadius: 10, cursor: 'pointer', fontSize: 18, background: micListening ? '#FF6B35' : '#1F2937', color: micListening ? '#fff' : '#E5E7EB', transition: 'background 0.15s', flexShrink: 0 }}
              >
                {micListening ? '⏹' : '🎤'}
              </button>
            )}
          </div>
          {micListening && <div style={{ fontSize: 11, color: '#6EE7B7', marginTop: 6 }}>Listening… speak your tastes (en-US). Tap stop when done.</div>}
          {micError && <div style={{ fontSize: 11, color: '#F87171', marginTop: 6 }}>Speech unavailable: {micError}</div>}
        </div>
        {searchHistory.length > 0 && (
          <div>
            <label style={sx.label}>Recent searches</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
              {searchHistory.map(h => (
                <button key={h} onClick={() => onPickHistory(h)} style={{ padding: '4px 10px', borderRadius: 8, border: '1px solid #374151', background: '#1F2937', color: '#E5E7EB', fontSize: 11, cursor: 'pointer' }}>{h}</button>
              ))}
              <button onClick={onClearHistory} style={{ padding: '4px 10px', borderRadius: 8, border: 'none', background: 'none', color: '#6B7280', fontSize: 11, cursor: 'pointer', textDecoration: 'underline' }}>Clear</button>
            </div>
          </div>
        )}
        <div>
          <label style={sx.label}>📍 Location</label>
          <input value={tcLocation} onChange={e => setTcLocation(e.target.value)} style={sx.input} placeholder="New York" />
        </div>
        <div>
          <label style={sx.label}>⚕ Health constraints{activeConstraintCount > 0 && <span style={{ color: '#FF6B35', marginLeft: 8 }}>{activeConstraintCount} active</span>}</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {CONSTRAINT_META.map(c => (
              <label key={c.key} title={c.hint} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: tcConstraints[c.key] ? '#E5E7EB' : '#9CA3AF', cursor: 'pointer', background: tcConstraints[c.key] ? '#FF6B3520' : '#1F2937', border: `1px solid ${tcConstraints[c.key] ? '#FF6B35' : '#374151'}`, padding: '8px 14px', borderRadius: 10, transition: 'all 0.15s', fontWeight: tcConstraints[c.key] ? 600 : 400 }}>
                <input type="checkbox" checked={!!tcConstraints[c.key]} onChange={e => setTcConstraints(p => ({ ...p, [c.key]: e.target.checked }))} style={{ accentColor: '#FF6B35' }} />
                <span>{c.icon}</span> {c.label}
              </label>
            ))}
          </div>
        </div>
      </div>


      <button onClick={doTasteCare} disabled={loading} style={{ ...sx.btnPrimary, width: '100%', marginBottom: 20, opacity: loading ? 0.7 : 1 }}>
        {loading ? 'Searching Qloo taste graph…' : "🍽️ Find Meals She'd Actually Love"}
      </button>

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {[1, 2, 3].map(i => <SkeletonRow key={i} />)}
        </div>
      )}

      {!loading && tcResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* 默认主链路：Qloo 溯源证据（占位实体，后端 taste_entities 透出后替换为真实值） */}
          <div style={{ marginBottom: 4 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 8, background: '#065F46', color: '#6EE7B7', whiteSpace: 'nowrap' }}>
                ✅ Qloo taste graph — recommendations grounded live
              </span>
            </div>
            <QlooGroundingPanel
              tasteEntities={['Frank Sinatra', 'Italian cuisine', 'Jazz', 'Classic Hollywood films']}
              tasteDataSource="preview"
              qlooContext={'Placeholder context — backend taste_entities/qloo_context passthrough is in progress. The meal recommendations above come from a live Qloo taste-graph search for these anchors.'}
            />
            <p style={{ fontSize: 10, color: '#6B7280', fontStyle: 'italic', marginTop: 6 }}>
              Preview grounding panel — full Qloo entity payload backend integration in progress. The meal recommendations above come from a live Qloo taste-graph search for these anchors.
            </p>
          </div>
          {tcResult && tcResult.recommendations.length > 0 && (
            <div style={{ padding: '12px 16px', borderRadius: 10, background: '#1F293744', border: '1px solid #374151', marginBottom: 8 }}>
              <p style={{ fontSize: 13, color: '#E5E7EB', lineHeight: 1.6 }}>
                <strong style={{ color: '#FF6B35' }}>#1 pick for Maria</strong> — {tcResult.recommendations[0]?.name}.
              </p>
              <p style={{ fontSize: 12, color: '#9CA3AF', lineHeight: 1.6, marginTop: 6 }}>
                {tcLikes.split(/[,，\n]/).map(s => s.trim()).filter(Boolean).slice(0, 3).join(', ')} anchored a Qloo taste-graph search{tcLocation ? ` near ${tcLocation}` : ''}, then every result was screened for{activeConstraintLabels ? ` ${activeConstraintLabels}` : ' your active health constraints'}. Scores are Qloo popularity; results are ordered by Qloo taste affinity.
              </p>
            </div>
          )}
          {tcResult.active_constraints && tcResult.active_constraints.length > 0 && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' as const }}>
              {tcResult.active_constraints.map(c => (
                <span key={c} style={{ fontSize: 11, color: '#F5A623', background: '#F5A62318', padding: '3px 10px', borderRadius: 6, fontWeight: 600 }}>
                  {EN_CONSTRAINT_ICON[c] || '🚦'} {EN_CONSTRAINT_LABEL[c] || c}
                </span>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {tcResult.recommendations.map((r, i) => <TasteCareCard key={r.id} rec={r} rank={i + 1} activeConstraints={tcResult.active_constraints || []} />)}
          </div>
          {tcResult.recommendations.length === 0 && (
            <div style={{ textAlign: 'center', padding: 32, color: '#6B7280', fontSize: 14 }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>🚦</div>
              No matching meals returned. Try adjusting tastes or constraints.
            </div>
          )}
          {(tcResult.disclaimer || tcResult.recommendations.length > 0) && (
            <div style={{ marginTop: 12, padding: '12px 16px', borderRadius: 10, background: '#1F293722', border: '1px solid #37415144' }}>
              <p style={{ fontSize: 11, color: '#9CA3AF', lineHeight: 1.5 }}>{DISCLAIMER_EN}</p>
              <p style={{ fontSize: 11, color: '#6B7280', lineHeight: 1.5, marginTop: 4 }}>{DISCLAIMER_ZH}</p>
            </div>
          )}
        </div>
      )}

      {!loading && !tcResult && tcSearched && (
        <div style={{ textAlign: 'center', padding: 32, color: '#6B7280', fontSize: 14 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🚫</div>
          No results. The Qloo API might not be configured — check that QLOO_API_KEY is set.
        </div>
      )}

      {!loading && !tcResult && !tcSearched && (
        <div style={{ textAlign: 'center', padding: 24, color: '#6B7280', fontSize: 13 }}>
          Press the button above to see Qloo find meals that match Maria's tastes, filtered by her health constraints.
        </div>
      )}
    </section>
  )
}
