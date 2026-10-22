/**
 * Shared taste-anchor string helpers.
 *
 * Taste anchors are stored as free text (the create form, the Senior Dining
 * textarea, and the Tastes → persona write-back all append to one string). The
 * canonical STORAGE format is a comma-separated list ("Frank Sinatra, Jazz,
 * Italian cuisine"), but real Qloo entity names can contain commas themselves
 * (e.g. "Nature's Point, luxury holiday homes by Together Travel"). A naive
 * comma split would truncate that name to "Nature's Point", so a subsequent
 * dedup pass never matches the full name and the write-back effect appends one
 * more copy on every run — unbounded localStorage growth and React 19's
 * "Maximum update depth exceeded".
 *
 * COMMA-SPLIT HEURISTIC (must stay in sync with the backend
 * `_split_anchor_text` in apps/server/app/api/chat.py). For each comma, look at
 * the segment B right after it:
 *   1. B starts LOWERCASE:
 *      - B has ≤ 2 words  → treat as an alias-variant duplicate ("Frank
 *        Sinatra, frank sinatra") → SPLIT into separate anchors.
 *      - B has > 2 words  → treat as a descriptive subtitle belonging to the
 *        current name ("Nature's Point, luxury holiday homes by Together
 *        Travel") → KEEP the comma, one anchor.
 *   2. B starts UPPERCASE / CJK / digit → another distinct entity → SPLIT.
 * A hard cap (MAX_TASTE_ANCHORS) keeps corrupted/legacy stores bounded.
 */
export const MAX_TASTE_ANCHORS = 32

/**
 * Split a taste-anchor string into clean, deduped, capped anchor names.
 * Separators: full/half-width commas and 、(with the comma-skip rule above),
 * newlines, and the legacy full-width 、. Case-insensitive dedupe.
 */
export function splitTasteAnchors(text: string | null | undefined): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  const push = (raw: string) => {
    const name = raw.trim()
    if (!name || name.length > 120) return
    const key = name.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    out.push(name)
  }
  // First split on newlines / 、(which never appear inside a name), then walk
  // the remaining text keeping commas only when they separate title-like parts.
  for (const line of (text || '').split(/[\n\r\u3001]+/)) {
    const parts = splitCommaKeepingNames(line)
    for (const p of parts) push(p)
  }
  return out.slice(0, MAX_TASTE_ANCHORS)
}

/** Split on commas, but keep the comma when the following token is NOT
 *  title-like (does not start uppercase / CJK / digit), so names containing
 *  commas ("Nature's Point, luxury holiday homes by Together Travel") survive.
 *  A lowercase-starting phrase that is SHORT (≤ 2 words, e.g. "frank sinatra"
 *  as a capitalized-variant duplicate) is still treated as a separator so
 *  case-insensitive dedup keeps working. */
function splitCommaKeepingNames(segment: string): string[] {
  const out: string[] = []
  let buf = ''
  let i = 0
  const s = segment
  /** Strip trailing separators/space (a blob often ends mid-list: "…Jazz, "). */
  const finalize = (raw: string) => raw.trim().replace(/[,，\s]+$/, '')
  while (i < s.length) {
    const ch = s[i]
    if (ch === ',' || ch === '，') {
      const rest = s.slice(i + 1)
      const m = rest.match(/^\s*(\S)/)
      const nextCh = m ? m[1] : ''
      let split = false
      if (nextCh) {
        if (/[A-Z]/.test(nextCh) || /[\u4e00-\u9fff0-9]/.test(nextCh)) {
          split = true
        } else if (/[a-z]/.test(nextCh)) {
          // Lowercase start: a SHORT following phrase is probably a capitalized
          // duplicate ("Frank Sinatra, frank sinatra"); a LONG one is a
          // descriptive subtitle belonging to the name
          // ("Nature's Point, luxury holiday homes by Together Travel").
          const pm = rest.match(/^\s*[a-zA-Z][\w'’\u2010-]*(\s+[a-zA-Z][\w'’\u2010-]*)*/)
          const words = pm ? pm[0].trim().split(/\s+/).length : 0
          split = words <= 2
        }
      }
      if (split && buf.trim()) {
        out.push(finalize(buf))
        buf = ''
        i++
        continue
      }
      // Otherwise keep the comma inside the current name.
      buf += ch
    } else {
      buf += ch
    }
    i++
  }
  if (buf.trim()) out.push(finalize(buf))
  return out
}

/** Join anchor names back into the canonical storage string (comma-separated). */
export function joinTasteAnchors(names: string[]): string {
  return names.map(n => n.trim()).filter(Boolean).slice(0, MAX_TASTE_ANCHORS).join(', ')
}

/**
 * Normalize a raw taste-anchor string: split → dedupe → cap → rejoin.
 * Use on the write-back path so repeated runs are idempotent.
 */
export function normalizeTasteAnchors(text: string | null | undefined): string {
  return joinTasteAnchors(splitTasteAnchors(text))
}
