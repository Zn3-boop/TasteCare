// 动作命令类型
export interface ActionCommand {
  id: string
  tool: string
  type: 'read' | 'write' | 'destructive' | 'system' | 'network'
  params: Record<string, unknown>
  reason: string
  confidence: number
  reasoning?: string
  risk?: 'low' | 'medium' | 'high' | 'blocked'
  require_confirmation?: boolean
  auto_execute?: boolean
  recommended?: boolean
  effect?: string
  impact?: string
}

// 动作执行结果类型
export interface ActionExecutionResult {
  id: string
  tool: string
  success: boolean
  duration: number
  error?: string
  code?: string
  blocked_reason?: string
  data?: unknown
  skipped?: boolean
}

// 语音运行时响应类型
export interface VoiceRuntimeResponse {
  enabled: boolean
  provider: string
  stt_enabled: boolean
  tts_enabled: boolean
  stt_model: string
  tts_model: string
  tts_voice: string
  base_url?: string
  supports_cloud_stt?: boolean
  supports_cloud_tts?: boolean
  recommended_next_steps?: string[]
}

// 语音命令响应类型
export interface VoiceCommandResponse {
  transcript?: string
  normalized_text: string
  intent: string
  reply: string
  review_notes?: string
  review_source?: string
  speech_text: string
  tts_content?: string
  tts_required?: boolean
  tts_audio_base64?: string
  tts_mime_type?: string
  conversation_id?: number
  turn_id?: string
  used_system_context?: boolean
  used_voice_context?: boolean
  used_fallback?: boolean
  fallback_reason?: string
  speech_provider?: string
  tts_fallback_used?: boolean
  tts_available?: boolean
  browser_tts_recommended?: boolean
  speech_capabilities?: {
    supports_cloud_stt?: boolean
    supports_cloud_tts?: boolean
    supports_wake_word?: boolean
    supports_long_session?: boolean
    supports_interruption_control?: boolean
  }
  context_info?: {
    original_turns?: number
    optimized_turns?: number
    history_summary?: string | null
    context_strategy?: string
    estimated_tokens?: number
    history_was_cleaned?: boolean
    history_was_truncated?: boolean
  }
  commands?: ActionCommand[]
  command_execution_mode?: string
  analysis?: string
  thinking?: string
  advice?: string
  risk_warning?: string
}

// 会话记录类型
export interface ConversationRecord {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
  role_prompt?: string
}

// 会话消息类型
export interface ConversationMessage {
  id: number
  conversation_id: number
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  metadata?: {
    source?: 'voice' | 'manual' | 'shortcut' | 'automation'
    turn_id?: string
    session_id?: string
    provider?: string
    intent?: string
    used_system_context?: boolean
    used_voice_context?: boolean
    tool_calls?: unknown[]
  }
  created_at?: string
}

// 文件条目类型
export interface FileEntry {
  name: string
  path: string
  type: 'file' | 'directory'
  isDirectory?: boolean
  size?: number
  modified?: string | null
  modifiedAt?: string | null
  exists?: boolean
}

export interface DirectoryListing {
  path: string
  entries: FileEntry[]
}

export type PendingActionCommand = ActionCommand

export interface ActionLogEntry {
  batchId: string
  timestamp: string
  commands: ActionCommand[]
  results: ActionExecutionResult[]
}

// 后端配置类型
export interface BackendConfig {
  apiBase: string
}

// 语音设置类型
export interface SpeechSettings {
  enabled: boolean
  criticalOnly: boolean
  quietStartHour: number
  quietEndHour: number
}

// 快捷指令类型
export interface ShortcutRecord {
  id: number
  name: string
  content: string
  category: string
  created_at?: string | null
}

// 语音状态响应类型
export interface VoiceStatusResponse {
  provider: string
  enabled: boolean
  available: boolean
  stt_enabled: boolean
  tts_enabled: boolean
  stt_available: boolean
  tts_available: boolean
  stt_model: string
  tts_model: string
  tts_voice: string
  base_url: string
  last_error?: string | null
  last_upload_mime_type?: string | null
  local_whisper_compute_type?: string | null
  local_whisper_device?: string | null
  local_whisper_model_loaded?: boolean | null
}

// 日志条目类型
export interface LogItem {
  id: string
  text: string
  timestamp: number
}

// 浏览器语音识别相关类型
export interface RecognitionAlternative {
  transcript?: string
}

export interface RecognitionResultLike {
  0?: RecognitionAlternative
  isFinal?: boolean
}

export type SpeechRecognitionEventLike = Event & {
  results: ArrayLike<RecognitionResultLike>
}

export type SpeechRecognitionErrorEventLike = Event & {
  error?: string
  message?: string
}

export interface SpeechRecognitionInstance {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
  onstart: (() => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}

export type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance

// 浏览器窗口扩展类型
export type BrowserSpeechWindow = Window & {
  webkitSpeechRecognition?: SpeechRecognitionConstructor
  SpeechRecognition?: SpeechRecognitionConstructor
}

// 语音诊断项类型
export interface VoiceDiagnosticsItem {
  label: string
  value: string
  tone?: 'ok' | 'warning'
}

// ===== 从 app.types.ts 重新导出 =====
export type { AppView, BackendCommand, ProcessTopData, DiskListData, TempScanData, SystemInfoData, AgentAnalysis, BadgeCounts } from './app.types'