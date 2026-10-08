import { useState } from 'react'
import { useTasteCare, type TasteCareResult } from '../hooks/useTasteCare'

const CARD_STYLE: React.CSSProperties = {
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: '10px',
  padding: '14px 16px',
  marginBottom: '12px',
}

const INPUT_STYLE: React.CSSProperties = {
  background: '#0b1020',
  color: '#e2e8f0',
  border: '1px solid #334155',
  borderRadius: '8px',
  padding: '8px 10px',
  fontSize: '14px',
  width: '100%',
  boxSizing: 'border-box',
}

export default function TasteCarePanel() {
  const { status, loading, error, recommend } = useTasteCare()
  const [likes, setLikes] = useState('Frank Sinatra, 罗马假日')
  const [location, setLocation] = useState('New York')
  const [lowSugar, setLowSugar] = useState(true)
  const [lowSodium, setLowSodium] = useState(true)
  const [soft, setSoft] = useState(true)
  const [medications, setMedications] = useState('血压药')
  const [result, setResult] = useState<TasteCareResult | null>(null)

  const constraints: Record<string, unknown> = {
    low_sugar: lowSugar,
    low_sodium: lowSodium,
    soft_chewable: soft,
  }
  if (medications.trim()) {
    constraints.medications = [medications.trim()]
  }

  const onRecommend = async () => {
    const res = await recommend({
      cultural_likes: likes.split(',').map(s => s.trim()).filter(Boolean),
      location: location.trim() || undefined,
      constraints,
      take: 10,
    })
    setResult(res)
  }

  return (
    <div style={{ padding: '20px', maxWidth: '820px', margin: '0 auto', color: '#e2e8f0' }}>
      <h2 style={{ margin: '0 0 4px', color: '#f8fafc', fontSize: '20px' }}>🍽️ TasteCare 老年友好餐饮</h2>
      <p style={{ margin: '0 0 16px', color: '#94a3b8', fontSize: '13px' }}>
        基于 Qloo 口味图谱，把老人的文化偏好（菜系 / 艺术家 / 电影）映射到餐厅，再做低糖·低盐·软食健康约束。
      </p>

      <div style={{ ...CARD_STYLE, padding: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: '#cbd5e1' }}>
              文化偏好（逗号分隔）
            </label>
            <input value={likes} onChange={e => setLikes(e.target.value)} placeholder="如：邓丽君、罗马假日、粤菜" style={INPUT_STYLE} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: '#cbd5e1' }}>地区</label>
            <input value={location} onChange={e => setLocation(e.target.value)} placeholder="如：New York" style={INPUT_STYLE} />
          </div>
        </div>

        <div style={{ display: 'flex', gap: '18px', margin: '14px 0 4px', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#cbd5e1' }}>
            <input type="checkbox" checked={lowSugar} onChange={e => setLowSugar(e.target.checked)} /> 低糖
          </label>
          <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#cbd5e1' }}>
            <input type="checkbox" checked={lowSodium} onChange={e => setLowSodium(e.target.checked)} /> 低盐
          </label>
          <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#cbd5e1' }}>
            <input type="checkbox" checked={soft} onChange={e => setSoft(e.target.checked)} /> 软食易咀嚼
          </label>
        </div>

        <div style={{ marginTop: '12px' }}>
          <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: '#cbd5e1' }}>
            正在用药（仅做风险提示，不提供医疗建议）
          </label>
          <input value={medications} onChange={e => setMedications(e.target.value)} placeholder="如：血压药 / 抗凝药" style={INPUT_STYLE} />
        </div>

        <button
          onClick={onRecommend}
          disabled={loading}
          style={{
            marginTop: '16px',
            width: '100%',
            padding: '11px',
            background: loading ? '#1e293b' : '#3b82f6',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontSize: '15px',
            fontWeight: 600,
            cursor: loading ? 'default' : 'pointer',
          }}
        >
          {loading ? '正在查询 Qloo 口味图谱…' : '推荐适合我的餐厅'}
        </button>
      </div>

      {status && (
        <div style={{ ...CARD_STYLE, background: '#0b1020', fontSize: '13px', color: status.enabled ? '#4ade80' : '#f87171' }}>
          Qloo 集成：{status.enabled ? `已启用（${status.base_url}）` : status.api_key_set ? '已配置 key' : '未配置 key（请在 apps/server/.env 设置 QLOO_API_KEY）'}
        </div>
      )}

      {error && <div style={{ ...CARD_STYLE, background: '#7f1d1d22', color: '#f87171', fontSize: '13px' }}>⚠️ {error}</div>}

      {result && (
        <div style={{ marginTop: '4px' }}>
          {result.explanation && (
            <div style={{ ...CARD_STYLE, background: '#0b1020', fontSize: '14px', lineHeight: 1.7 }}>
              <strong style={{ color: '#93c5fd' }}>🧠 推荐说明：</strong>
              <span>{result.explanation}</span>
            </div>
          )}
          {result.recommendations.map((r, i) => {
            const health = r.health || { passes: false, labels: [], warnings: [] }
            const labels = (health.labels || []).join('、')
            const warns = health.warnings || []
            return (
              <div key={r.id || i} style={CARD_STYLE}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '15px', fontWeight: 600, color: '#f8fafc' }}>{r.name}</span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: '10px',
                      background: health.passes ? '#14532d' : '#7f1d1d',
                      color: '#fff',
                    }}
                  >
                    {health.passes ? '健康匹配' : '需确认'}
                  </span>
                </div>
                {(r.tags && r.tags.length > 0) && (
                  <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {r.tags.slice(0, 6).map(t => (
                      <span key={t} style={{ background: '#1e293b', color: '#cbd5e1', borderRadius: '6px', padding: '2px 8px', fontSize: '12px' }}>{t}</span>
                    ))}
                  </div>
                )}
                {labels && <div style={{ marginTop: '8px', fontSize: '13px', color: '#4ade80' }}>✓ {labels}</div>}
                {warns.length > 0 && (
                  <div style={{ marginTop: '6px', fontSize: '13px', color: '#fbbf24' }}>
                    ⚠️ {warns.join('；')}
                  </div>
                )}
                {typeof r.popularity === 'number' && (
                  <div style={{ marginTop: '6px', fontSize: '12px', color: '#64748b' }}>人气评分：{r.popularity.toFixed(2)}</div>
                )}
              </div>
            )
          })}
          {result.disclaimer && (
            <div style={{ ...CARD_STYLE, background: '#0b1020', fontSize: '12px', color: '#94a3b8', lineHeight: 1.6 }}>
              {result.disclaimer}
            </div>
          )}
        </div>
      )}
    </div>
  )
}