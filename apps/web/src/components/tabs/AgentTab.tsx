import { useState } from 'react'
import type { Dispatch, SetStateAction, RefObject } from 'react'
import { sx } from '../sx'
import { useSpeechInput } from '../../hooks/useSpeechInput'
import { QlooGroundingPanel } from '../QlooGroundingPanel'
import { QlooStatusStrip } from '../QlooStatusStrip'
import { AGENT_SCENARIO_PROMPTS } from '../../constants'
import { uniqueBy } from '../../utils/list'
import { type MemoryEntity } from '../../hooks/useTasteMemory'
import type { QlooEntityDetail } from '../../api'

type ChatItem = { id: string; role: string; text: string; tasteEntities?: string[]; tasteDataSource?: string; qlooContext?: unknown; tasteEntityDetails?: QlooEntityDetail[]; tasteRecommendations?: QlooEntityDetail[]; tasteLocation?: string; feedback?: 'up' | 'down' | null }

type PersonaOption = {
  id: string
  name: string
  taste_anchors: string
  health_constraints: string
  location: string
}

type Props = {
  chatMsg: string
  setChatMsg: (v: string) => void
  chatHistory: ChatItem[]
  setChatHistory: Dispatch<SetStateAction<ChatItem[]>>
  chatEndRef: RefObject<HTMLDivElement | null>
  doChat: () => void
  onFeedback: (messageId: string, thumb: 'up' | 'down') => void
  loading: boolean
  onOpenDiscover?: () => void
  memory?: { liked: MemoryEntity[]; clearAll: () => void }
  /** Effective persona the agent is currently grounding on (may be pinned ≠ global). */
  personaName?: string
  personaAnchor?: string
  /** All available persons (Maria + custom profiles). */
  personas?: PersonaOption[]
  /** Id of the globally selected person (from the top PersonaPicker). */
  globalPersonaId?: string
  /** Id pinning this tab to a specific person; null = follow the global one. */
  boundPersonaId?: string | null
  /** Choose a persona to bind to, or null to unbind (follow global / message-only tastes). */
  onBindPersona?: (id: string | null) => void
  /** Profile-lock mode: backend grounds ONLY on the persona's saved anchors. */
  locked?: boolean
  /** Toggle profile-lock (only meaningful when a persona is bound). */
  onToggleLocked?: () => void
}

export function AgentTab(props: Props) {
  const {
    chatMsg, setChatMsg, chatHistory, chatEndRef, doChat, onFeedback, loading, memory,
    personaName = 'Maria', personaAnchor = 'Frank Sinatra', personas = [],
    boundPersonaId = null, onBindPersona, locked = false, onToggleLocked,
  } = props
  const [personaOpen, setPersonaOpen] = useState(false)
  const {
    supported: micSupported, listening: micListening, transcribing: micTranscribing,
    engine: micEngine, error: micError, toggle: toggleMic,
  } = useSpeechInput((t) => setChatMsg(t))

  return (
    <section>
      {memory && memory.liked.length > 0 && (
        <div style={{ ...sx.card, marginBottom: 16, border: '1px solid #C77DFF44', background: '#1a1040' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: '#C77DFF' }}>Taste Memory (compounds across sessions)</h3>
            <button onClick={memory.clearAll} style={{ fontSize: 11, color: '#9CA3AF', background: 'none', border: 'none', cursor: 'pointer' }}>Clear all</button>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {uniqueBy(memory.liked, e => e.entity_id || e.name).map(e => (
              <span key={e.entity_id || `${e.name}-${e.domain || ''}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#1F2937', padding: '3px 8px', borderRadius: 8, fontSize: 11, color: '#D8B4FE', border: '1px solid #7C3AED44' }}>
                {e.name}{e.domain ? <span style={{ color: '#6B7280', fontSize: 10 }}>{e.domain}</span> : ''}
              </span>
            ))}
          </div>
          <p style={{ fontSize: 10, color: '#6B7280', marginTop: 6 }}>These anchors are prepended to all cross-domain queries so your taste profile compounds over time.</p>
        </div>
      )}
      <div style={{ ...sx.card, marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' as const, gap: 8, marginBottom: 8 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#E5E7EB' }}>Culturally Intelligent Agent</h2>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', background: '#111827', border: '1px solid #374151', padding: '4px 12px', borderRadius: 999 }}>
              ⚙️ raw capability
            </span>
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setPersonaOpen(o => !o)}
                style={{ fontSize: 11, fontWeight: 700, color: '#D8B4FE', background: '#1a1040', border: '1px solid #C77DFF55', padding: '4px 12px', borderRadius: 999, cursor: 'pointer' }}
                title="Click to change who the agent is grounded on"
              >
                {/* Single text expression, not three sibling text nodes: a persona
                    switch changes personaName ''↔'Maria', and under a translation
                    extension that re-wrapped the old text in <font>/spans React
                    would have to REMOVE those wrapped nodes to splice in the new
                    label → "removeChild: node is not a child". One expression means
                    React only writes textContent, never touches node structure. */}
                {((personaName === '' ? '🚫 No persona' : ((boundPersonaId && boundPersonaId !== 'unbound') ? '📌 Pinned: ' : '🔗 Bound to ')) + (personaName || '') + ' ▾')}
              </button>
              {/* STABLE DOM CONTRACT — the dropdown is ALWAYS mounted and toggled
                  via CSS, never mounted/unmounted. Persona switches swap several
                  subtrees (the lock button, the active ● markers) in one commit;
                  if a browser translation/labelling extension has re-wrapped any
                  of those nodes, unmounting the dropdown here fires React 19's
                  "removeChild: node is not a child" crash (same failure the
                  QlooStatusStrip comment documents). display:none costs zero
                  visual space and keeps the tree fully React-owned. */}
              <div
                style={{
                  position: 'absolute', right: 0, top: 30, width: 290, zIndex: 40,
                  background: '#0f172a', border: '1px solid #374151', borderRadius: 10,
                  boxShadow: '0 16px 40px #0009', padding: 10,
                  display: personaOpen ? 'block' : 'none',
                }}
              >
                  <div style={{ fontSize: 10, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 }}>Bind agent to</div>
                  <button
                    onClick={() => { onBindPersona?.(null); setPersonaOpen(false) }}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', padding: '7px 10px', borderRadius: 8, cursor: 'pointer', background: !boundPersonaId ? '#C77DFF22' : 'transparent', border: !boundPersonaId ? '1px solid #C77DFF66' : '1px solid transparent', color: '#E5E7EB', fontSize: 12, marginBottom: 4 }}
                  >
                    <span>🌐 Follow current person</span>
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: '#C77DFF', opacity: !boundPersonaId ? 1 : 0 }}>●</span>
                  </button>
                  {personas.length === 0 && (
                    <div style={{ fontSize: 11, color: '#6B7280', padding: '6px 10px' }}>No custom profiles yet — create one in the top Person picker.</div>
                  )}
                  {personas.map(p => {
                    const active = boundPersonaId === p.id
                    return (
                      <button
                        key={p.id}
                        onClick={() => { onBindPersona?.(p.id); setPersonaOpen(false) }}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', padding: '7px 10px', borderRadius: 8, cursor: 'pointer', background: active ? '#C77DFF22' : 'transparent', border: active ? '1px solid #C77DFF66' : '1px solid transparent', color: '#E5E7EB', fontSize: 12, marginBottom: 4 }}
                      >
                        <span>{p.name.slice(0, 1)}</span>
                        <span style={{ fontWeight: 700 }}>{p.name}</span>
                        <span style={{ marginLeft: 'auto', fontSize: 10, color: '#9CA3AF', maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.taste_anchors.split(',')[0]?.trim()}</span>
                        <span style={{ fontSize: 10, color: '#C77DFF', opacity: active ? 1 : 0 }}>●</span>
                      </button>
                    )
                  })}
                  {onBindPersona && (
                    <button
                      onClick={() => { onBindPersona('unbound'); setPersonaOpen(false) }}
                      style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', padding: '7px 10px', borderRadius: 8, cursor: 'pointer', background: boundPersonaId === 'unbound' ? '#F8717118' : 'transparent', border: boundPersonaId === 'unbound' ? '1px solid #F8717155' : '1px solid transparent', color: boundPersonaId === 'unbound' ? '#FCA5A5' : '#9CA3AF', fontSize: 12 }}
                    >
                      <span>🚫 Don't use any persona (message tastes only)</span>
                      <span style={{ marginLeft: 'auto', fontSize: 10, color: '#F87171', opacity: boundPersonaId === 'unbound' ? 1 : 0 }}>●</span>
                    </button>
                  )}
                </div>
            </div>
            {/* Profile-lock toggle: only meaningful when the agent has a persona
                (bound to a pinned person OR following the global current person).
                STABLE DOM CONTRACT — the button is ALWAYS mounted and hidden with
                display:none (a style change), so unbound/persona switches never
                REMOVE this node. Conditional unmounting here is the very subtree
                removal that, under a browser translation/labelling extension that
                has re-wrapped the DOM, throws React 19's "removeChild: node is
                not a child" error when clicking 🚫 No persona. */}
            {onToggleLocked && (
              <button
                onClick={onToggleLocked}
                title={locked
                  ? 'Profile lock ON: Qloo seeds come ONLY from the saved persona anchors'
                  : 'Profile lock OFF: the agent also explores new tastes from your question'}
                style={{
                  display: boundPersonaId === 'unbound' ? 'none' : 'inline-flex',
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '4px 12px',
                  borderRadius: 999,
                  cursor: 'pointer',
                  background: locked ? '#C77DFF' : '#111827',
                  border: locked ? '1px solid #C77DFF' : '1px solid #374151',
                  color: locked ? '#1a1040' : '#9CA3AF',
                }}
              >
                {locked ? '🔒 Locked to profile' : '🔓 Profile lock'}
              </button>
            )}
          </div>
        </div>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          Ask anything — the agent calls the <strong style={{ color: '#E5E7EB' }}>Qloo taste graph</strong> to ground every recommendation in real cultural data, not guesses.
          This is the <strong style={{ color: '#E5E7EB' }}>raw harness</strong> that powers the productized 🍽️ Senior Dining demo — same grounding, no product wrapper.
        </p>
        <p style={{ fontSize: 11, color: '#6B7280', marginTop: 6, fontStyle: 'italic' }}>
          💡 The full Why Qloo grounding panel appears under each agent reply. Try the Sinatra prompt below — it resolves cultural anchors into visible Qloo entities.
        </p>
        <div style={{ marginTop: 10, fontSize: 11, color: '#9CA3AF', lineHeight: 1.7, background: '#111827', border: '1px solid #374151', borderRadius: 10, padding: '10px 12px' }}>
          <div style={{ fontWeight: 700, color: '#D8B4FE', marginBottom: 4 }}>How your input is grounded</div>
          <div>
            {boundPersonaId === 'unbound' ? (
              <>🫧 <strong style={{ color: '#E5E7EB' }}>No persona</strong> — type your own cultural tastes in the box; ONLY what you typed is used as Qloo seeds (e.g. “Frank Sinatra, Italian food”).</>
            ) : (
              <>🔗 <strong style={{ color: '#E5E7EB' }}>Bound to {personaName}</strong> — your typed tastes are blended ON TOP of {personaName}'s saved anchors{locked ? ' (LOCKED: only the saved anchors are grounded)' : ' (mixed: message tastes are grounded too)'}.</>
            )}
          </div>
          <div style={{ marginTop: 4 }}>
            ✨ Every taste the agent resolves also feeds the <strong style={{ color: '#E5E7EB' }}>Taste Bridge</strong> (Discover tab) — bound or not, what you ask the agent shows up in the constellation.
          </div>
        </div>
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', marginBottom: 8 }}>Quick scenarios (click to ask)</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {AGENT_SCENARIO_PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => setChatMsg(p)}
                style={{ fontSize: 11, padding: '6px 12px', borderRadius: 8, background: '#1F2937', color: '#D1D5DB', border: '1px solid #374151', cursor: 'pointer', textAlign: 'left', maxWidth: 300, lineHeight: 1.4 }}
                title={p}
              >
                🤖 {i + 1}. {p.length > 44 ? p.slice(0, 44) + '…' : p}
              </button>
            ))}
          </div>
        </div>
      </div>
      <QlooStatusStrip
        loading={loading}
        matched={loading ? null : (chatHistory[chatHistory.length - 1]?.role === 'agent' ? (chatHistory[chatHistory.length - 1]?.tasteEntityDetails?.length ?? chatHistory[chatHistory.length - 1]?.tasteEntities?.length ?? null) : null)}
        detail={personaAnchor ? `anchored on “${personaAnchor}”` : undefined}
      />
      <div style={{ minHeight: 340, maxHeight: 440, overflow: 'auto', marginBottom: 16, padding: 18, borderRadius: 12, background: '#0b1020', border: '1px solid #1F2937' }}>
        {chatHistory.length === 0 && (
          <div style={{ color: '#6B7280', fontSize: 13, lineHeight: 1.8 }}>
            <p style={{ marginBottom: 8 }}>Try asking:</p>
            <p style={{ color: '#9CA3AF', fontStyle: 'italic' }}>"I love the films of Christopher Nolan and classic Chicago blues — where should I eat in New York, and what should I wear?"</p>
            <p style={{ color: '#9CA3AF', fontStyle: 'italic', marginTop: 8 }}>"My 80-year-old dad loves Frank Sinatra and Italian food but needs low-sodium meals. What restaurants near Boston would he enjoy?"</p>
          </div>
        )}
        {chatHistory.map((m, i) => (
          <div key={m.id || i} style={{ marginBottom: 12, display: 'flex', flexDirection: 'column' as const, alignItems: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <span style={{ display: 'inline-block', padding: '10px 14px', borderRadius: 12, background: m.role === 'user' ? '#3B82F633' : '#1F2937', border: m.role === 'user' ? '1px solid #3B82F644' : '1px solid #374151', fontSize: 13, maxWidth: '85%', whiteSpace: 'pre-wrap' as const, lineHeight: 1.5, color: '#E5E7EB' }}>{m.text}</span>
            {m.role === 'agent' && m.tasteEntities && m.tasteEntities.length > 0 && (
              <QlooGroundingPanel
                tasteEntities={m.tasteEntities}
                tasteDataSource={m.tasteDataSource || ''}
                qlooContext={m.qlooContext}
                tasteEntityDetails={m.tasteEntityDetails}
                tasteRecommendations={m.tasteRecommendations}
                tasteLocation={m.tasteLocation}
              />
            )}
            {m.role === 'agent' && (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 6 }}>
                {['up', 'down'].map(t => {
                  const active = m.feedback === t
                  return (
                    <button
                      key={t}
                      onClick={() => { if (!m.feedback) onFeedback(m.id, t as 'up' | 'down') }}
                      disabled={!!m.feedback}
                      title={t === 'up' ? '👍 Like this recommendation' : '👎 Dislike this recommendation'}
                      style={{
                        padding: '3px 10px', borderRadius: 8, border: active ? '1px solid #FF6B35' : '1px solid #374151',
                        cursor: m.feedback ? 'default' : 'pointer', fontSize: 12, background: active ? '#FF6B3522' : '#1F2937',
                        color: active ? '#FF6B35' : '#9CA3AF', opacity: m.feedback && !active ? 0.4 : 1,
                      }}
                    >
                      {t === 'up' ? '👍' : '👎'}
                    </button>
                  )
                })}
                {m.tasteDataSource === 'preview' && (
                  <span style={{ fontSize: 10, color: '#F5A623', opacity: 0.85 }}>⚠ Demo preview feedback (local memory only)</span>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={chatMsg} onChange={e => setChatMsg(e.target.value)} onKeyDown={e => e.key === 'Enter' && !loading && doChat()} placeholder="Ask about cultural recommendations…" style={{ ...sx.input, flex: 1 }} />
        {micSupported && (
          <button
            onClick={toggleMic}
            disabled={micTranscribing}
            title={micTranscribing ? 'Transcribing…' : (micListening ? 'Stop and transcribe' : 'Speak to the agent')}
            style={{ width: 44, border: 'none', borderRadius: 10, cursor: micTranscribing ? 'default' : 'pointer', fontSize: 18, background: micListening ? '#3B82F6' : '#1F2937', color: micListening ? '#fff' : '#E5E7EB', opacity: micTranscribing ? 0.6 : 1, transition: 'background 0.15s', flexShrink: 0 }}
          >
            {micTranscribing ? '…' : micListening ? '⏹' : '🎤'}
          </button>
        )}
        <button onClick={doChat} disabled={loading} style={{ ...sx.btnSecondary, background: '#3B82F6', color: '#fff' }}>{loading ? '…' : 'Send'}</button>
      </div>
      {micListening && <div style={{ fontSize: 11, color: '#93C5FD', marginTop: 8 }}>{micEngine === 'whisper' ? 'Listening… speak, then tap stop — transcription runs locally (no cloud).' : 'Listening… speak to the agent (en-US). Tap stop when done.'}</div>}
      {micTranscribing && <div style={{ fontSize: 11, color: '#F5A623', marginTop: 8 }}>Transcribing your voice locally…</div>}
      {micError && <div style={{ fontSize: 11, color: '#F87171', marginTop: 8 }}>{micError}</div>}
      {!micSupported && (
        <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 8 }}>
          🎤 Voice input unavailable — start the local server (`pnpm dev:server`), or type instead.
        </div>
      )}
    </section>
  )
}