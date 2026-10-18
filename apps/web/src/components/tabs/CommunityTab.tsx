import { useState } from 'react'
import { sx } from '../sx'
import { CONSTRAINT_META, EMPTY_STATE_EXAMPLES } from '../../constants'
import type { CommunityMatch } from '../../api'
import type { useCommunity } from '../../hooks/useCommunity'

type Props = {
  community: ReturnType<typeof useCommunity>
  qlooEnabled: boolean
}

/**
 * Community tab — find people who share your cultural taste AND health needs,
 * then connect with mutual opt-in (both sides verify). Qloo does the cultural
 * matching (cloud); no LLM key or local models are needed.
 */
export function CommunityTab({ community, qlooEnabled }: Props) {
  const { likesText, setLikesText, location, setLocation, constraints, toggleConstraint, result, doMatch, doConnect, doAccept } = community
  const [pending, setPending] = useState<Record<string, string>>({})

  const handleConnect = async (m: CommunityMatch) => {
    const r = await doConnect(m.peer_id)
    if (r) setPending(prev => ({ ...prev, [m.peer_id]: r.status }))
  }

  const handleAccept = async (m: CommunityMatch) => {
    const r = await doAccept(m.peer_id)
    if (r) setPending(prev => ({ ...prev, [m.peer_id]: r.status }))
  }

  const statusFor = (m: CommunityMatch) => pending[m.peer_id] || 'none'

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #C77DFF44', background: 'linear-gradient(135deg, #C77DFF10, #111827)' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#C77DFF', marginBottom: 8 }}>👥 Community — find people who share your taste &amp; needs</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          <strong style={{ color: '#E5E7EB' }}>Cultural intelligence is the matching key:</strong> your cultural anchors are resolved through Qloo&apos;s taste graph and compared with people facing the same needs. Connecting is <strong style={{ color: '#E5E7EB' }}>mutual opt-in</strong> — a request stays pending until the other person accepts. Always verify health-related advice independently.
        </p>
        {!qlooEnabled && (
          <p style={{ fontSize: 11, color: '#F5A623', marginTop: 6 }}>
            ⚠ No QLOO_API_KEY detected — showing the clearly-labelled <strong>demo peer pool</strong> (name-level overlap). Set QLOO_API_KEY for live taste-graph matching.
          </p>
        )}
      </div>

      <div style={{ ...sx.card, marginBottom: 16 }}>
        <div style={{ marginBottom: 12 }}>
          <label style={sx.label}>Your cultural anchors (comma-separated)</label>
          <input value={likesText} onChange={e => setLikesText(e.target.value)} placeholder="Frank Sinatra, Italian cuisine, Jazz" style={sx.input} />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={sx.label}>Location (optional)</label>
          <input value={location} onChange={e => setLocation(e.target.value)} placeholder="New York" style={sx.input} />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={sx.label}>Health needs you want matched on</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {CONSTRAINT_META.map(c => {
              const active = !!constraints[c.key]
              return (
                <button
                  key={c.key}
                  onClick={() => toggleConstraint(c.key)}
                  title={c.hint}
                  style={{
                    padding: '6px 12px', borderRadius: 8, border: active ? '1px solid #C77DFF' : '1px solid #374151',
                    background: active ? '#C77DFF22' : '#1F2937', color: active ? '#D8B4FE' : '#9CA3AF',
                    fontSize: 12, cursor: 'pointer', fontWeight: active ? 700 : 400,
                  }}
                >
                  {active ? '✓ ' : ''}{c.icon} {c.label}
                </button>
              )
            })}
          </div>
        </div>
        <button onClick={doMatch} style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #C77DFF, #8B5CF6)', boxShadow: '0 4px 14px #C77DFF44' }}>
          🔍 Find People with the Same Taste &amp; Needs
        </button>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
          {EMPTY_STATE_EXAMPLES.map(ex => (
            <button key={ex} onClick={() => setLikesText(prev => prev.includes(ex) ? prev : `${prev ? prev + ', ' : ''}${ex}`)} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 8, background: '#1F2937', color: '#D1D5DB', border: '1px solid #374151', cursor: 'pointer' }}>
              + {ex}
            </button>
          ))}
        </div>
      </div>

{result && (
        <div style={sx.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: '#E5E7EB' }}>
              {result.matches.length} {result.matches.length === 1 ? 'match' : 'matches'}
            </h3>
            <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 8, background: result.data_source === 'live' ? '#065F46' : '#78350F', color: result.data_source === 'live' ? '#6EE7B7' : '#FCD34D', fontWeight: 700 }}>
              {result.data_source === 'live' ? '🟢 Qloo live taste-graph matching' : '🟠 Demo peer pool (preview)'}
            </span>
          </div>
          {result.user_likes_resolved.length > 0 && (
            <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 12 }}>
              Your anchors resolved through Qloo: {result.user_likes_resolved.map(u => u.name).join(' · ')}
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {result.matches.length === 0 && (
              <div style={{ fontSize: 12, color: '#6B7280', fontStyle: 'italic' }}>No overlapping profiles found. Try broader cultural anchors or fewer constraints.</div>
            )}
            {result.matches.map(m => {
              const st = statusFor(m)
              return (
                <div key={m.peer_id} style={{ padding: 14, borderRadius: 10, background: '#0b1020', border: '1px solid #C77DFF33' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: '#E5E7EB' }}>{m.name}</div>
                      <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>{m.tagline}{m.location ? ` · 📍 ${m.location}` : ''}</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                        {m.shared_anchors.map((a, i) => (
                          <span key={i} style={{ fontSize: 10, color: '#D8B4FE', background: '#C77DFF22', padding: '2px 8px', borderRadius: 6 }}>🎯 {a}</span>
                        ))}
                        {m.shared_constraints.map((c, i) => (
                          <span key={`c-${i}`} style={{ fontSize: 10, color: '#6EE7B7', background: '#065F4633', padding: '2px 8px', borderRadius: 6 }}>✓ {CONSTRAINT_META.find(x => x.key === c)?.label || c}</span>
                        ))}
                      </div>
                      <div style={{ fontSize: 11, color: '#6B7280', marginTop: 8 }}>
                        Likes: {m.cultural_likes.join(', ')}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: '#C77DFF' }}>{Math.round(m.affinity * 100)}%</div>
                      <div style={{ fontSize: 10, color: '#6B7280' }}>taste affinity</div>
                    </div>
                  </div>
                  <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                    {st === 'none' && (
                      <button onClick={() => handleConnect(m)} style={{ ...sx.btnSecondary, background: '#7C3AED', color: '#fff' }}>📨 Request Connection</button>
                    )}
                    {st === 'pending' && (
                      <>
                        <span style={{ fontSize: 11, color: '#F5A623', fontWeight: 700 }}>⏳ Pending — waiting for mutual acceptance</span>
                        <button onClick={() => handleAccept(m)} style={{ ...sx.btnSecondary, background: '#059669', color: '#fff' }}>✓ Simulate Peer Accept (mutual opt-in)</button>
                      </>
                    )}
                    {st === 'connected' && (
                      <span style={{ fontSize: 11, color: '#6EE7B7', fontWeight: 700 }}>✅ Connected — both sides verified</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          <p style={{ fontSize: 10, color: '#6B7280', marginTop: 14, lineHeight: 1.6 }}>
            The peer pool is a simulated demo set — in production, profiles would come from an opt-in community database.
            Always verify shared health information with your physician/pharmacist before acting on it.
          </p>
        </div>
      )}
    </section>
  )
}