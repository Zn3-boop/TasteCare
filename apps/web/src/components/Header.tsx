import type { QlooStatus } from '../hooks/useQlooStatus'

/** 品牌区 + Qloo 连接状态徽标。 */
export function Header({ status }: { status: QlooStatus | null }) {
  return (
    <header style={{ textAlign: 'center', marginBottom: 28 }}>
      <div style={{ fontSize: 11, color: '#F5A623', letterSpacing: 3, textTransform: 'uppercase', fontWeight: 600 }}>Qloo × LLM Hackathon</div>
      <h1 style={{ fontSize: 32, fontWeight: 800, margin: '8px 0 4px', background: 'linear-gradient(135deg, #FF6B35, #F5A623)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
        TasteCare
      </h1>
      <p style={{ fontSize: 15, color: '#9CA3AF', maxWidth: 600, margin: '0 auto', lineHeight: 1.6 }}>
        Culturally intelligent dining for seniors.<br />
        <strong style={{ color: '#E5E7EB' }}>Not "what's healthy" — what <em>this person</em> would actually love</strong>, filtered for their health reality.
      </p>
      <div style={{ marginTop: 12, display: 'flex', gap: 8, justifyContent: 'center', alignItems: 'center' }}>
        <span style={{ fontSize: 11, padding: '4px 12px', borderRadius: 8, background: status?.enabled ? '#065F46' : '#374151', color: status?.enabled ? '#6EE7B7' : '#9CA3AF', fontWeight: 600 }}>
          {status?.enabled ? '✅ Qloo Taste Graph Connected' : '🔌 Qloo Not Configured'}
        </span>
        <span style={{ fontSize: 10, color: '#6B7280' }}>250M+ entities</span>
      </div>
    </header>
  )
}
