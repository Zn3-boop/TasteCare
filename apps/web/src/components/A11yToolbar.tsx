import { useEffect, useMemo, useRef, useState } from 'react'

/**
 * A11yToolbar — senior-friendly accessibility controls ("A11y" = accessibility).
 *
 * Zero dependencies, zero third-party keys, 100% local:
 *  - Text scaling with an "whole page OR body text only" switch (scale via zoom).
 *  - Three readable color themes: high contrast (B/W), sepia paper (glare-free),
 *    and deep blue (macular-degeneration friendly).
 *  - Read-aloud via the browser's NATIVE Web Speech API (speechSynthesis) — no
 *    cloud key, works fully offline; current sentence is highlighted as the
 *    voice reads it; pause/resume + rate slider (default slow for seniors).
 *  - "Read full page" and "Read selected text" entry points.
 *  - Everything persists to localStorage so an older user never reconfigures.
 *
 * This is demo-grade senior tuning, floated bottom-center so it is discoverable
 * but never covers content.
 */

const THEMES = [
  { key: 'default', label: 'Original', hint: 'Follow the demo styling' },
  { key: 'high-contrast', label: 'B/W', hint: 'High contrast (B/W)' },
  { key: 'sepia', label: 'Sepia', hint: 'Warm paper, less glare' },
  { key: 'blue', label: 'Blue', hint: 'Deep blue (macular-friendly)' },
] as const
type ThemeKey = (typeof THEMES)[number]['key']

const BTN: React.CSSProperties = {
  minWidth: 44,
  height: 44,
  borderRadius: 10,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  fontSize: 14,
  fontWeight: 700,
  color: '#E5E7EB',
  background: '#1F2937',
  border: '1px solid #374151',
  cursor: 'pointer',
  padding: '0 12px',
}

/** Restore a saved floating-point scale without blowing past bounds. */
function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n))
}

export function A11yToolbar() {
  const [open, setOpen] = useState(false)
  // Text scale 75% – 160%. "contentOnly" scales just the main reading area;
  // otherwise the whole page zooms (header nav included).
  const [scale, setScaleState] = useState<number>(() => {
    const raw = Number(localStorage.getItem('tastecare.a11y.scale') ?? '1')
    return clamp(raw || 1, 0.75, 1.6)
  })
  const [contentOnly, setContentOnly] = useState<boolean>(() => localStorage.getItem('tastecare.a11y.contentOnly') === '1')
  const [theme, setTheme] = useState<ThemeKey>(() => {
    const t = localStorage.getItem('tastecare.a11y.theme')
    return (THEMES.some(x => x.key === t) ? t : 'default') as ThemeKey
  })
  const [playing, setPlaying] = useState(false)
  const [paused, setPaused] = useState(false)
  const [rate, setRate] = useState<number>(() => {
    const r = Number(localStorage.getItem('tastecare.a11y.rate') ?? '0.8')
    return clamp(r || 0.8, 0.6, 1.2)
  })
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
  const pendingRef = useRef<string>('')
  const activeElRef = useRef<HTMLElement | null>(null)

  const persist = (key: string, value: string) => {
    try { localStorage.setItem(key, value) } catch { /* ignore */ }
  }

// ---- Apply visual preferences to the document --------------------------------
  useEffect(() => {
    const root = document.documentElement
    const content = document.querySelector('.app-content') as HTMLElement | null
    if (contentOnly) {
      root.style.zoom = ''
      // Scale ONLY the reading area; header nav stays put so navigation isn't cluttered.
      if (content) content.style.zoom = String(scale)
      document.body.classList.add('a11y-content-only')
    } else {
      root.style.zoom = String(scale)
      if (content) content.style.zoom = ''
      document.body.classList.remove('a11y-content-only')
    }
    persist('tastecare.a11y.scale', String(scale))
    persist('tastecare.a11y.contentOnly', contentOnly ? '1' : '0')
    return () => { root.style.zoom = ''; if (content) content.style.zoom = ''; document.body.classList.remove('a11y-content-only') }
  }, [scale, contentOnly])

  useEffect(() => {
    THEMES.forEach(t => document.body.classList.toggle(`a11y-theme-${t.key}`, theme === t.key))
    persist('tastecare.a11y.theme', theme)
  }, [theme])

  useEffect(() => persist('tastecare.a11y.rate', String(rate)), [rate])

  // ---- Read-aloud helper -------------------------------------------------------
  const stopSpeaking = () => {
    window.speechSynthesis?.cancel()
    utteranceRef.current = null
    setPlaying(false)
    setPaused(false)
    activeElRef.current?.classList.remove('a11y-sentence-active')
    activeElRef.current = null
  }

  useEffect(() => stopSpeaking, [])

  const getSpeakingSource = () => {
    // Prefer currently-selected text; fall back to the whole reading area.
    const sel = window.getSelection()?.toString().trim()
    if (sel) return sel
    const main = document.querySelector('.app-content')
    return (main ? main.textContent : document.body.textContent || '') || ''
  }

  const speak = (text: string) => {
    if (!text.trim() || !('speechSynthesis' in window)) return
    stopSpeaking()
    pendingRef.current = text
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-US'
    u.rate = rate
    u.onend = () => { setPlaying(false); setPaused(false); activeElRef.current?.classList.remove('a11y-sentence-active'); activeElRef.current = null }
    u.onerror = () => { setPlaying(false); setPaused(false) }
    // Highlight the sentence being read, sentence boundaries from the source.
    u.onboundary = (e: SpeechSynthesisEvent) => {
      try {
        const idx = e.charIndex
        const src = pendingRef.current
        const sentence = src.slice(0, idx).split(/[.!?。！？]|(?:\s*$)/).filter(Boolean).pop() || ''
        const re = new RegExp(sentence.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
        const main = document.querySelector('.app-content') || document.body
        // Walk text nodes; a target is the smallest element CONTAINING the text.
        const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT)
        let node: Node | null = walker.nextNode()
        while (node) {
          const txt = (node.textContent || '').trim()
          if (txt && re.test(txt)) {
            const target = node.parentElement as HTMLElement | null
            if (target && target !== activeElRef.current) {
              activeElRef.current?.classList.remove('a11y-sentence-active')
              target.classList.add('a11y-sentence-active')
              activeElRef.current = target
            }
            break
          }
          node = walker.nextNode()
        }
      } catch { /* boundary highlight is best-effort */ }
    }
    utteranceRef.current = u
    window.speechSynthesis.speak(u)
    setPlaying(true)
    setPaused(false)
  }

  const togglePause = () => {
    if (!('speechSynthesis' in window)) return
    if (paused) { window.speechSynthesis.resume(); setPaused(false) }
    else { window.speechSynthesis.pause(); setPaused(true) }
  }

  const setScale = (d: number) => setScaleState(s => clamp(+(s + d).toFixed(2), 0.75, 1.6))

  const themePreview = useMemo(() => ({
    default: { bg: '#0b1020', fg: '#E5E7EB' },
    'high-contrast': { bg: '#000', fg: '#FFD60A' },
    sepia: { bg: '#F5EBC8', fg: '#3E2E17' },
    blue: { bg: '#0B1E3F', fg: '#E7F3FF' },
  }), [])
return (
    <div style={{ position: 'fixed', left: '50%', bottom: 14, transform: 'translateX(-50%)', zIndex: 60, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      {open && (
        <div style={{ width: 'min(680px, calc(100vw - 24px))', background: '#111827F2', border: '1px solid #374151', borderRadius: 16, padding: 14, boxShadow: '0 12px 32px rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)' }}>
          {/* 1) Text size */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
            <label style={{ fontSize: 12, fontWeight: 700, color: '#E5E7EB' }}>Text size</label>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button style={{ ...BTN }} onClick={() => setScale(-0.1)} aria-label="Decrease text size">A−</button>
              <span style={{ fontSize: 13, color: '#D1D5DB', minWidth: 44, textAlign: 'center' }}>{Math.round(scale * 100)}%</span>
              <button style={{ ...BTN }} onClick={() => setScale(0.1)} aria-label="Increase text size">A+</button>
              <label style={{ fontSize: 12, color: '#9CA3AF', display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer', marginLeft: 8 }}>
                <input type="checkbox" checked={contentOnly} onChange={e => setContentOnly(e.target.checked)} style={{ width: 16, height: 16 }} />
                Body text only
              </label>
            </span>
          </div>

          {/* 2) Color theme */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#E5E7EB', marginBottom: 6 }}>Color theme (eye-friendly)</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {THEMES.map(t => {
                const p = themePreview[t.key]
                const active = theme === t.key
                return (
                  <button
                    key={t.key}
                    onClick={() => setTheme(t.key)}
                    title={t.hint}
                    style={{
                      height: 44,
                      padding: '0 12px',
                      borderRadius: 10,
                      cursor: 'pointer',
                      fontSize: 13,
                      fontWeight: 700,
                      background: p.bg,
                      color: p.fg,
                      border: active ? '2px solid #F5A623' : '1px solid #374151',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    {active ? '✓ ' : ''}{t.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* 3) Read aloud */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: '#E5E7EB' }}>Read aloud</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <label style={{ fontSize: 11, color: '#9CA3AF' }}>Speed</label>
                <input
                  type="range" min={0.6} max={1.2} step={0.05} value={rate}
                  onChange={e => setRate(Number(e.target.value))}
                  style={{ width: 120, accentColor: '#F5A623' }}
                  aria-label="Reading speed"
                />
                <span style={{ fontSize: 11, color: '#9CA3AF', minWidth: 40 }}>{rate.toFixed(2)}×</span>
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button style={{ ...BTN, background: '#0B63CE', borderColor: '#0B63CE' }} onClick={() => speak(getSpeakingSource())}>
                {playing ? '🔄 Re-read page' : '🔊 Read page aloud'}
              </button>
              {playing && (
                <button style={{ ...BTN }} onClick={togglePause}>
                  {paused ? '▶ Resume' : '⏸ Pause'}
                </button>
              )}
              <button style={{ ...BTN }} onClick={() => { const s = window.getSelection()?.toString().trim(); if (s) speak(s) }}>
                📖 Read selected text
              </button>
              <button style={{ ...BTN }} onClick={stopSpeaking}>⏹ Stop</button>
            </div>
            <div style={{ fontSize: 10.5, color: '#6B7280', marginTop: 6 }}>
              Browser-native text-to-speech (Web Speech API) — no network or server key needed; the current sentence is highlighted as it is read.
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Accessibility tools"
        title="Accessibility tools"
        style={{
          width: 52, height: 52, borderRadius: '50%',
          background: 'linear-gradient(135deg, #FF6B35, #F5A623)',
          color: '#fff', fontSize: 22, border: 'none', cursor: 'pointer',
          boxShadow: '0 4px 16px rgba(245,166,35,0.4)',
        }}
      >
        {open ? '✕' : '♿'}
      </button>
      {!open && (
        <span style={{ fontSize: 10, color: '#9CA3AF', background: '#111827CC', padding: '3px 10px', borderRadius: 20, border: '1px solid #374151' }}>
          Accessibility tools
        </span>
      )}
    </div>
  )
}