import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import type {
  ActionCommand,
  ActionExecutionResult,
  PendingActionCommand,
  VoiceCommandResponse,
  AgentAnalysis,
} from '../types'
import { useVoiceAgent } from './useVoiceAgent'
import {
  createCommandSignature,
  generateAdviceFromResults,
  generateDefaultCommands,
} from '../utils/command-utils'
import type { AppView } from '../types'

const getApiBase = () => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('api_base') || import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
  }
  return 'http://127.0.0.1:8000'
}

interface AppContextValue {
  apiBase: string
  setApiBase: (base: string) => void
  preloadStatus: string
  activeView: AppView
  setActiveView: (view: AppView) => void
  showConfig: boolean
  setShowConfig: (show: boolean) => void
  suggestedCommands: ActionCommand[]
  setSuggestedCommands: React.Dispatch<React.SetStateAction<ActionCommand[]>>
  executionResults: ActionExecutionResult[]
  executionLogs: { batchId: string; timestamp: string; commands: ActionCommand[]; results: ActionExecutionResult[] }[]
  pendingActions: PendingActionCommand[]
  isExecuting: boolean
  isPaused: boolean
  error: string
  agentAnalysis: AgentAnalysis | null
  cloudAudioStatus: string

  handleAnalyzeProblem: (text: string) => Promise<void>
  handleExecuteSelected: (commands: ActionCommand[]) => Promise<void>
  handleConfirmPending: (ids: string[]) => Promise<void>
  handleRejectPending: (ids: string[]) => void
  handlePause: () => Promise<void>
  handleResume: () => Promise<void>
  speakText: (text: string, label?: string, audioBase64?: string, mimeType?: string) => void
  isMuted: boolean
  setIsMuted: React.Dispatch<React.SetStateAction<boolean>>
  toasts: ToastItem[]
  addToast: (toast: Omit<ToastItem, 'id'>) => void
  removeToast: (id: string) => void
}

export interface ToastItem {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration?: number
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [apiBase, setApiBase] = useState(getApiBase())
  const [preloadStatus, setPreloadStatus] = useState('web mode')
  const [activeView, setActiveView] = useState<AppView>('tasks')
  const [showConfig, setShowConfig] = useState(false)
  const [suggestedCommands, setSuggestedCommands] = useState<ActionCommand[]>([])
  const [executionResults, setExecutionResults] = useState<ActionExecutionResult[]>([])
  const [executionLogs, setExecutionLogs] = useState<{ batchId: string; timestamp: string; commands: ActionCommand[]; results: ActionExecutionResult[] }[]>([])
  const [pendingActions, setPendingActions] = useState<PendingActionCommand[]>([])
  const [isExecuting, setIsExecuting] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [error, setError] = useState('')
  const [agentAnalysis, setAgentAnalysis] = useState<AgentAnalysis | null>(null)
  const [analyzedTools, setAnalyzedTools] = useState<Set<string>>(new Set())
  const [isMuted, setIsMuted] = useState(false)
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const addToast = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    setToasts(prev => [...prev.slice(-9), { ...toast, id }])
    const dur = toast.duration ?? 3000
    if (dur > 0) {
      setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), dur)
    }
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const { speakText: _speakText, cloudAudioStatus } = useVoiceAgent()

  const speakText = useCallback((
    text: string,
    label?: string,
    audioBase64?: string,
    mimeType?: string
  ) => {
    if (isMuted) return
    _speakText(text, label, audioBase64, mimeType)
  }, [_speakText, isMuted])

  const handleAnalyzeProblem = useCallback(async (text: string) => {
    setIsExecuting(true)
    setError('')
    setExecutionResults([])

    try {
      const response = await fetch(`${apiBase}/voice/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript: text,
          mode: 'default',
          system_context: null,
          conversation_id: null,
        }),
      })

      if (!response.ok) throw new Error(`后端返回错误: ${response.status}`)

      const data = await response.json() as VoiceCommandResponse

      if (data.analysis || data.thinking || data.advice) {
        setAgentAnalysis({
          analysis: data.analysis || '',
          thinking: data.thinking || '',
          advice: data.advice || '',
          riskWarning: data.risk_warning || '',
        })
      } else {
        setAgentAnalysis(null)
      }

      if (data.commands && data.commands.length > 0) {
        const seen = new Set<string>()
        const uniqueCommands: ActionCommand[] = []
        
        data.commands.forEach((cmd) => {
          const sig = createCommandSignature(cmd.tool, cmd.params)
          if (!seen.has(sig)) {
            seen.add(sig)
            uniqueCommands.push({
              id: `task-${Date.now()}-${uniqueCommands.length}`,
              tool: cmd.tool,
              type: (cmd.type || 'read') as ActionCommand['type'],
              params: cmd.params || {},
              reason: cmd.reason || '未说明原因',
              confidence: cmd.confidence || 0.5,
              risk: (cmd.risk || 'low') as ActionCommand['risk'],
              require_confirmation: cmd.require_confirmation || cmd.type === 'destructive',
              recommended: cmd.recommended || false,
            })
          }
        })
        
        setSuggestedCommands(uniqueCommands)
      } else {
        setSuggestedCommands(generateDefaultCommands(text))
      }

      if (data.speech_text) {
        speakText(data.speech_text, '分析完成', data.tts_audio_base64, data.tts_mime_type)
      }
    } catch (e) {
      setError(String(e))
      setSuggestedCommands(generateDefaultCommands(text))
    } finally {
      setIsExecuting(false)
    }
  }, [speakText, apiBase])

  const handleExecuteSelected = useCallback(async (commands: ActionCommand[]) => {
    setIsExecuting(true)
    setError('')
    try {
      const response = await fetch(`${apiBase}/voice/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript: `执行以下操作: ${commands.map(c => c.tool).join(', ')}`,
          mode: 'automation',
          system_context: null,
        }),
      })
      const data = await response.json() as VoiceCommandResponse

      const results: ActionExecutionResult[] = commands.map(cmd => ({
        id: cmd.id,
        tool: cmd.tool,
        success: true,
        duration: 0,
        data: data,
      }))
      setExecutionResults(results)

      const successCount = results.filter(r => r.success).length
      const summary = `执行完成，${successCount}个操作已提交`
      speakText(summary, '执行完成')
    } catch (e) {
      setError(String(e))
    } finally {
      setIsExecuting(false)
    }
  }, [speakText, apiBase])

  const handleConfirmPending = useCallback(async (ids: string[]) => {
    const cmds = pendingActions.filter(a => ids.includes(a.id))
    setPendingActions(prev => prev.filter(a => !ids.includes(a.id)))
    if (cmds.length > 0) {
      await handleExecuteSelected(cmds)
    }
  }, [pendingActions, handleExecuteSelected])

  const handleRejectPending = useCallback((ids: string[]) => {
    setPendingActions(prev => prev.filter(a => !ids.includes(a.id)))
  }, [])

  const handlePause = useCallback(async () => {
    setIsPaused(true)
  }, [])

  const handleResume = useCallback(async () => {
    setIsPaused(false)
  }, [])

  const value: AppContextValue = {
    apiBase,
    setApiBase,
    preloadStatus,
    activeView,
    setActiveView,
    showConfig,
    setShowConfig,
    suggestedCommands,
    setSuggestedCommands,
    executionResults,
    executionLogs,
    pendingActions,
    isExecuting,
    isPaused,
    error,
    agentAnalysis,
    cloudAudioStatus,
    handleAnalyzeProblem,
    handleExecuteSelected,
    handleConfirmPending,
    handleRejectPending,
    handlePause,
    handleResume,
    speakText,
    isMuted,
    setIsMuted,
    toasts,
    addToast,
    removeToast,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used within AppProvider')
  }
  return context
}