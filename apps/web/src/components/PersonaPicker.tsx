// PersonaPicker — the global "who is this demo about" control.
// 终版契约②: 顶部人物卡片（当前人物 → 切换下拉 + 新建人物四字段表单）。It only
// reads/writes the persona profile from usePersona; the tabs receive the profile
// via props from App and stay completely unaware of where it came from.
import { useState } from 'react'
import { CONSTRAINT_META, EN_CONSTRAINT_ICON } from '../constants'
import { usePersona, type ConstraintKey } from '../hooks/usePersona'
import { sx } from './sx'
import { uniqueBy } from '../utils/list'

function Chip({ children, color = '#C77DFF' }: { children: React.ReactNode; color?: string }) {
  return (
    <span style={{ fontSize: 10.5, padding: '3px 9px', borderRadius: 999, background: `${color}18`, border: `1px solid ${color}44`, color: '#D1D5DB', fontWeight: 600 }}>
      {children}
    </span>
  )
}

export function PersonaPicker({ state }: { state: ReturnType<typeof usePersona> }) {
  const { current, all, select, create } = state
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)

  // Create-new form fields. NOTE: the free-text "习惯爱好 / anchors" input was
  // removed — a person no longer types anchors at creation time. The Taste
  // Bridge anchors a new (anchorless) person on their NAME instead (see App),
  // so free-text hobbies that could never resolve to Qloo entities no longer
  // produce an empty bridge.
  const [name, setName] = useState('')
  const [constraints, setConstraints] = useState<ConstraintKey[]>([])
  const [location, setLocation] = useState('')

  const toggleConstraint = (k: ConstraintKey) => {
    setConstraints(prev => (prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k]))
  }

  const submit = () => {
    create({
      name,
      // 新建人物不再填写锚点：taste_anchors 留空，App 侧会用人物名作为味觉桥
      // 中心锚点（见 App.tsx persona-watch effect 的 anchorsText 兜底）。
      taste_anchors: '',
      health_constraints: constraints.join(', '),
      location,
    })
    setCreating(false)
    setOpen(false)
    setName(''); setConstraints([]); setLocation('')
  }
return (
    <div style={{ ...sx.card, marginBottom: 20, padding: 14, display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap', border: '1px solid #C77DFF33' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 38, height: 38, borderRadius: 50, background: 'linear-gradient(135deg, #FF6B35, #C77DFF)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, color: '#fff', fontWeight: 800 }}>
          {current.name.slice(0, 1)}
        </div>
        <div>
          <div style={{ fontSize: 10, letterSpacing: 2, textTransform: 'uppercase', color: '#6B7280', fontWeight: 700 }}>当前人物 · Current Person</div>
          <div style={{ fontSize: 16, fontWeight: 800, color: '#E5E7EB' }}>
            {current.name}
            <span style={{ fontSize: 11, fontWeight: 500, color: '#9CA3AF', marginLeft: 8 }}>📍 {current.location || 'no location set'}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center', flex: 1 }}>
        {uniqueBy(current.taste_anchors.split(/[,，\n]/).map(a => a.trim()).filter(Boolean), a => a.toLowerCase()).slice(0, 3).map((a, i) => (
          <Chip key={`${a.toLowerCase()}-${i}`}>{a}</Chip>
        ))}
        <Chip color="#6EE7B7">🩺 {current.health_constraints || 'no constraints'}</Chip>
      </div>

      <div style={{ position: 'relative' }}>
        <button onClick={() => setOpen(o => !o)} style={{ ...sx.btnSecondary, border: '1px solid #374151' }}>
          {open ? '▴ Close' : '▾ Switch Person / ➕ Create New'}
        </button>
        {open && (
          <div style={{ position: 'absolute', right: 0, top: 44, width: 300, zIndex: 30, ...sx.card, border: '1px solid #374151', boxShadow: '0 16px 40px #0009' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#9CA3AF', marginBottom: 8, letterSpacing: 0.5, textTransform: 'uppercase' }}>Profiles</div>
            {all.map(p => (
              <button
                key={p.id}
                onClick={() => { select(p.id); setOpen(false) }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                  background: p.id === current.id ? '#C77DFF22' : 'transparent', border: p.id === current.id ? '1px solid #C77DFF66' : '1px solid transparent', color: '#E5E7EB', fontSize: 13, marginBottom: 4,
                }}
              >
                <span>{p.name.slice(0, 1)}</span>
                <span style={{ fontWeight: 700 }}>{p.name}</span>
                {p.id === current.id && <span style={{ marginLeft: 'auto', fontSize: 10, color: '#C77DFF' }}>● current</span>}
              </button>
            ))}

            {!creating ? (
              <button onClick={() => { setCreating(true) }} style={{ ...sx.btnSecondary, width: '100%', marginTop: 6, border: '1px dashed #C77DFF66', color: '#C77DFF' }}>
                ➕ Create New Person
              </button>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10, borderTop: '1px solid #1F2937', paddingTop: 10 }}>
                <input placeholder="名字 · Name" value={name} onChange={e => setName(e.target.value)} style={sx.input} />
                <input placeholder="所在城市 · Location (e.g. Chicago)" value={location} onChange={e => setLocation(e.target.value)} style={sx.input} />
                <div>
                  <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 700, marginBottom: 4 }}>健康约束 · Health constraints</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {CONSTRAINT_META.map(c => {
                      const active = constraints.includes(c.key as ConstraintKey)
                      return (
                        <button
                          key={c.key}
                          onClick={() => toggleConstraint(c.key as ConstraintKey)}
                          title={c.hint}
                          style={{
                            fontSize: 10.5, padding: '3px 8px', borderRadius: 999, cursor: 'pointer', fontWeight: 700,
                            background: active ? '#065F46' : '#1F2937', color: active ? '#6EE7B7' : '#9CA3AF', border: active ? '1px solid #6EE7B755' : '1px solid #374151',
                          }}
                        >
                          {EN_CONSTRAINT_ICON[c.key] || ''} {c.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={submit} style={{ ...sx.btnPrimary, flex: 1, padding: '8px 12px', fontSize: 12 }}>Save Person</button>
                  <button onClick={() => setCreating(false)} style={{ ...sx.btnSecondary, flex: 1, padding: '8px 12px', fontSize: 12 }}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}