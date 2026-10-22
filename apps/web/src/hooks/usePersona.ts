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
import { normalizeTasteAnchors } from '../utils/tasteAnchors'

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
  /** `taste_anchors` is OPTIONAL and typically filled from the create/edit
   *   form's habits field. A person with no anchors still works (the bridge
   *   centers on their name), but filling habits means the Agent tab grounds on
   *   THIS person's tastes — edited only in the PersonaPicker (profiles are
   *   never auto-merged from Tastes/Discover). */
  create: (p: { name: string; taste_anchors?: string; health_constraints: string; location: string }) => Persona
  /** Merge updated fields into an existing profile — custom people AND the
   *   built-in Maria (via a dedicated override slot beside the preset). Each
   *   write touches ONLY that person's own data, so anchors never cross into
   *   another profile; Maria's preset constant is never mutated. Returns true
   *   when a profile with that id exists. */
  update: (id: string, patch: Partial<Pick<Persona, 'taste_anchors' | 'health_constraints' | 'location'>>) => boolean
}

export function usePersona(): PersonaState {
  const STORAGE_KEY = 'tastecare.persona.v1'

  // Hydrate once from localStorage: the current persona id + any custom
  // profiles + any edits made to the built-in Maria (her override slot).
  // Best-effort — a missing/corrupt entry simply falls back to Maria (default).
  const initial = (() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return null
      const parsed = JSON.parse(raw) as { currentId?: string; custom?: Persona[]; mariaOverride?: Partial<Persona> }
      // Self-heal poisoned legacy stores: a comma-in-name entity repeated
      // hundreds of times (the "Meet jj" bug) must be collapsed to a single
      // deduped, capped list on hydration — before any tab renders it.
      // Maria's override goes through the same normalization so an edited habit
      // list can never reintroduce the blob growth it was built to prevent.
      const healed = {
        ...parsed,
        custom: Array.isArray(parsed.custom) ? parsed.custom.map(p => ({ ...p, taste_anchors: normalizeTasteAnchors(p.taste_anchors) })) : [],
        mariaOverride: parsed.mariaOverride
          ? {
              ...parsed.mariaOverride,
              taste_anchors: normalizeTasteAnchors(parsed.mariaOverride.taste_anchors ?? MARIA_PERSONA.taste_anchors),
            }
          : undefined,
      }
      return healed
    } catch {
      /* ignore corrupt storage */
    }
    return null
  })()

  const [currentId, setCurrentId] = useState<string>(initial?.currentId || MARIA_PERSONA.id)
  const [custom, setCustom] = useState<Persona[]>(initial?.custom || [])
  // Maria's editable fields live in a SEPARATE override slot layered on top of
  // the read-only preset — editing her in the picker never mutates the shared
  // MARIA_PERSONA constant, and (unlike the old Tastes→persona merge) never
  // touches any OTHER person's profile. Only her own tasting habits change.
  const [mariaOverride, setMariaOverride] = useState<Partial<Persona> | undefined>(initial?.mariaOverride)
  const mariaPersona: Persona = mariaOverride ? { ...MARIA_PERSONA, ...mariaOverride } : MARIA_PERSONA
  const all = [mariaPersona, ...custom]
  const current = all.find(p => p.id === currentId) || mariaPersona

  // Persist on every change so a refresh lands back on the same person + profiles.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ currentId, custom, mariaOverride }))
    } catch {
      /* quota/private-mode — demo keeps working without persistence */
    }
  }, [currentId, custom, mariaOverride])

  const select = (id: string) => {
    if (all.some(p => p.id === id)) setCurrentId(id)
  }

  const create = (p: { name: string; taste_anchors?: string; health_constraints: string; location: string }): Persona => {
    const profile: Persona = {
      id: `custom-${Date.now().toString(36)}`,
      name: p.name.trim() || 'Custom Person',
      // Normalize on entry: dedupe + hard cap + comma-safe protection (a Qloo
      // entity name like "Nature's Point, luxury holiday homes by Together
      // Travel" must not fall victim to comma-based splitting downstream).
      taste_anchors: normalizeTasteAnchors(p.taste_anchors),
      health_constraints: p.health_constraints.trim(),
      location: p.location.trim(),
    }
    setCustom(prev => [...prev, profile])
    setCurrentId(profile.id)
    return profile
  }

  const update: PersonaState['update'] = (id, patch) => {
    // Normalize taste_anchors on every write (dedupe + cap so the profile edit
    // can never blob up — repeated saves settle idempotently).
    const next = { ...patch } as typeof patch
    if (next.taste_anchors !== undefined) next.taste_anchors = normalizeTasteAnchors(next.taste_anchors)
    // Maria is editable through her dedicated override slot — the built-in
    // preset stays pristine and only her own profile reflects the edit.
    if (id === 'maria') {
      setMariaOverride(prev => ({ ...(prev || {}), ...next }))
      return true
    }
    const exists = custom.some(p => p.id === id)
    if (!exists) return false
    setCustom(prev => prev.map(p => (p.id === id ? { ...p, ...next } : p)))
    return true
  }

  return { current, all, select, create, update }
}
