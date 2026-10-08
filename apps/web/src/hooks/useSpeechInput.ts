import { useEffect, useRef, useState } from 'react'

// Minimal structural types for the Web Speech API so we don't need the
// DOM/lib.dom types to be globally complete.
type TranscriptResult = { transcript: string }
type SpeechRecognitionResultLike = { isFinal: boolean; 0: TranscriptResult }
type SpeechRecognitionEventLike = {
  resultIndex: number
  results: { length: number; [i: number]: SpeechRecognitionResultLike }
}
type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: SpeechRecognitionEventLike) => void) | null
  onend: (() => void) | null
  onerror: ((e: { error: string }) => void) | null
  start: () => void
  stop: () => void
}

/**
 * Browser-native speech-to-text for the senior search box.
 * Wraps the Web Speech API (SpeechRecognition / webkitSpeechRecognition).
 * - en-US by default, no backend call, no API key.
 * - Returns `supported: false` on browsers without the API, so callers can
 *   hide the mic button and gracefully degrade to typing.
 */
export function useSpeechInput(onTranscript: (t: string) => void, lang = 'en-US') {
  const [supported, setSupported] = useState(false)
  const [listening, setListening] = useState(false)
  const [error, setError] = useState('')
  const recRef = useRef<SpeechRecognitionLike | null>(null)
  const onTranscriptRef = useRef(onTranscript)
  onTranscriptRef.current = onTranscript

  useEffect(() => {
    if (typeof window === 'undefined') return
    const w = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognitionLike
      webkitSpeechRecognition?: new () => SpeechRecognitionLike
    }
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition
    if (!Ctor) { setSupported(false); return }
    setSupported(true)

    const rec = new Ctor()
    rec.lang = lang
    rec.interimResults = true
    rec.continuous = true
    let final = ''
    let last = ''
    rec.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const tr = e.results[i]?.[0]?.transcript ?? ''
        if (e.results[i].isFinal) final += tr
        else interim += tr
      }
      last = final + interim
      onTranscriptRef.current(last)
    }
    rec.onend = () => setListening(false)
    rec.onerror = (e) => { setError(e.error); setListening(false) }
    recRef.current = rec

    return () => {
      rec.onend = null
      rec.onerror = null
      try { rec.stop() } catch { /* already stopped */ }
    }
  }, [lang])

  const start = () => {
    if (!recRef.current) return
    setError('')
    setListening(true)
    try { recRef.current.start() } catch { /* already started */ }
  }
  const stop = () => recRef.current?.stop()
  const toggle = () => (listening ? stop() : start())

  return { supported, listening, error, start, stop, toggle }
}
