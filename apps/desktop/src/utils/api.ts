const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

let _apiBase: string | null = null

export async function getApiBase(): Promise<string> {
  if (_apiBase) return _apiBase
  const base = DEFAULT_API_BASE
  _apiBase = base
  return base
}

export async function setApiBase(url: string): Promise<void> {
  _apiBase = url
}

export async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`)
  }
  return (await response.json()) as T
}

export async function getStorageApiBase(): Promise<string> {
  return `${await getApiBase()}/storage`
}

export async function getVoiceApiBase(): Promise<string> {
  return `${await getApiBase()}/voice`
}

getApiBase()