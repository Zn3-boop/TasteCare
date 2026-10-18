// Shared constants for the TasteCare web demo.
// Kept in their own module so the tab components stay presentational.

export const DOMAINS = [
  { key: '', label: 'All' },
  { key: 'music', label: '🎵 Music' },
  { key: 'film', label: '🎬 Film' },
  { key: 'dining', label: '🍽️ Dining' },
  { key: 'fashion', label: '👗 Fashion' },
  { key: 'travel', label: '✈️ Travel' },
  { key: 'podcast', label: '🎙️ Podcast' },
  { key: 'book', label: '📚 Books' },
]

export const DOMAIN_COLORS: Record<string, string> = {
  music: '#1DB954', film: '#E50914', dining: '#FF6B35',
  fashion: '#C77DFF', travel: '#00B4D8', podcast: '#FFB703', book: '#8B5CF6',
}

export const SENIOR_PERSONA = {
  likes: 'Frank Sinatra, Bob Dylan, Italian cuisine, Jazz, Classic Hollywood films',
  location: 'New York',
}

export const CONSTRAINT_META: { key: string; label: string; hint: string; icon: string }[] = [
  { key: 'soft_chewable', label: 'Easy to Chew', hint: 'Soft / tender textures for chewing difficulty', icon: '🦷' },
  { key: 'low_sodium', label: 'Low Sodium', hint: 'Heart-healthy, lowers blood-pressure risk', icon: '❤️' },
  { key: 'low_sugar', label: 'Low Sugar', hint: 'Blood-sugar friendly (diabetes care)', icon: '🩸' },
  { key: 'medications', label: 'Medication-Aware', hint: 'Avoids ingredients that interfere with common meds', icon: '💊' },
]

export const GENERIC_LLM_RESULTS = [
  { name: 'Grilled Chicken Breast', reason: 'Common "healthy" default — ignores that she loves Italian flavors' },
  { name: 'Steamed Vegetables', reason: 'Nutritionally correct, culturally tone-deaf' },
  { name: 'Oatmeal with Berries', reason: 'A breakfast suggestion for dinner time' },
  { name: 'Salmon and Rice', reason: 'Generic "senior meal" — no connection to Sinatra-era New York Italian dining' },
]

export const DISCLAIMER_EN = 'This application provides culturally-grounded dining recommendations and general dietary screening only — it does not constitute medical advice. If medications are involved (e.g., anticoagulants, blood pressure, or diabetes drugs), please confirm specific dish suitability with your physician or pharmacist before deciding.'

// Example query seeds shown when the Taste Bridge has no data yet.
export const EMPTY_STATE_EXAMPLES = [
  'Italian cuisine',
  'Jazz music',
  'Frank Sinatra',
  'Bob Dylan',
  'Classic Hollywood films',
  'Tom Yum soup',
  'Matcha',
  'Avocado',
]

// Scenario prompt buttons for Senior Dining tab
export const SENIOR_SCENARIO_PROMPTS = [
  'My 80-year-old dad loves Frank Sinatra and Italian food but needs low-sodium meals. What would he enjoy near New York?',
  'My grandmother grew up in Little Italy, loves jazz and old Hollywood. She has diabetes and can\'t eat hard foods.',
  'Help my 75-year-old mom who loves Bob Dylan and folk music find soft, healthy meals in Chicago.',
]

// Scenario prompt buttons for Agent tab
export const AGENT_SCENARIO_PROMPTS = [
  '"I love Christopher Nolan films and Chicago blues — where should I eat in New York and what should I wear?"',
  '"My 82-year-old father loves Frank Sinatra, Italian food, and old movies. He has hypertension and poor dentition. What would he enjoy eating near Boston?"',
  '"Recommend dinner for Maria, who has hypertension, poor dentition, and prefers light Jiangnan home cooking."',
]
// Domain load indicators rendered while cross-domain requests are in flight.
export type DomainStatus = 'done' | 'loading' | 'idle'
export const DOMAIN_LIST = ['music', 'film', 'dining', 'fashion', 'travel', 'podcast', 'book'] as const
export type DomainKey = typeof DOMAIN_LIST[number]

// G3: friendly names/icons for active health constraints on TasteCare cards.
export const EN_CONSTRAINT_LABEL: Record<string, string> = {
  low_sodium: 'Low Sodium',
  low_sugar: 'Low Sugar',
  soft_chewable: 'Easy to Chew',
  medications: 'Medication-screened',
}
export const EN_CONSTRAINT_ICON: Record<string, string> = {
  low_sodium: '❤️', low_sugar: '🩸', soft_chewable: '🦷', medications: '💊',
}
// ===== Taste Bridge =====
// Preview constellation data, used ONLY when Qloo is NOT connected so the
// cross-domain graph is still explorable during a no-key demo. The `why`
// strings are faithful, semantically-grounded relationships (Sinatra really did
// collaborate with Ella Fitzgerald and Basie, star in "Guys and Dolls", come
// from a NY Italian tavern culture, and popularize the fedora). We NEVER present
// this as live Qloo output — the UI labels it "demo preview" (dataSource:
// 'preview') whenever the live cross-domain results are unavailable, and the
// score_fit-style philosophy is that a clearly-labelled fallback beats a fake
// live claim.

export type BridgeNodeData = { name: string; why: string; popularity: number }

export const PREVIEW_BRIDGE: Record<string, BridgeNodeData[]> = {
  music: [
    { name: 'Ella Fitzgerald', popularity: 0.93, why: 'A frequent Sinatra collaborator and the "First Lady of Song" — they shared bands, albums and the swing-era stage.' },
    { name: 'Count Basie Orchestra', popularity: 0.9, why: "Sinatra fronted Basie's band and recorded the live classic \"Sinatra at the Sands\" with them." },
    { name: 'Tony Bennett', popularity: 0.87, why: 'An heir of the crooner lineage whose phrasing descends directly from Sinatra.' },
  ],
  dining: [
    { name: 'Jazz-era Supper Club', popularity: 0.92, why: 'Sinatra was forged in jazz supper clubs — live trio, dim light, Italian-American fare — mirroring his Little Italy upbringing.' },
    { name: 'Old-school Trattoria', popularity: 0.9, why: 'His parents ran a tavern; Italian-American red-sauce table culture is a cornerstone of his taste.' },
    { name: 'Hotel Cocktail Lounge', popularity: 0.84, why: 'Post-war lounge culture he helped define: cocktails with intimate live music.' },
  ],
  film: [
    { name: 'Guys and Dolls', popularity: 0.91, why: 'Sinatra starred in this 1955 musical at the peak of his crossover film fame.' },
    { name: 'On the Waterfront', popularity: 0.85, why: 'An iconic New York drama Sinatra fought to appear in — classic Hollywood at its best.' },
    { name: 'Some Came Running', popularity: 0.8, why: "A Sinatra vehicle blending the Rat Pack era's glamour with a searching dramatic turn." },
  ],
  travel: [
    { name: 'Little Italy, NYC', popularity: 0.9, why: 'Maria, like Sinatra, grew up with Italian-American New York culture — the emotional anchor of the whole graph.' },
    { name: 'Atlantic City, NJ', popularity: 0.82, why: 'Sinatra helped build its entertainment industry and was a regular headline act on the boardwalk.' },
    { name: 'Miami Beach, FL', popularity: 0.79, why: 'A perennial Rat Pack stage-city, mixing music, film glamour and resort dining.' },
  ],
  fashion: [
    { name: 'Vintage Italian Tailoring', popularity: 0.86, why: "Sinatra's signature two-piece, high-waisted Italian-cut suits set the mid-century look." },
    { name: 'Classic Fedora', popularity: 0.84, why: "The fedora is practically Sinatra's emblem — film noir and jazz stage in one silhouette." },
    { name: 'Cuff-linked Dress Shirt', popularity: 0.78, why: 'Evening Rat Pack wear: crisp, tailored, understated glamour.' },
  ],
  podcast: [
    { name: 'Rat Pack Radio Shows', popularity: 0.85, why: "Sinatra's live radio broadcasts defined the 1940s-50s podcast-like entertainment format." },
    { name: 'Jazz Talk Radio', popularity: 0.79, why: 'The conversational jazz format mirrors the intimacy of supper club performances.' },
  ],
  book: [
    { name: 'The Great Gatsby', popularity: 0.82, why: 'The Jazz Age novel Sinatra embodied — pre-war American glamour and melancholy.' },
    { name: 'On the Waterfront Script Books', popularity: 0.71, why: "Sinatra's iconic role cemented New York dockworker literature in the cultural canon." },
  ],
}

export const BRIDGE_DOMAIN_ORDER = ['music', 'dining', 'film', 'travel', 'fashion', 'podcast', 'book']

// Maria's cross-domain journey: FIXED persona + FIXED path skeleton + FIXED seeds.
// The CONTENT of each step is DYNAMIC — live Qloo cross-domain results when a key
// is set, otherwise the clearly-labelled PREVIEW_BRIDGE pool. This is deliberately
// half-dynamic: the demo is always controllable (never a runaway free-running
// chain) and never fakes a live claim (without a key it says "demo preview").
export const MARIA_JOURNEY: { domain: string; icon: string; label: string; seed: string }[] = [
  { domain: 'music', icon: '🎵', label: 'Maria loves', seed: 'Frank Sinatra' },
  { domain: 'dining', icon: '🍽️', label: '…dines at', seed: 'Jazz-era Supper Club' },
  { domain: 'film', icon: '🎬', label: '…watches', seed: 'Guys and Dolls' },
  { domain: 'travel', icon: '✈️', label: '…travels to', seed: 'Little Italy, NYC' },
  { domain: 'fashion', icon: '👗', label: '…wears', seed: 'Vintage Italian Tailoring' },
]

export const BRIDGE_LEGEND = [
  { domain: 'music', label: 'Music' },
  { domain: 'dining', label: 'Dining' },
  { domain: 'film', label: 'Film' },
  { domain: 'travel', label: 'Travel' },
  { domain: 'fashion', label: 'Fashion' },
  { domain: 'podcast', label: 'Podcast' },
  { domain: 'book', label: 'Book' },
]
