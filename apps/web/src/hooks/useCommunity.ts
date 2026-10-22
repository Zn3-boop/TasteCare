import { useCallback, useEffect, useState } from 'react'
import {
  communityAccept, communityConnect, communityConnections, communityMatch,
  type CommunityMatchResponse,
} from '../api'
import { useToast } from './useToast'
import { splitTasteAnchors } from '../utils/tasteAnchors'

/**
 * Community tab state — Qloo-powered peer matching with mutual opt-in.
 *
 * - doMatch: resolve your cultural likes through Qloo (cloud) and find peers
 *   with overlapping anchors + health constraints.
 * - doConnect: send a PENDING request — connection only completes after the
 *   other party accepts (mutual verification by design).
 */
export function useCommunity() {
  const toast = useToast()
  const [likesText, setLikesText] = useState('Frank Sinatra, Italian cuisine, Jazz')
  const [location, setLocation] = useState('New York')
  const [constraints, setConstraints] = useState<Record<string, boolean>>({
    low_sodium: true,
    soft_chewable: true,
  })
  const [result, setResult] = useState<CommunityMatchResponse | null>(null)
  // Connections live in a lightweight server-side JSON store (server/data/
  // community_connections.json) and SURVIVE restarts — this map re-hydrates them
  // on load so already-connected peers show "✅ Connected" after a refresh.
  const [saved, setSaved] = useState<Record<string, string>>({})

  useEffect(() => {
    let alive = true
    communityConnections().then(res => {
      if (!alive) return
      const map: Record<string, string> = {}
      res.connections.forEach(c => { map[c.peer_id] = c.status })
      setSaved(map)
    }).catch(() => { /* best-effort */ })
    return () => { alive = false }
  }, [])

  const doMatch = useCallback(async () => {
    const likes = splitTasteAnchors(likesText)
    if (!likes.length) {
      toast('Enter at least one cultural anchor', 'error')
      return
    }
    toast('Matching via the Qloo taste graph…', 'info')
    try {
      const r = await communityMatch({
        cultural_likes: likes,
        location: location || undefined,
        constraints,
      })
      setResult(r)
      const live = r.data_source === 'live'
      toast(live ? `Found ${r.matches.length} matches (Qloo live)` : `Found ${r.matches.length} matches (demo peer pool)`, 'success')
    } catch (e) {
      toast(`Matching failed: ${String(e)}`, 'error')
    }
  }, [likesText, location, constraints, toast])

  const doConnect = useCallback(async (peerId: string) => {
    try {
      const r = await communityConnect(peerId)
      if (r.ok) {
        toast(r.message || 'Connection request sent (pending).', 'success')
      } else {
        toast(r.error || 'Connection request failed.', 'error')
      }
      return r
    } catch (e) {
      toast(`Connect failed: ${String(e)}`, 'error')
      return null
    }
  }, [toast])

  const doAccept = useCallback(async (peerId: string) => {
    try {
      const r = await communityAccept(peerId)
      if (r.ok) {
        toast('Connection accepted — mutual verification complete. Remember: independently verify any health advice.', 'success')
      } else {
        toast(r.error || 'Accept failed.', 'error')
      }
      return r
    } catch (e) {
      toast(`Accept failed: ${String(e)}`, 'error')
      return null
    }
  }, [toast])

  const toggleConstraint = useCallback((key: string) => {
    setConstraints(prev => ({ ...prev, [key]: !prev[key] }))
  }, [])

  return {
    likesText, setLikesText, location, setLocation, constraints, toggleConstraint,
    result, saved, doMatch, doConnect, doAccept,
  }
}