import type { Dispatch, SetStateAction } from 'react'
import type { TasteCareResult } from '../../api'
import { GENERIC_LLM_RESULTS } from '../../constants'
import { sx, TasteCareCard } from '../ui'

type Props = {
  whyMode: 'qloo' | 'generic'
  setWhyMode: Dispatch<SetStateAction<'qloo' | 'generic'>>
  tcResult: TasteCareResult | null
}

export function WhyQlooTab(props: Props) {
  const { whyMode, setWhyMode, tcResult } = props

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20, textAlign: 'center', background: 'linear-gradient(135deg, #3B82F610, #111827)', border: '1px solid #3B82F633' }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: '#3B82F6', marginBottom: 8 }}>Why This Only Works With Qloo</h2>
        <p style={{ fontSize: 14, color: '#9CA3AF', lineHeight: 1.6 }}>
          A generic LLM recommends <em>"what's popular"</em>. Qloo recommends <strong style={{ color: '#E5E7EB' }}>what <em>this specific person</em> would love</strong> — because it knows the cultural taste graph connecting 250M+ entities.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, justifyContent: 'center' }}>
        <button onClick={() => setWhyMode('qloo')} style={{ padding: '8px 18px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: whyMode === 'qloo' ? 700 : 400, background: whyMode === 'qloo' ? '#3B82F6' : '#1F2937', color: whyMode === 'qloo' ? '#fff' : '#9CA3AF' }}>
          With Qloo (TasteCare)
        </button>
        <button onClick={() => setWhyMode('generic')} style={{ padding: '8px 18px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: whyMode === 'generic' ? 700 : 400, background: whyMode === 'generic' ? '#6B7280' : '#1F2937', color: whyMode === 'generic' ? '#fff' : '#9CA3AF' }}>
          Without Qloo (Generic LLM)
        </button>
      </div>

      {whyMode === 'qloo' ? (
        <div>
          <div style={{ padding: '14px 18px', borderRadius: 12, background: '#065F4622', border: '1px solid #065F4644', marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: '#6EE7B7', marginBottom: 6 }}>With Qloo: TasteCare for Maria</h3>
            <p style={{ fontSize: 13, color: '#D1D5DB', lineHeight: 1.6 }}>
              Input: <em>"Frank Sinatra, Jazz, Italian cuisine"</em> + <em>"easy-to-chew, low-sodium"</em>
            </p>
          </div>
          {tcResult && tcResult.recommendations.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tcResult.recommendations.slice(0, 6).map((r, i) => <TasteCareCard key={r.id} rec={r} rank={i + 1} activeConstraints={tcResult.active_constraints || []} />)}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ padding: '14px 18px', borderRadius: 12, background: '#065F4622', border: '1px solid #065F4644' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#6EE7B7' }}>🍚 Italian seafood risotto</div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>Cultural match: 94% · ✅ Easy to chew · ✅ Low sodium · ✅ Italian heritage</div>
              </div>
              <div style={{ padding: '14px 18px', borderRadius: 12, background: '#065F4622', border: '1px solid #065F4644' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#6EE7B7' }}>🥣 Tuscan white bean soup (ribollita)</div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>Cultural match: 91% · ✅ Soft texture · ✅ Heart-healthy · ✅ Connects to Italian roots</div>
              </div>
              <div style={{ padding: '14px 18px', borderRadius: 12, background: '#065F4622', border: '1px solid #065F4644' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#6EE7B7' }}>🎷 Jazz-age supper club — braised osso buco</div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>Cultural match: 88% · ✅ Tender braised · ✅ Sinatra-era ambiance · ✅ Low sodium option</div>
              </div>
            </div>
          )}
          <p style={{ fontSize: 12, color: '#6EE7B7', marginTop: 12, fontStyle: 'italic' }}>
            Each result is grounded in Maria's actual cultural taste via Qloo's entity graph, then filtered for her health constraints. She'd recognize these as <em>her</em> kind of food.
          </p>
        </div>
      ) : (
        <div>
          <div style={{ padding: '14px 18px', borderRadius: 12, background: '#7F1D1D22', border: '1px solid #7F1D1D44', marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: '#FCA5A5', marginBottom: 6 }}>Without Qloo: Generic "Healthy Senior Meals"</h3>
            <p style={{ fontSize: 13, color: '#D1D5DB', lineHeight: 1.6 }}>
              Input: <em>"82-year-old, low-sodium, soft food"</em> (no cultural taste data)
            </p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {GENERIC_LLM_RESULTS.map((r, i) => (
              <div key={i} style={{ padding: '14px 18px', borderRadius: 12, background: '#7F1D1D18', border: '1px solid #7F1D1D33' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#FCA5A5' }}>{r.name}</div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>❌ {r.reason}</div>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 12, color: '#FCA5A5', marginTop: 12, fontStyle: 'italic' }}>
            These are nutritionally defensible but culturally tone-deaf. Maria wouldn't recognize any of this as <em>her</em> food. She'd go back to ordering what she always ordered — and ignore the "healthy" advice entirely.
          </p>
        </div>
      )}

      <div style={{ marginTop: 24, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={{ borderRadius: 12, border: '1px solid #374151', padding: 18 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10, color: '#9CA3AF' }}>Without Qloo</h3>
          <ul style={{ fontSize: 12, color: '#9CA3AF', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8, padding: 0 }}>
            <li>❌ "Here are popular healthy meals"</li>
            <li>❌ No connection to the person's identity</li>
            <li>❌ Can't bridge film → dining → fashion</li>
            <li>❌ Same list for every senior</li>
          </ul>
        </div>
        <div style={{ borderRadius: 12, border: '1px solid #3B82F6', padding: 18, background: '#3B82F610' }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10, color: '#3B82F6' }}>With Qloo</h3>
          <ul style={{ fontSize: 12, color: '#E5E7EB', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8, padding: 0 }}>
            <li>✅ "Here's what <em>this person</em> would love"</li>
            <li>✅ Grounded in 250M+ entity taste graph</li>
            <li>✅ Cross-domain cultural bridges</li>
            <li>✅ Unique list per individual's taste</li>
          </ul>
        </div>
      </div>
    </section>
  )
}

