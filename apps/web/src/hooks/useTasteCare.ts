import { useCallback, useEffect, useMemo, useState } from 'react'
import { tasteCareRecommend, type TasteCareResult } from '../api'
import { SENIOR_PERSONA, CONSTRAINT_META } from '../constants'
import { useSearchHistory } from './useSearchHistory'
import { useToast } from './useToast'

type Busy = { setLoading: (v: boolean) => void; setError: (e: string) => void }

/**
 * TasteCare (Senior Dining) tab state and actions.
 * loading/error are owned by AppShell and forwarded through the Busy callbacks.
 */
export function useTasteCare({ setLoading, setError }: Busy) {
  const toast = useToast()

  // Persist the Senior-Dining form state (likes / location / constraint chips)
  // so a page refresh KEEPS whatever the user last set — including manually
  // toggled health constraints. The persona-watch effect in App only re-marshals
  // the form on a REAL persona switch (or a cold boot with no saved form).
  const FORM_KEY = 'tastecare.form.v1'
  const persistedForm = (() => {
    try {
      const raw = localStorage.getItem(FORM_KEY)
      return raw ? (JSON.parse(raw) as { likes?: string; location?: string; constraints?: Record<string, boolean> }) : null
    } catch { return null }
  })()
  const DEFAULT_CONSTRAINTS: Record<string, boolean> = {
    soft_chewable: true, low_sodium: true, low_sugar: false, medications: false,
  }

  const [tcLikes, setTcLikes] = useState<string>(persistedForm?.likes ?? SENIOR_PERSONA.likes)
  const [tcLocation, setTcLocation] = useState<string>(persistedForm?.location ?? SENIOR_PERSONA.location)
  const [tcConstraints, setTcConstraints] = useState<Record<string, boolean>>(persistedForm?.constraints ?? DEFAULT_CONSTRAINTS)
  // True when a saved form exists → App's persona-watch effect must NOT clobber
  // the user's constraint edits on a cold boot (refresh).
  const formHydrated = !!persistedForm
  const [tcResult, setTcResult] = useState<TasteCareResult | null>(null)
  const [tcSearched, setTcSearched] = useState(false)
  const { history: tcHistory, add: addTcHistory, clear: clearTcHistory } = useSearchHistory('tasteCareHistory', 6)

  // Persist form edits on every change (demo-scale state, cheap stringify).
  useEffect(() => {
    try {
      localStorage.setItem(FORM_KEY, JSON.stringify({ likes: tcLikes, location: tcLocation, constraints: tcConstraints }))
    } catch { /* private-mode: demo keeps working without persistence */ }
  }, [tcLikes, tcLocation, tcConstraints, FORM_KEY])

  const activeConstraintCount = useMemo(
    () => Object.values(tcConstraints).filter(Boolean).length,
    [tcConstraints],
  )
  const activeConstraintLabels = useMemo(
    () => CONSTRAINT_META.filter((m) => tcConstraints[m.key]).map((m) => m.label).join(', '),
    [tcConstraints],
  )

  const doTasteCare = useCallback(async (override?: { likes?: string; location?: string }) => {
    // Accept an explicit override so one-click demos ("Try Maria's Story") can
    // skip the async setState round-trip: the button resets the form AND fires
    // the search with the same values in a single synchronous pass.
    const likesSrc = override?.likes ?? tcLikes
    const likes = likesSrc.split(/[,，\n]/).map(s => s.trim()).filter(Boolean)
    if (!likes.length) { setError('Enter at least one cultural interest (artist, cuisine, film…)'); return }
    const loc = override?.location ?? tcLocation
    setLoading(true); setError(''); setTcSearched(true)
    try {
      const res = await tasteCareRecommend({ cultural_likes: likes, location: loc, constraints: tcConstraints, take: 12 })
      setTcResult(res)
      addTcHistory(likes.join(', '))
      toast('TasteCare suggestions ready — grounded in Qloo taste graph', 'success')
    }
    catch (e) { setError(String(e)); setTcResult(null); toast(String(e), 'error') }
    setLoading(false)
  }, [tcLikes, tcLocation, tcConstraints, addTcHistory, setLoading, setError, toast])

  return {
    tcLikes, setTcLikes,
    tcLocation, setTcLocation,
    tcConstraints, setTcConstraints,
    tcResult, setTcResult,
    tcSearched, setTcSearched,
    tcHistory, clearTcHistory,
    activeConstraintCount, activeConstraintLabels,
    doTasteCare,
    formHydrated,
    defaultLikes: SENIOR_PERSONA.likes,
    defaultLocation: SENIOR_PERSONA.location,
  }
}
