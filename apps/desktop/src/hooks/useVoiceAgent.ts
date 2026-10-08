import { useState, useCallback, useRef, useEffect } from 'react'
import type { VoiceRuntimeResponse, VoiceCommandResponse } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
const VOICE_API_BASE = `${API_BASE}/voice`

export const useVoiceAgent = () => {
  const [voiceRuntime, setVoiceRuntime] = useState<VoiceRuntimeResponse | null>(null)
  const [voiceResponse, setVoiceResponse] = useState<VoiceCommandResponse | null>(null)
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [voiceError, setVoiceError] = useState('')
  const [cloudAudioStatus, setCloudAudioStatus] = useState('未连接云端语音服务')

  const audioPlaybackRef = useRef<HTMLAudioElement | null>(null)

  const loadVoiceRuntime = useCallback(async () => {
    try {
      const response = await fetch(`${VOICE_API_BASE}/runtime`)
      if (response.ok) {
        const data = await response.json() as VoiceRuntimeResponse
        setVoiceRuntime(data)
        if (data.stt_enabled || data.tts_enabled) {
          setCloudAudioStatus(`后端语音部分可用：${data.provider}（STT:${data.stt_enabled ? '开' : '关'} / TTS:${data.tts_enabled ? '开' : '关'}）`)
        } else {
          setCloudAudioStatus('后端语音未启用，将优先尝试浏览器语音能力')
        }
      }
    } catch {
      setCloudAudioStatus('未获取到语音运行时配置，将继续按浏览器能力运行')
    }
  }, [])

  useEffect(() => {
    void loadVoiceRuntime()
  }, [loadVoiceRuntime])

  const stopActiveSpeech = useCallback(() => {
    if (audioPlaybackRef.current) {
      audioPlaybackRef.current.pause()
      audioPlaybackRef.current = null
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
  }, [])

  const speakText = useCallback((
    text: string,
    doneLabel = '播报完成',
    cloudAudioBase64?: string | null,
    cloudAudioMimeType?: string | null
  ) => {
    stopActiveSpeech()

    if (cloudAudioBase64) {
      const audio = new Audio(`data:${cloudAudioMimeType ?? 'audio/mpeg'};base64,${cloudAudioBase64}`)
      audioPlaybackRef.current = audio
      audio.onplay = () => {
        setCloudAudioStatus('当前正在播放云端 TTS 音频')
      }
      audio.onended = () => {
        setCloudAudioStatus('云端音频播放完成')
        audioPlaybackRef.current = null
      }
      audio.onerror = () => {
        audioPlaybackRef.current = null
        setCloudAudioStatus('云端音频播放失败，准备回退浏览器 TTS')
      }
      void audio.play().catch(() => {
        audioPlaybackRef.current = null
        setCloudAudioStatus('浏览器阻止自动播放，准备回退浏览器 TTS')
      })
      return
    }

    if (!window.speechSynthesis) {
      setCloudAudioStatus('当前环境不支持浏览器 TTS，请改为查看文本回复')
      return
    }

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'zh-CN'
    utterance.onstart = () => setCloudAudioStatus('正在使用浏览器语音播报')
    utterance.onend = () => setCloudAudioStatus(doneLabel)
    utterance.onerror = () => setCloudAudioStatus('浏览器 TTS 不可用，请查看文本回复或启用后端 TTS')
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
  }, [stopActiveSpeech])

  const submitVoiceCommand = useCallback(async (
    transcript: string,
    options?: {
      conversationId?: number | null
      source?: string
      turnId?: string
    }
  ) => {
    setVoiceLoading(true)
    setVoiceError('')

    try {
      const turnId = options?.turnId ?? `turn-${Date.now()}`

      const response = await fetch(`${VOICE_API_BASE}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript,
          mode: 'voice',
          system_context: null,
          conversation_id: options?.conversationId,
          turn_id: turnId,
          source: options?.source ?? 'voice',
        }),
      })

      if (!response.ok) {
        throw new Error(`voice command failed: ${response.status}`)
      }

      const data = await response.json() as VoiceCommandResponse
      setVoiceResponse(data)
      
      return data
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '语音命令处理失败'
      setVoiceError(errorMsg)
      throw err
    } finally {
      setVoiceLoading(false)
    }
  }, [speakText])

  return {
    voiceRuntime,
    voiceResponse,
    voiceLoading,
    voiceError,
    cloudAudioStatus,
    audioPlaybackRef,
    loadVoiceRuntime,
    submitVoiceCommand,
    stopActiveSpeech,
    speakText,
  }
}