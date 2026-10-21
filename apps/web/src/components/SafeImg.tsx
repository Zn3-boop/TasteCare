// SafeImg — image that never touches the DOM directly from an event handler.
// React 19 + StrictMode: mutating `e.currentTarget.style` inside `onError` races
// with React's own commit phase (the node may be detached while the handler
// runs) and is a classic "removeChild: node is not a child" trigger. Instead we
// flip local state and render a styled letter fallback — the DOM stays fully
// React-owned.
import { useState, type CSSProperties } from 'react'

type Props = {
  src: string
  alt?: string
  style?: CSSProperties
  fallbackStyle?: CSSProperties
  fallbackChar?: string
}

export function SafeImg({ src, alt = '', style, fallbackStyle, fallbackChar }: Props) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return (
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#1F2937', color: '#9CA3AF', fontWeight: 700, flexShrink: 0,
          ...fallbackStyle, ...style,
        }}
      >
        {(fallbackChar || alt || '?')[0]?.toUpperCase()}
      </div>
    )
  }
  return <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} style={style} />
}
