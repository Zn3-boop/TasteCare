/** Taste Memory — persists resolved Qloo anchors in localStorage across sessions.

When the user likes a recommendation or manually adds an entity as a taste anchor,
this hook records the entity_id + name + domain so that future cross-domain
fetches prepend those IDs to signal.interests.entities.
*/
import { useCallback, useState } from 'react'

export interface MemoryEntity {
  entity_id: string
  name: string
  domain: string
  added_at: string
}

const STORAGE_KEY = 'tastecare_memory'

function loadFromStorage(): MemoryEntity[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as MemoryEntity[]) : []
  } catch { return [] }
}

function saveToStorage(entities: MemoryEntity[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(entities)) } catch { /* quota */ }
}

export function useTasteMemory() {
  const [liked, setLiked] = useState<MemoryEntity[]>(loadFromStorage)

  const addLiked = useCallback((entity_id: string, name: string, domain: string) => {
    setLiked(prev => {
      const filtered = prev.filter(e => e.entity_id !== entity_id)
      const next = [{ entity_id, name, domain, added_at: new Date().toISOString() }, ...filtered].slice(0, 20)
      saveToStorage(next)
      return next
    })
  }, [])

  const removeLiked = useCallback((entity_id: string) => {
    setLiked(prev => {
      const next = prev.filter(e => e.entity_id !== entity_id)
      saveToStorage(next)
      return next
    })
  }, [])

  const clearAll = useCallback(() => {
    setLiked([])
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* noop */ }
  }, [])

  const entityIds = liked.map(e => e.entity_id)

  return { liked, addLiked, removeLiked, clearAll, entityIds }
}
