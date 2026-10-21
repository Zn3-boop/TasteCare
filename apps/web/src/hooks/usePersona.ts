// Global persona binding — the ONE source of "who is this demo about".
//
// 终版契约②: 一个人物贯穿全应用（Maria 预置 + 自定义人物）。The state is a small
// JSON profile hydrated from / persisted to localStorage under
// `tastecare.persona.v1` so a page refresh KEEPS the selected person (and any
// custom profiles the judge created) instead of silently resetting to Maria.
// The rest of the app (Senior Dining, Taste Bridge, Agent, Tastes) reads this
// profile via props only and treats it as the shared persona: taste anchors,
// health constraints and default location all come from here.
import { useEffect, useState } from 'react'

export type ConstraintKey = 'soft_chewable' | 'low_sodium' | 'low_sugar' | 'medications'

export interface Persona {
  /** Stable id so the picker can key the built-in profile separately from custom ones. */
  id: string
  name: string
  /** Free-text taste anchors (cuisines / artists / films …), one line of text. */
  taste_anchors: string
  /** Human-readable health context shown beside the persona card. */
  health_constraints: string
  /** Default / home location used by all tabs (e.g. "New York"). */
  location: string
}

/** The built-in Maria profile — the demo's default person. */
export const MARIA_PERSONA: Persona = {
  id: 'maria',
  name: 'Maria',
  taste_anchors: 'Frank Sinatra, Jazz, Italian cuisine, Classic Hollywood films',
  health_constraints: 'low_sodium, low_sugar, soft_chewable, medications',
  location: 'New York',
}

/** Parse the built-in comma-list style constraints into booleans (for the tabs that consume them). */
export function personaConstraintKeys(persona: Persona | null): ConstraintKey[] {
  if (!persona) return []
  const text = persona.health_constraints.toLowerCase()
  const keys: ConstraintKey[] = []
  if (text.includes('sodium')) keys.push('low_sodium')
  if (text.includes('sugar')) keys.push('low_sugar')
  if (text.includes('chew')) keys.push('soft_chewable')
  if (text.includes('medication')) keys.push('medications')
  return keys
}

export interface PersonaState {
  /** Currently selected persona (always defined — falls back to Maria). */
  current: Persona
  /** All available profiles (Maria built-in + user-created custom people). */
  all: Persona[]
  select: (id: string) => void
  /** `taste_anchors` is now OPTIONAL — the create form no longer collects a
   *   habits field (product decision). A new person starts anchorless; the
   *   Taste Bridge centers on their name until they gather explicit tastes. */
  create: (p: { name: string; taste_anchors?: string; health_constraints: string; location: string }) => Persona
}

export function usePersona(): PersonaState {
  const STORAGE_KEY = 'tastecare.persona.v1'

  // Hydrate once from localStorage: the current persona id + any custom profiles.
  // Best-effort — a missing/corrupt entry simply falls back to Maria (default).
  const initial = (() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return null
      const parsed = JSON.parse(raw) as { currentId?: string; custom?: Persona[] }
      if (parsed && Array.isArray(parsed.custom)) return parsed
    } catch {
      /* ignore corrupt storage */
    }
    return null
  })()

  const [currentId, setCurrentId] = useState<string>(initial?.currentId || MARIA_PERSONA.id)
  const [custom, setCustom] = useState<Persona[]>(initial?.custom || [])
  const all = [MARIA_PERSONA, ...custom]
  const current = all.find(p => p.id === currentId) || MARIA_PERSONA

  // Persist on every change so a refresh lands back on the same person + profiles.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ currentId, custom }))
    } catch {
      /* quota/private-mode — demo keeps working without persistence */
    }
  }, [currentId, custom])

  const select = (id: string) => {
    if (all.some(p => p.id === id)) setCurrentId(id)
  }

  const create = (p: { name: string; taste_anchors?: string; health_constraints: string; location: string }): Persona => {
    const profile: Persona = {
      id: `custom-${Date.now().toString(36)}`,
      name: p.name.trim() || 'Custom Person',
      taste_anchors: (p.taste_anchors || '').trim(),
      health_constraints: p.health_constraints.trim(),
      location: p.location.trim(),
    }
    setCustom(prev => [...prev, profile])
    setCurrentId(profile.id)
    return profile
  }

  return { current, all, select, create }
}
