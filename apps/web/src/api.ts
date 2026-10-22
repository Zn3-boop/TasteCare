// The backend already prefixes business APIs with /api/v1 (/ and /health are liveness paths, no version).
export const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '') + '/api/v1'

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

export interface EntityDetails {
  id: string
  name: string
  type: string
  domain?: string
  tags?: string[]
  description?: string
  popularity?: number
}

export async function getEntityDetails(entityId: string): Promise<EntityDetails | null> {
  const resp = await fetch(`${API_BASE}/qloo/entity/${encodeURIComponent(entityId)}`)
  if (!resp.ok) return null
  return await resp.json()
}

export async function getTasteProfile(entityIds: string[]) {
  const resp = await fetch(`${API_BASE}/qloo/taste-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_ids: entityIds }),
  })
  if (!resp.ok) throw new Error(`Taste profile failed: ${resp.status}`)
  return await resp.json()
}

export async function getSimilarity(entityIds: string[], targetType?: string) {
  const resp = await fetch(`${API_BASE}/qloo/similarity`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_ids: entityIds, target_type: targetType }),
  })
  if (!resp.ok) throw new Error(`Similarity failed: ${resp.status}`)
  return await resp.json()
}
export interface QlooEntityDetail {
  entity_id?: string
  name?: string
  type?: string
  domain?: string
  image?: string | null
  popularity?: number | null
  /** Real Qloo match score (0..1) resolved for this anchor — passthrough only,
      never fabricated; omitted when Qloo returned no score. Rendered by the
      grounding panel as the "92%" proof that this entity came from the taste graph. */
  score?: number | null
  tags?: string[]
  description?: string | null
}
export interface ChatAgentResponse {
  reply: string
  taste_entities?: string[]
  taste_data_source?: string
  qloo_context?: unknown
  tool_calls?: unknown[]
  // Structured grounding evidence for the Agent tab's Grounding panel:
  // resolved anchor entities + taste-graph recommendations (with images) and
  // the location extracted from the user's message ("in New York").
  taste_entity_details?: QlooEntityDetail[]
  taste_recommendations?: QlooEntityDetail[]
  taste_location?: string | null
}

export interface PersonaChatContext {
  /** Display name of the active persona (Maria / custom). */
  personaName?: string | null
  /** Comma-separated taste anchors ("Frank Sinatra, Jazz, Italian cuisine"). */
  personaAnchors?: string | null
  /**
   * 'locked' = pure profile mode: the backend grounds ONLY on the persona's
   * saved anchors (skips message-derived likes AND the fixed core anchors), so
   * an off-profile question never invents new cultural entities. 'mixed' (the
   * default) keeps free exploration: persona + message likes + core anchors.
   */
  personaMode?: 'locked' | 'mixed' | null
}

export async function chatWithAgent(message: string, persona?: PersonaChatContext): Promise<ChatAgentResponse> {
  const resp = await fetch(`${API_BASE}/chat/agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      persona_name: persona?.personaName ?? null,
      persona_anchors: persona?.personaAnchors ?? '',
      persona_mode: persona?.personaMode ?? 'mixed',
    }),
  })
  if (!resp.ok) throw new Error(`Chat failed: ${resp.status}`)
  return await resp.json()
}

// Ablation: chat WITHOUT Qloo cultural grounding (for comparison)
export async function chatWithoutQloo(message: string, persona?: PersonaChatContext): Promise<ChatAgentResponse> {
  const resp = await fetch(`${API_BASE}/chat/agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      disable_qloo: true,
      persona_name: persona?.personaName ?? null,
      persona_anchors: persona?.personaAnchors ?? '',
      persona_mode: persona?.personaMode ?? 'mixed',
    }),
  })
  if (!resp.ok) throw new Error(`Chat without Qloo failed: ${resp.status}`)
  return await resp.json()
}
// ===== TasteCare (senior dining, Qloo-grounded) =====
export interface UsdaNutrition {
  source: 'usda-fdc'
  matched: string
  per_100g: { sodium_mg: number; protein_g: number; fiber_g: number; kcal: number }
  texture: 'soft' | 'medium' | 'hard'
}

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
  health?: { passes: boolean; labels: string[]; warnings: string[]; usda?: UsdaNutrition | null }
  /** Structured health-screening bucket from the backend: "pass" = fully meets active
   * health constraints; "review" = culturally well-matched but some menu items may
   * exceed them. Optional so old responses fall back to `health.passes`. */
  screening?: 'pass' | 'review'
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
  data_source?: 'live' | 'preview' | string
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
  /** Real TasteCare pipeline output (resolved anchors + health-screening summary) for live Variant B. */
  grounding_note?: string
  data_source?: string
  rationale?: AblationRationale[]
}
export interface AblationRowDiff {
  /** True when Qloo moved the #1 pick vs the rule-based list. */
  top_changed: boolean
  /** How many restaurants the top-4 lists share (0-4). */
  top4_overlap: number
  /** Restaurants Qloo brought into the top-4 that rules didn't. */
  b_only: string[]
}
export interface AblationComparisonItem {
  case: { query: string; cultural_likes: string[]; location: string; constraints: Record<string, boolean> }
  variant_a: AblationVariantResult
  variant_b: AblationVariantResult
  diff?: AblationRowDiff
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

// ===== Community matching (Qloo-powered, mutual opt-in) =====
export interface CommunityMatch {
  peer_id: string
  name: string
  tagline: string
  location?: string
  cultural_likes: string[]
  constraints: Record<string, boolean>
  shared_anchors: string[]
  shared_constraints: string[]
  affinity: number
}

export interface CommunityMatchResponse {
  matches: CommunityMatch[]
  user_likes_resolved: { name: string; domain: string }[]
  data_source: 'live' | 'preview' | string
}

export async function communityMatch(input: {
  cultural_likes: string[]
  location?: string
  constraints?: Record<string, boolean>
  limit?: number
}): Promise<CommunityMatchResponse> {
  const resp = await fetch(`${API_BASE}/community/match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      cultural_likes: input.cultural_likes,
      location: input.location || undefined,
      constraints: input.constraints || {},
      limit: input.limit || 5,
    }),
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.detail || `Community match failed: ${resp.status}`)
  }
  return await resp.json()
}

export interface CommunityConnectResponse {
  ok: boolean
  peer_id: string
  status: string
  message: string
  error?: string | null
}

export async function communityConnect(peerId: string): Promise<CommunityConnectResponse> {
  const resp = await fetch(`${API_BASE}/community/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ peer_id: peerId }),
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.detail || `Connect failed: ${resp.status}`)
  }
  return await resp.json()
}

export async function communityAccept(peerId: string): Promise<CommunityConnectResponse> {
  const resp = await fetch(`${API_BASE}/community/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ peer_id: peerId }),
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.detail || `Accept failed: ${resp.status}`)
  }
  return await resp.json()
}

export async function communityConnections(): Promise<{ connections: { peer_id: string; peer_name: string; status: string }[] }> {
  const resp = await fetch(`${API_BASE}/community/connections`)
  if (!resp.ok) return { connections: [] }
  return await resp.json()
}