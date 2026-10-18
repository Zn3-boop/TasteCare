import type { QlooStatus } from '../hooks/useQlooStatus'
import { useState } from 'react'

function statusConfig(s: QlooStatus | null) {
  if (!s) return { dot: '⚪', label: 'Checking…', bg: '#374151', fg: '#9CA3AF', border: '#374151' }
  if (s.enabled) return { dot: '🟢', label: 'Live', bg: '#065F46', fg: '#6EE7B7', border: '#065F46' }
  if (s.api_key_set) return { dot: '🟡', label: 'Preview', bg: '#78350F', fg: '#FCD34D', border: '#78350F' }
  return { dot: '🔴', label: 'Not configured', bg: '#7F1D1D', fg: '#FCA5A5', border: '#7F1D1D' }
}

function buildShareUrl() {
  const params = new URLSearchParams({
    likes: 'Italian cuisine, Jazz, Frank Sinatra',
    location: 'New York',
    soft_chewable: 'true',
    low_sodium: 'true',
    low_sugar: 'false',
    medications: 'false',
  })
  return `${window.location.origin}${window.location.pathname}?${params.toString()}`
}

/** Brand header with persistent live/preview/broken status badge and a Share button. */
export function Header({ status }: { status: QlooStatus | null }) {
  const cfg = statusConfig(status)
  const [copied, setCopied] = useState(false)

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(buildShareUrl())
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* fallback: do nothing */ }
  }

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
        <span style={{ fontSize: 11, padding: '4px 12px', borderRadius: 8, background: cfg.bg, color: cfg.fg, border: `1px solid ${cfg.border}`, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6, boxShadow: '0 0 8px ' + cfg.bg }}>
          <span style={{ fontSize: 13 }}>{cfg.dot}</span>
          {cfg.label}
          {status?.base_url && <span style={{ opacity: 0.6, fontWeight: 400, fontFamily: 'monospace', fontSize: 10 }}>{new URL(status.base_url).hostname}</span>}
        </span>
        <span style={{ fontSize: 10, color: '#6B7280' }}>250M+ entities</span>
        <button onClick={handleShare} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 8, background: '#1F2937', color: copied ? '#6EE7B7' : '#9CA3AF', border: '1px solid #374151', cursor: 'pointer', fontWeight: 600, transition: 'all 0.2s' }}>
          {copied ? '✓ Copied!' : '🔗 Share this demo'}
        </button>
      </div>
    </header>
  )
}
