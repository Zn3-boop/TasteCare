import type { Dispatch, SetStateAction, RefObject } from 'react'
import { sx } from '../ui'
import { useSpeechInput } from '../../hooks/useSpeechInput'
import { QlooGroundingPanel } from '../QlooGroundingPanel'

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
}

export function AgentTab(props: Props) {
  const { chatMsg, setChatMsg, chatHistory, chatEndRef, doChat, onFeedback, loading, onOpenDiscover } = props
  const {
    supported: micSupported, listening: micListening, error: micError, toggle: toggleMic,
  } = useSpeechInput((t) => setChatMsg(t))

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#E5E7EB', marginBottom: 8 }}>Culturally Intelligent Agent</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          Ask anything — the agent calls the <strong style={{ color: '#E5E7EB' }}>Qloo taste graph</strong> to ground every recommendation in real cultural data, not guesses.
        </p>
        {onOpenDiscover && (
          <button
            onClick={onOpenDiscover}
            style={{ marginTop: 12, padding: '9px 16px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600, background: 'linear-gradient(135deg, #059669, #047857)', color: '#fff', boxShadow: '0 3px 10px #05966944' }}
          >
            🔗 Open Taste Bridge
          </button>
        )}
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