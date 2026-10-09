import { TABS, type Tab } from './tabs'

/** 顶部 tab 导航。 */
export function TabNav({ tab, setTab }: { tab: Tab; setTab: (t: Tab) => void }) {
  return (
    <nav style={{ display: 'flex', gap: 6, marginBottom: 24, justifyContent: 'center', flexWrap: 'wrap' }}>
      {TABS.map(([k, label, title]) => (
        <button
          key={k}
          onClick={() => setTab(k)}
          title={title}
          style={{
            padding: '8px 18px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 13,
            fontWeight: tab === k ? 700 : 400, background: tab === k ? '#FF6B35' : '#1F2937',
            color: tab === k ? '#fff' : '#9CA3AF', transition: 'background 0.15s, color 0.15s',
            boxShadow: tab === k ? '0 2px 8px #FF6B3533' : 'none',
          }}
        >
          {label}
        </button>
      ))}
    </nav>
  )
}
