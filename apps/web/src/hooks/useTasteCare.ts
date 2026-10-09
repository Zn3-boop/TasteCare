import { useCallback, useMemo, useState } from 'react'
import { tasteCareRecommend, type TasteCareResult } from '../api'
import { SENIOR_PERSONA, CONSTRAINT_META } from '../constants'
import { useSearchHistory } from './useSearchHistory'
import { useToast } from './useToast'

type Busy = { setLoading: (v: boolean) => void; setError: (e: string) => void }

/**
 * TasteCare（Senior Dining）tab 的全部状态与动作。
 * loading/error 由 AppShell 统一管理，通过 Busy 回调透传。
 */
export function useTasteCare({ setLoading, setError }: Busy) {
  const toast = useToast()

  const [tcLikes, setTcLikes] = useState(SENIOR_PERSONA.likes)
  const [tcLocation, setTcLocation] = useState(SENIOR_PERSONA.location)
  const [tcConstraints, setTcConstraints] = useState<Record<string, boolean>>({
    soft_chewable: true, low_sodium: true, low_sugar: false, medications: false,
  })
  const [tcResult, setTcResult] = useState<TasteCareResult | null>(null)
  const [tcSearched, setTcSearched] = useState(false)
  const { history: tcHistory, add: addTcHistory, clear: clearTcHistory } = useSearchHistory('tasteCareHistory', 6)

  const activeConstraintCount = useMemo(
    () => Object.values(tcConstraints).filter(Boolean).length,
    [tcConstraints],
  )
  const activeConstraintLabels = useMemo(
    () => CONSTRAINT_META.filter((m) => tcConstraints[m.key]).map((m) => m.label).join(', '),
    [tcConstraints],
  )

  const doTasteCare = useCallback(async () => {
    const likes = tcLikes.split(/[,，\n]/).map(s => s.trim()).filter(Boolean)
    if (!likes.length) { setError('Enter at least one cultural interest (artist, cuisine, film…)'); return }
    setLoading(true); setError(''); setTcSearched(true)
    try {
      const res = await tasteCareRecommend({ cultural_likes: likes, location: tcLocation, constraints: tcConstraints, take: 12 })
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
  }
}
