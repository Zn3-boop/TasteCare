// PersonaPicker — the global "who is this demo about" control.
// 终版契约②: 顶部人物卡片（当前人物 → 切换下拉 + 新建人物四字段表单）。It only
// reads/writes the persona profile from usePersona; the tabs receive the profile
// via props from App and stay completely unaware of where it came from.
import { useState } from 'react'
import { CONSTRAINT_META, EN_CONSTRAINT_ICON } from '../constants'
import { usePersona, personaConstraintKeys, type ConstraintKey } from '../hooks/usePersona'
import { sx } from './sx'
import { uniqueBy } from '../utils/list'
import { splitTasteAnchors } from '../utils/tasteAnchors'

function Chip({ children, color = '#C77DFF' }: { children: React.ReactNode; color?: string }) {
  return (
    <span style={{ fontSize: 10.5, padding: '3px 9px', borderRadius: 999, background: `${color}18`, border: `1px solid ${color}44`, color: '#D1D5DB', fontWeight: 600 }}>
      {children}
    </span>
  )
}

export function PersonaPicker({ state }: { state: ReturnType<typeof usePersona> }) {
  const { current, all, select, create, update } = state
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  // Non-null while the edit form is open → that custom profile's fields are
  // loaded and "Save Person" calls `update()` instead of `create()`. The habit
  // anchors edited here are the single source of truth the Agent tab injects —
  // they ride `taste_anchors` into /chat/agent exactly as typed.
  const [editingId, setEditingId] = useState<string | null>(null)

  // Create-new form fields. The free-text "习惯爱好 / taste anchors" input is
  // REQUIRED for the Agent tab to ground on THIS person (single source of truth
  // with Tastes/Discover). A person created without anchors still works — the
  // Taste Bridge centers on their NAME (see App) — but asking the agent a
  // domain-only question ("which place do you advise me to travel") would fall
  // back to the fixed core anchors instead of this person's tastes.
  const [name, setName] = useState('')
  const [anchors, setAnchors] = useState('')
  const [constraints, setConstraints] = useState<ConstraintKey[]>([])
  const [location, setLocation] = useState('')

  const toggleConstraint = (k: ConstraintKey) => {
    setConstraints(prev => (prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k]))
  }

  // Pre-fill the form from an existing profile so it can be edited in
  // place (habit anchors too — editing them here is what feeds the Agent tab).
  // Every persona is editable: custom profiles update in place, the built-in
  // Maria saves to her dedicated override slot in usePersona.
  const startEdit = (p: ReturnType<typeof usePersona>['all'][number]) => {
    setCreating(false)
    setEditingId(p.id)
    setName(p.name)
    setAnchors(p.taste_anchors)
    setConstraints(personaConstraintKeys(p))
    setLocation(p.location)
  }

  const submit = () => {
    if (editingId) {
      // Edit-in-place path: update() normalizes taste_anchors (dedupe + cap) so
      // repeated edits settle idempotently and cannot grow the profile blob.
      update(editingId, {
        taste_anchors: anchors.trim(),
        health_constraints: constraints.join(', '),
        location,
      })
    } else {
      create({
        name,
        // The create form now collects habits again: these anchors ride the
        // persona profile into /chat/agent so the Agent tab grounds on the bound
        // person's own tastes (persona-first seed priority on the backend).
        taste_anchors: anchors.trim(),
        health_constraints: constraints.join(', '),
        location,
      })
    }
    setCreating(false)
    setEditingId(null)
    setOpen(false)
    setName(''); setAnchors(''); setConstraints([]); setLocation('')
  }
return (
    <div style={{ ...sx.card, marginBottom: 20, padding: 14, display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap', border: '1px solid #C77DFF33' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 38, height: 38, borderRadius: 50, background: 'linear-gradient(135deg, #FF6B35, #C77DFF)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, color: '#fff', fontWeight: 800 }}>
          {current.name.slice(0, 1)}
        </div>
        <div>
          <div style={{ fontSize: 10, letterSpacing: 2, textTransform: 'uppercase', color: '#6B7280', fontWeight: 700 }}>Current Person</div>
          <div style={{ fontSize: 16, fontWeight: 800, color: '#E5E7EB' }}>
            {current.name}
            <span style={{ fontSize: 11, fontWeight: 500, color: '#9CA3AF', marginLeft: 8 }}>📍 {current.location || 'no location set'}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center', flex: 1 }}>
        {uniqueBy(splitTasteAnchors(current.taste_anchors), a => a.toLowerCase()).slice(0, 3).map((a, i) => (
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
              <div
                key={p.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, width: '100%', padding: '6px 8px', borderRadius: 8,
                  background: p.id === current.id ? '#C77DFF22' : 'transparent', border: p.id === current.id ? '1px solid #C77DFF66' : '1px solid transparent', color: '#E5E7EB', fontSize: 13, marginBottom: 4,
                }}
              >
                <button
                  onClick={() => { select(p.id); setOpen(false) }}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, textAlign: 'left', background: 'none', border: 'none', color: 'inherit', fontSize: 13, cursor: 'pointer', padding: 0 }}
                >
                  <span>{p.name.slice(0, 1)}</span>
                  <span style={{ fontWeight: 700 }}>{p.name}</span>
                  {p.id === current.id && <span style={{ marginLeft: 'auto', fontSize: 10, color: '#C77DFF' }}>● current</span>}
                </button>
                {/* Edit works for EVERY persona — custom profiles AND the
                    built-in Maria. Maria's changes save to her own override
                    slot (the preset stays pristine), so profiles never
                    cross-pollinate. 'unbound' has no profile to edit. */}
                {p.id !== 'unbound' && (
                  <button
                    onClick={() => startEdit(p)}
                    title={`Edit ${p.name}'s profile (habits, location, health)`}
                    style={{ fontSize: 11, color: '#C77DFF', background: 'none', border: '1px solid #C77DFF44', borderRadius: 6, padding: '2px 7px', cursor: 'pointer' }}
                  >
                    ✏️ Edit
                  </button>
                )}
              </div>
            ))}

            {!creating && !editingId ? (
              <button onClick={() => { setCreating(true); setName(''); setAnchors(''); setConstraints([]); setLocation('') }} style={{ ...sx.btnSecondary, width: '100%', marginTop: 6, border: '1px dashed #C77DFF66', color: '#C77DFF' }}>
                ➕ Create New Person
              </button>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10, borderTop: '1px solid #1F2937', paddingTop: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: editingId ? '#D8B4FE' : '#9CA3AF', letterSpacing: 0.4 }}>
                  {editingId ? `✏️ Editing "${name}" — habits below are what the Agent injects` : '➕ New person'}
                </div>
                <input
                  placeholder="Name"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  disabled={!!editingId}
                  style={{ ...sx.input, opacity: editingId ? 0.6 : 1 }}
                />
                <input
                  placeholder="Taste anchors (e.g. Frank Sinatra, Jazz, Italian cuisine)"
                  value={anchors}
                  onChange={e => setAnchors(e.target.value)}
                  style={sx.input}
                />
                <input placeholder="Location (e.g. Chicago)" value={location} onChange={e => setLocation(e.target.value)} style={sx.input} />
                <div>
                  <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 700, marginBottom: 4 }}>Health constraints</div>
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
                  <button onClick={submit} style={{ ...sx.btnPrimary, flex: 1, padding: '8px 12px', fontSize: 12 }}>{editingId ? 'Save Changes' : 'Save Person'}</button>
                  <button onClick={() => { setCreating(false); setEditingId(null) }} style={{ ...sx.btnSecondary, flex: 1, padding: '8px 12px', fontSize: 12 }}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}