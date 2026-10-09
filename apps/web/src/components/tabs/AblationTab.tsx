import { useState } from 'react'
import type { AblationComparisonResponse } from '../../api'
import { fetchAblationComparison } from '../../api'
import { sx } from '../sx'

function RationaleCard({ item, tone }: { item: { name?: string; cultural_match?: string; safety_validation?: string; passes?: boolean }; tone: 'a' | 'b' }) {
  const col = tone === 'a' ? '#F87171' : '#6EE7B7'
  const bg = tone === 'a' ? '#7F1D1D22' : '#065F4622'
  return (
    <div style={{ padding: '12px 14px', borderRadius: 10, background: bg, border: `1px solid ${col}33`, marginBottom: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#E5E7EB', marginBottom: 6 }}>{item.name}</div>
      <div style={{ fontSize: 11.5, color: '#D1D5DB', lineHeight: 1.5 }}>
        <span style={{ fontWeight: 700, color: col }}>Cultural match:</span> {item.cultural_match || '—'}
      </div>
      <div style={{ fontSize: 11.5, color: '#D1D5DB', lineHeight: 1.5, marginTop: 4 }}>
        <span style={{ fontWeight: 700, color: col }}>Safety:</span> {item.safety_validation || '—'}
      </div>
    </div>
  )
}

export function AblationTab() {
  const [data, setData] = useState<AblationComparisonResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const run = async () => {
    setLoading(true); setError('')
    try {
      const res = await fetchAblationComparison()
      setData(res)
    } catch (e) {
      setError(String(e)); setData(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20, textAlign: 'center', background: 'linear-gradient(135deg, #7C2D1210, #111827)', border: '1px solid #B4530944' }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: '#F59E0B', marginBottom: 8 }}>Ablation Comparison</h2>
        <p style={{ fontSize: 14, color: '#9CA3AF', lineHeight: 1.6 }}>
          Side-by-side: <strong style={{ color: '#FCA5A5' }}>Variant A</strong> (pure LLM + health rules, <em>no Qloo</em>) vs{' '}
          <strong style={{ color: '#6EE7B7' }}>Variant B</strong> (LLM + Qloo taste graph + health rules). See the difference cultural grounding makes.
        </p>
        {data && data.data_source === 'preview' && (
          <p style={{ fontSize: 11, color: '#FCD34D', marginTop: 6, fontStyle: 'italic' }}>
            Demo preview data (QLOO_API_KEY not set) — clearly labelled, not live Qloo output.
          </p>
        )}
      </div>

      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <button onClick={() => void run()} disabled={loading} style={{ ...sx.btnPrimary, background: 'linear-gradient(135deg, #B45309, #92400E)', boxShadow: '0 4px 14px #B4530944', opacity: loading ? 0.6 : 1 }}>
          {loading ? 'Running ablation…' : '▶ Run Ablation Comparison'}
        </button>
      </div>

      {error && <div style={{ color: '#F87171', fontSize: 12, marginBottom: 12, textAlign: 'center' }}>{error}</div>}

      {!data && !loading && (
        <div style={{ textAlign: 'center', padding: 24, color: '#6B7280', fontSize: 13 }}>
          Press the button above to run the paired Variant A / Variant B comparison on the same senior-dining prompts.
        </div>
      )}

      {data && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {data.comparison.map((row, i) => (
            <div key={i} style={{ ...sx.card }}>
              <div style={{ fontSize: 13, color: '#9CA3AF', marginBottom: 14, lineHeight: 1.5, fontStyle: 'italic' }}>
                Prompt {i + 1}: “{row.case.query}”
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div style={{ borderRadius: 12, border: '1px solid #7F1D1D44', background: '#111827', padding: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 700, color: '#FCA5A5' }}>Variant A — No Qloo</h3>
                    <span style={{ fontSize: 11, color: '#9CA3AF' }}>Top: {row.variant_a.top_pick || '—'}</span>
                  </div>
                  <div style={{ fontSize: 11, color: '#FCA5A5', marginBottom: 10 }}>{row.variant_a.has_cultural_match ? '✓ cultural match' : '✗ no cultural match'}</div>
                  {(row.variant_a.rationale || []).map((r, j) => <RationaleCard key={j} item={r} tone="a" />)}
                  {(row.variant_a.rationale || []).length === 0 && <div style={{ color: '#6B7280', fontSize: 12 }}>No recommendations.</div>}
                </div>
                <div style={{ borderRadius: 12, border: '1px solid #065F4644', background: '#0D1F17', padding: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 700, color: '#6EE7B7' }}>Variant B — With Qloo</h3>
                    <span style={{ fontSize: 11, color: '#9CA3AF' }}>Top: {row.variant_b.top_pick || '—'}</span>
                  </div>
                  <div style={{ fontSize: 11, color: '#6EE7B7', marginBottom: 10 }}>{row.variant_b.has_cultural_match ? '✓ cultural match (Qloo-grounded)' : '✗ no cultural match'}</div>
                  {(row.variant_b.rationale || []).map((r, j) => <RationaleCard key={j} item={r} tone="b" />)}
                  {(row.variant_b.rationale || []).length === 0 && <div style={{ color: '#6B7280', fontSize: 12 }}>No recommendations.</div>}
                </div>
              </div>
            </div>
          ))}
          {data.comparison.length === 0 && (
            <div style={{ textAlign: 'center', padding: 24, color: '#6B7280', fontSize: 13 }}>No comparison rows returned.</div>
          )}
        </div>
      )}
    </section>
  )
}