// QlooStatusStrip — the one-line process visualization (终版契约③).
// Shows the live Qloo query lifecycle in a single line:
//   ⏳ Querying Qloo Taste Graph… (1.4 s)
//   → ✓ 12 entities matched (2.3 s) — live Qloo grounding
// It self-times the request (memory-only; no timers stored anywhere) so the
// "N entities matched (T s)" number is the real wall-clock duration of the
// Qloo fetch, never a fabricated latency.
import { useEffect, useRef, useState } from 'react'

type Props = {
  loading: boolean
  /** Number of entities the Qloo query resolved (recommendations / anchors). */
  matched?: number | null
  /** Optional suffix shown after the matched count, e.g. "live Qloo grounding". */
  detail?: string
  /** Override the query label (default: "Qloo Taste Graph"). */
  queryLabel?: string
}

export function QlooStatusStrip({ loading, matched = null, detail, queryLabel = 'Qloo Taste Graph' }: Props) {
  const startRef = useRef(0)
  const [elapsed, setElapsed] = useState(0)

  // Time the live query with a stopwatch. The start time and the interval both
  // live inside the effect (the only place refs may be written), and state is
  // only updated from the interval callback — never synchronously in the effect
  // body — so the react-hooks lint rules stay satisfied. On the loading→done
  // transition the cleanup clears the interval and `elapsed` holds the last tick
  // (within ~50ms of the true final duration — honest wall-clock timing).
  useEffect(() => {
    if (loading) {
      startRef.current = performance.now()
      const t = window.setInterval(() => setElapsed((performance.now() - startRef.current) / 1000), 50)
      return () => window.clearInterval(t)
    }
    return undefined
  }, [loading])

  // STABLE DOM CONTRACT — never unmount, never add/remove child nodes:
  // the SAME four spans (keyed) are always rendered; loading/done/idle only ever
  // change their TEXT and the container's CSS (display/colors). React therefore
  // never deletes an old `<span>` to make room for a new one, so the "removeChild:
  // node is not a child" crash — which fired here when concurrent async flows
  // flipped `loading` and React had to swap the span set while a browser
  // translation/labelling extension had already re-parented a text node — has
  // nothing left to delete. Idle is hidden with display:none (a style change),
  // which keeps the node mounted and costs zero visual space.
  const isDone = !loading && matched != null
  const isIdle = !loading && matched == null
  const bg = loading ? '#1a1040' : isDone ? '#0b1f17' : 'transparent'
  const brd = loading ? '1px solid #C77DFF55' : isDone ? '1px solid #05966944' : 'none'
  const fg = loading ? '#D8B4FE' : isDone ? '#6EE7B7' : 'transparent'

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: isIdle ? 'none' : 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
        padding: '7px 12px', borderRadius: 999, fontSize: 12.5, fontWeight: 600,
        fontVariantNumeric: 'tabular-nums',
        background: bg, border: brd, color: fg,
      }}
    >
      <span key="icon" style={{ minWidth: 16 }}>{loading ? '⏳' : isDone ? '✓' : ''}</span>
      <span key="label" style={{ fontWeight: 600 }}>
        {loading ? `Querying ${queryLabel}…` : isDone ? `${matched} entities matched` : ''}
      </span>
      <span key="timer" style={{ opacity: 0.8 }}>{loading || isDone ? `(${elapsed.toFixed(1)} s)` : ''}</span>
      <span key="detail" style={{ fontWeight: 700 }}>{!loading && detail ? `— ${detail}` : ''}</span>
    </div>
  )
}
