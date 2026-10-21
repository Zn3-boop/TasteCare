import { useCallback, useRef, useState } from 'react'
import { chatWithAgent, chatWithoutQloo, sendTasteFeedback, type QlooEntityDetail } from '../api'
import { useToast } from './useToast'
import { useTasteMemory } from './useTasteMemory'

export type ChatMsg = {
  id: string
  role: string
  text: string
  tasteEntities?: string[]
  tasteDataSource?: string
  qlooContext?: unknown
  tasteEntityDetails?: QlooEntityDetail[]
  tasteRecommendations?: QlooEntityDetail[]
  tasteLocation?: string
  feedback?: 'up' | 'down' | null
}

type Busy = { setLoading: (v: boolean) => void; setError: (e: string) => void }

/**
 * Agent tab's full state and actions (chat + like/dislike feedback).
 */
export function useChatAgent({ setLoading, setError, personaName, personaAnchors, personaMode, onTasteEntities }: Busy & {
  /** Active persona display name (passed from App.tsx). */
  personaName?: string | null
  /** Active persona's comma-separated taste anchors. */
  personaAnchors?: string | null
  /** 'locked' keeps Qloo seeds inside the saved profile; 'mixed' allows exploration. */
  personaMode?: 'locked' | 'mixed'
  /** Called when a Qloo-grounded reply resolves cultural entities, so the caller
   *  (App.tsx) can also feed them into the Taste Bridge — agent input therefore
   *  shows up on the Discover constellation, not just in this tab. */
  onTasteEntities?: (names: string[]) => void
}) {
  const toast = useToast()
  const memory = useTasteMemory()
  const [chatMsg, setChatMsg] = useState('')
  const [chatHistory, setChatHistory] = useState<ChatMsg[]>([])
  const chatEndRef = useRef<HTMLDivElement>(null)

  const doChat = useCallback(async () => {
    if (!chatMsg.trim()) return
    setLoading(true); setError('')
    setChatHistory(h => [...h, { id: crypto.randomUUID(), role: 'user', text: chatMsg }])
    try {
      const r = await chatWithAgent(chatMsg, { personaName, personaAnchors, personaMode })
      if (r.taste_entities && r.taste_entities.length > 0) {
        // Feed agent-resolved cultural entities into the Taste Bridge (Discover),
        // so what the agent grounds on is also visible in the constellation.
        onTasteEntities?.(r.taste_entities)
      }
      setChatHistory(h => [...h, {
        id: crypto.randomUUID(),
        role: 'agent',
        text: r.reply || '',
        tasteEntities: r.taste_entities,
        tasteDataSource: r.taste_data_source,
        qlooContext: r.qloo_context,
        tasteEntityDetails: r.taste_entity_details,
        tasteRecommendations: r.taste_recommendations,
        tasteLocation: r.taste_location || undefined,
        feedback: null,
      }])
    } catch (e) { setError(String(e)) }
    setChatMsg(''); setLoading(false)
  }, [chatMsg, setLoading, setError, personaName, personaAnchors, personaMode, onTasteEntities])

  // Ablation mode: call LLM without Qloo cultural grounding
  const doChatWithoutQloo = useCallback(async () => {
    if (!chatMsg.trim()) return
    setLoading(true); setError('')
    setChatHistory(h => [...h, { id: crypto.randomUUID(), role: 'user', text: chatMsg }])
    try {
      const r = await chatWithoutQloo(chatMsg, { personaName, personaAnchors, personaMode })
      setChatHistory(h => [...h, {
        id: crypto.randomUUID(),
        role: 'agent-no-qloo',
        text: r.reply || '',
        tasteEntities: [],
        tasteDataSource: 'no_qloo',
        qlooContext: null,
        feedback: null,
      }])
    } catch (e) { setError(String(e)) }
    setChatMsg(''); setLoading(false)
  }, [chatMsg, setLoading, setError, personaName, personaAnchors, personaMode])

  const handleFeedback = useCallback(async (messageId: string, thumb: 'up' | 'down') => {
    const target = chatHistory.find(m => m.id === messageId)
    if (!target) return
    setChatHistory(h => h.map(m => m.id === messageId ? { ...m, feedback: thumb } : m))
    try {
      const res = await sendTasteFeedback(messageId, thumb, target.tasteEntities)
      const hint = res.data_source === 'preview'
        ? 'Feedback saved to local preview memory'
        : 'Feedback saved to Qloo taste profile'
      if (thumb === 'up' && target.tasteEntities && target.tasteEntities.length > 0) {
        for (const name of target.tasteEntities.slice(0, 3)) {
          // entity_id = name for the preview/local memory layer so the same liked
          // taste is deduped when the user 👍's it again (compounding over time).
          memory.addLiked(name, name, '')
        }
      }
      toast(`${thumb === 'up' ? '👍' : '👎'} ${hint}`, 'success')
    } catch (e) {
      setChatHistory(h => h.map(m => m.id === messageId ? { ...m, feedback: null } : m))
      toast(`Feedback failed: ${String(e)}`, 'error')
    }
  }, [chatHistory, toast, memory])

  return { chatMsg, setChatMsg, chatHistory, setChatHistory, chatEndRef, doChat, doChatWithoutQloo, handleFeedback, memory }
}
