// 后端已对业务 API 统一加 /api/v1 前缀（/ 与 /health 是探活路径，不用版本）。
const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '') + '/api/v1'

export interface QlooEntity {
  id: string
  name: string
  type: string
  domain?: string
  score?: number
  image_url?: string
}

export async function qlooSearch(query: string, domain?: string, limit?: number): Promise<QlooEntity[]> {
  const resp = await fetch(`${API_BASE}/qloo/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, domain, limit: limit || 10 }),
  })
  if (!resp.ok) throw new Error(`Search failed: ${resp.status}`)
  const data = await resp.json()
  return data.results || []
}

export async function qlooRecommend(seedEntityIds: string[], targetDomain?: string, limit?: number) {
  const resp = await fetch(`${API_BASE}/qloo/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seed_entity_ids: seedEntityIds, target_domain: targetDomain, limit: limit || 10 }),
  })
  if (!resp.ok) throw new Error(`Recommend failed: ${resp.status}`)
  return await resp.json()
}

export async function qlooCrossDomain(seedEntityIds: string[], domains?: string[], perDomainLimit?: number) {
  const resp = await fetch(`${API_BASE}/qloo/cross-domain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seed_entity_ids: seedEntityIds, domains, per_domain_limit: perDomainLimit || 5 }),
  })
  if (!resp.ok) throw new Error(`Cross-domain failed: ${resp.status}`)
  return await resp.json()
}

export async function qlooCulturalFit(seedNames: string[], candidateNames: string[], domain?: string) {
  const resp = await fetch(`${API_BASE}/qloo/cultural-fit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seed_names: seedNames, candidate_names: candidateNames, domain }),
  })
  if (!resp.ok) throw new Error(`Cultural fit failed: ${resp.status}`)
  const data = await resp.json()
  return data.scores || []
}

export async function qlooStatus() {
  const resp = await fetch(`${API_BASE}/qloo/status`)
  if (!resp.ok) return { enabled: false, base_url: '', api_key_set: false }
  return await resp.json()
}

export interface ChatAgentResponse {
  reply: string
  taste_entities?: string[]
  taste_data_source?: string
  qloo_context?: unknown
  tool_calls?: unknown[]
}

export async function chatWithAgent(message: string): Promise<ChatAgentResponse> {
  const resp = await fetch(`${API_BASE}/chat/agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!resp.ok) throw new Error(`Chat failed: ${resp.status}`)
  return await resp.json()
}

// ===== TasteCare (senior dining, Qloo-grounded) =====
export interface TasteCareRecommendation {
  id: string
  name: string
  type?: string
  image?: string
  tags?: string[]
  popularity?: number
  fit?: number
  fit_source?: 'qloo-popularity' | 'qloo-affinity'
  description?: string
  address?: string
  health?: { passes: boolean; labels: string[]; warnings: string[] }
  // Two-part rationale (from answer_generation_node); optional so cards fall back gracefully.
  cultural_match?: string
  safety_validation?: string
}

export interface TasteCareResult {
  recommendations: TasteCareRecommendation[]
  source?: string
  location?: string
  active_constraints?: string[]
  explanation?: string
  disclaimer?: string
}

export async function tasteCareRecommend(input: {
  cultural_likes: string[]
  location?: string
  constraints?: Record<string, boolean>
  take?: number
}): Promise<TasteCareResult> {
  const resp = await fetch(`${API_BASE}/tastecare/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      cultural_likes: input.cultural_likes,
      location: input.location || undefined,
      constraints: input.constraints || {},
      take: input.take || 12,
    }),
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.detail || `TasteCare failed: ${resp.status}`)
  }
  return await resp.json()
}

// ===== 👍/👎 feedback loop (P0) =====
export interface FeedbackResponse {
  ok: boolean
  message_id: string
  thumb: string
  data_source: string
  qloo_enabled: boolean
  recorded: boolean
  note?: string
}

export async function sendTasteFeedback(
  messageId: string,
  thumb: 'up' | 'down',
  tasteEntities?: string[],
): Promise<FeedbackResponse> {
  const resp = await fetch(`${API_BASE}/chat/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message_id: messageId, thumb, taste_entities: tasteEntities || [] }),
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.detail || `Feedback failed: ${resp.status}`)
  }
  return await resp.json()
}

// ===== Ablation Comparison (P2) =====
export interface AblationRationale {
  name: string
  cultural_match: string
  safety_validation: string
  passes: boolean
}
export interface AblationVariantResult {
  top_pick?: string | null
  has_cultural_match?: boolean
  cultural_grounding?: string
  data_source?: string
  rationale?: AblationRationale[]
}
export interface AblationComparisonItem {
  case: { query: string; cultural_likes: string[]; location: string; constraints: Record<string, boolean> }
  variant_a: AblationVariantResult
  variant_b: AblationVariantResult
}
export interface AblationComparisonResponse {
  timestamp: number
  cases: unknown[]
  variants: Record<string, AblationVariantResult[]>
  comparison: AblationComparisonItem[]
  data_source: string
}

export async function fetchAblationComparison(): Promise<AblationComparisonResponse> {
  const resp = await fetch(`${API_BASE}/ablation/comparison`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!resp.ok) throw new Error(`Ablation comparison failed: ${resp.status}`)
  return await resp.json()
}