export type AppView = 'tasks' | 'conversation' | 'culture' | 'tastecare' | 'execution' | 'files' | 'providers'

export interface BackendCommand {
  tool: string
  type?: string
  params?: Record<string, unknown>
  reason?: string
  confidence?: number
  risk?: string
  require_confirmation?: boolean
  recommended?: boolean
}

export interface ProcessTopData {
  processes: { name: string; pid: number; mem: number }[]
}

export interface DiskListData {
  drives: { name: string; usePercent: number; free: number }[]
}

export interface TempScanData {
  entries: { isTempLike: boolean }[]
  total: number
}

export interface SystemInfoData {
  platform?: string
  cpus?: number
  totalMem?: number
}

export interface AgentAnalysis {
  analysis: string
  thinking: string
  advice: string
  riskWarning: string
}

export interface BadgeCounts {
  tasks: number
  conversation: number
  execution: number
  files: number
}

export interface AppContextState {
  apiBase: string
  setApiBase: (base: string) => void
  preloadStatus: string
  activeView: AppView
  setActiveView: (view: AppView) => void
  showConfig: boolean
  setShowConfig: (show: boolean) => void
  suggestedCommands: unknown[]
  setSuggestedCommands: unknown
  executionResults: unknown[]
  executionLogs: unknown[]
  pendingActions: unknown[]
  isExecuting: boolean
  isPaused: boolean
  error: string
  agentAnalysis: AgentAnalysis | null
  cloudAudioStatus: string
  handleAnalyzeProblem: unknown
  handleExecuteSelected: unknown
  handleConfirmPending: unknown
  handleRejectPending: unknown
  handlePause: unknown
  handleResume: unknown
  speakText: unknown
}