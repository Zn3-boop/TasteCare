import { useCallback, useRef, useState } from 'react'
import { chatWithAgent, sendTasteFeedback } from '../api'
import { useToast } from './useToast'

export type ChatMsg = {
  id: string
  role: string
  text: string
  tasteEntities?: string[]
  tasteDataSource?: string
  qlooContext?: unknown
  feedback?: 'up' | 'down' | null
}

type Busy = { setLoading: (v: boolean) => void; setError: (e: string) => void }

/**
 * Agent tab 的全部状态与动作（对话 + 点赞/点踩反馈）。
 */
export function useChatAgent({ setLoading, setError }: Busy) {
  const toast = useToast()
  const [chatMsg, setChatMsg] = useState('')
  const [chatHistory, setChatHistory] = useState<ChatMsg[]>([])
  const chatEndRef = useRef<HTMLDivElement>(null)

  const doChat = useCallback(async () => {
    if (!chatMsg.trim()) return
    setLoading(true); setError('')
    setChatHistory(h => [...h, { id: crypto.randomUUID(), role: 'user', text: chatMsg }])
    try {
      const r = await chatWithAgent(chatMsg)
      setChatHistory(h => [...h, {
        id: crypto.randomUUID(),
        role: 'agent',
        text: r.reply || '',
        tasteEntities: r.taste_entities,
        tasteDataSource: r.taste_data_source,
        qlooContext: r.qloo_context,
        feedback: null,
      }])
    } catch (e) { setError(String(e)) }
    setChatMsg(''); setLoading(false)
  }, [chatMsg, setLoading, setError])

  const handleFeedback = useCallback(async (messageId: string, thumb: 'up' | 'down') => {
    const target = chatHistory.find(m => m.id === messageId)
    if (!target) return
    setChatHistory(h => h.map(m => m.id === messageId ? { ...m, feedback: thumb } : m))
    try {
      const res = await sendTasteFeedback(messageId, thumb, target.tasteEntities)
      const hint = res.data_source === 'preview'
        ? 'Feedback saved to local preview memory'
        : 'Feedback saved to Qloo taste profile'
      toast(`${thumb === 'up' ? '👍' : '👎'} ${hint}`, 'success')
    } catch (e) {
      setChatHistory(h => h.map(m => m.id === messageId ? { ...m, feedback: null } : m))
      toast(`Feedback failed: ${String(e)}`, 'error')
    }
  }, [chatHistory, toast])

  return { chatMsg, setChatMsg, chatHistory, setChatHistory, chatEndRef, doChat, handleFeedback }
}
