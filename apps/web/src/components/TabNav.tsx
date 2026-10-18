import type { CSSProperties } from 'react'
import { TABS, FEATURED_TAB, type Tab } from './tabs'

/** Top tab navigation. discover (Taste Bridge) is the project's signature tab and gets a highlighted style. */
export function TabNav({ tab, setTab }: { tab: Tab; setTab: (t: Tab) => void }) {
  return (
    <nav style={{ display: 'flex', gap: 6, marginBottom: 24, justifyContent: 'center', flexWrap: 'wrap' }}>
      {TABS.map(([k, label, title]) => {
        const active = tab === k
        const base: CSSProperties = {
          padding: '8px 18px', borderRadius: 10, cursor: 'pointer', fontSize: 13,
          fontWeight: active ? 700 : 400,
          transition: 'background 0.15s, color 0.15s, box-shadow 0.15s',
        }
        if (k === FEATURED_TAB) {
          // Signature cross-domain tab: gradient glow so the Taste Bridge story
          // reads at a glance (feedback #10 — make cross-domain discovery pop).
          return (
            <button
              key={k}
              onClick={() => setTab(k)}
              title={title}
              style={{
                ...base,
                background: active ? 'linear-gradient(135deg, #8B5CF6, #059669)' : '#111827',
                color: active ? '#fff' : '#C77DFF',
                border: '1px solid #C77DFF66',
                boxShadow: active ? '0 3px 16px #8B5CF688' : '0 0 10px #C77DFF22',
              }}
            >
              {label}
            </button>
          )
        }
        return (
          <button
            key={k}
            onClick={() => setTab(k)}
            title={title}
            style={{
              ...base,
              background: active ? '#FF6B35' : '#1F2937',
              color: active ? '#fff' : '#9CA3AF',
              boxShadow: active ? '0 2px 8px #FF6B3533' : 'none',
              border: 'none',
            }}
          >
            {label}
          </button>
        )
      })}
    </nav>
  )
}