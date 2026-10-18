import type { Dispatch, SetStateAction, RefObject } from 'react'
import { sx } from '../sx'
import { useSpeechInput } from '../../hooks/useSpeechInput'
import { QlooGroundingPanel } from '../QlooGroundingPanel'
import { AGENT_SCENARIO_PROMPTS } from '../../constants'
import { type MemoryEntity } from '../../hooks/useTasteMemory'

type ChatItem = { id: string; role: string; text: string; tasteEntities?: string[]; tasteDataSource?: string; qlooContext?: unknown; feedback?: 'up' | 'down' | null }

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
}

export function AgentTab(props: Props) {
  const { chatMsg, setChatMsg, chatHistory, chatEndRef, doChat, onFeedback, loading, onOpenDiscover, memory } = props
  const {
    supported: micSupported, listening: micListening, error: micError, toggle: toggleMic,
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
            {memory.liked.map(e => (
              <span key={e.entity_id} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#1F2937', padding: '3px 8px', borderRadius: 8, fontSize: 11, color: '#D8B4FE', border: '1px solid #7C3AED44' }}>
                {e.name}{e.domain ? <span style={{ color: '#6B7280', fontSize: 10 }}>{e.domain}</span> : ''}
              </span>
            ))}
          </div>
          <p style={{ fontSize: 10, color: '#6B7280', marginTop: 6 }}>These anchors are prepended to all cross-domain queries so your taste profile compounds over time.</p>
        </div>
      )}
      <div style={{ ...sx.card, marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#E5E7EB', marginBottom: 8 }}>Culturally Intelligent Agent</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          Ask anything — the agent calls the <strong style={{ color: '#E5E7EB' }}>Qloo taste graph</strong> to ground every recommendation in real cultural data, not guesses.
        </p>
        <p style={{ fontSize: 11, color: '#6B7280', marginTop: 6, fontStyle: 'italic' }}>
          💡 The full Grounding evidence panel appears under each agent reply. Try the Sinatra prompt below — it resolves cultural anchors into visible Qloo entities.
        </p>
        {onOpenDiscover && (
          <button
            onClick={onOpenDiscover}
            style={{ marginTop: 12, padding: '9px 16px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600, background: 'linear-gradient(135deg, #059669, #047857)', color: '#fff', boxShadow: '0 3px 10px #05966944' }}
          >
            🔗 Open Taste Bridge
          </button>
        )}
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
      <div style={{ minHeight: 340, maxHeight: 440, overflow: 'auto', marginBottom: 16, padding: 18, borderRadius: 12, background: '#0b1020', border: '1px solid #1F2937' }}>
        {chatHistory.length === 0 && (
          <div style={{ color: '#6B7280', fontSize: 13, lineHeight: 1.8 }}>
            <p style={{ marginBottom: 8 }}>Try asking:</p>
            <p style={{ color: '#9CA3AF', fontStyle: 'italic' }}>"I love the films of Christopher Nolan and classic Chicago blues — where should I eat in New York, and what should I wear?"</p>
            <p style={{ color: '#9CA3AF', fontStyle: 'italic', marginTop: 8 }}>"My 80-year-old dad loves Frank Sinatra and Italian food but needs low-sodium meals. What restaurants near Boston would he enjoy?"</p>
          </div>
        )}
        {chatHistory.map((m, i) => (
          <div key={i} style={{ marginBottom: 12, display: 'flex', flexDirection: 'column' as const, alignItems: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <span style={{ display: 'inline-block', padding: '10px 14px', borderRadius: 12, background: m.role === 'user' ? '#3B82F633' : '#1F2937', border: m.role === 'user' ? '1px solid #3B82F644' : '1px solid #374151', fontSize: 13, maxWidth: '85%', whiteSpace: 'pre-wrap' as const, lineHeight: 1.5, color: '#E5E7EB' }}>{m.text}</span>
            {m.role === 'agent' && m.tasteEntities && m.tasteEntities.length > 0 && (
              <QlooGroundingPanel
                tasteEntities={m.tasteEntities}
                tasteDataSource={m.tasteDataSource || ''}
                qlooContext={m.qlooContext}
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
            title={micListening ? 'Stop listening' : 'Speak to the agent'}
            style={{ width: 44, border: 'none', borderRadius: 10, cursor: 'pointer', fontSize: 18, background: micListening ? '#3B82F6' : '#1F2937', color: micListening ? '#fff' : '#E5E7EB', transition: 'background 0.15s', flexShrink: 0 }}
          >
            {micListening ? '⏹' : '🎤'}
          </button>
        )}
        <button onClick={doChat} disabled={loading} style={{ ...sx.btnSecondary, background: '#3B82F6', color: '#fff' }}>{loading ? '…' : 'Send'}</button>
      </div>
      {micListening && <div style={{ fontSize: 11, color: '#93C5FD', marginTop: 8 }}>Listening… speak to the agent (en-US). Tap stop when done.</div>}
      {micError && <div style={{ fontSize: 11, color: '#F87171', marginTop: 8 }}>Speech unavailable: {micError}</div>}
    </section>
  )
}