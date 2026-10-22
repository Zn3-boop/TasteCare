/**
 * Dedupe a list while preserving first-seen order.
 *
 * React 19's reconciliation treats duplicate list keys as a hard error and
 * crashes with "Failed to execute 'removeChild' on 'Node'" when a re-render
 * reorders/inserts items. Backend-driven lists (taste_entities, Qloo search /
 * recommend / cross-domain results, TasteCare recommendations) have repeatedly
 * been observed to contain duplicate ids (or empty ids that collapse to the
 * same fallback key), so every render boundary must dedupe + guarantee a
 * unique composite key before mapping.
 */
export function uniqueBy<T>(items: T[], pick: (item: T) => string): T[] {
  const seen = new Set<string>()
  const out: T[] = []
  for (const item of items) {
    const key = pick(item)
    if (!key || seen.has(key)) continue
    seen.add(key)
    out.push(item)
  }
  return out
}

/** Unique, stable key for a list item: real id wins, else name, else index. */
export function entityKey(id?: string | null, name?: string | null, index = 0): string {
  return id || `${name || 'item'}-${index}`
}
