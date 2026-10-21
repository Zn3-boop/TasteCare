export type Tab = 'tastecare' | 'recommend' | 'discover' | 'agent' | 'evidence' | 'community'

export const TABS: [Tab, string, string][] = [
  ['tastecare', '🍽️ Senior Dining', 'The headline demo: Qloo culture match + senior health safety screening (low sodium / easy-to-chew / medication-aware)'],
  ['discover', '🌌 Taste Bridge', 'Cross-domain taste transfer — the signature demo: one anchor → music · dining · film · fashion · travel'],
  ['evidence', '🧠 Why Qloo?', 'Why Qloo + ablation — the culture-graph capability proof'],
  ['agent', '💬 Agent', 'Conversational agent — just type what you want; it parses your tastes and grounds answers in Qloo'],
  ['recommend', '💡 Tastes', 'Explore more cultural picks: All | Music | Film | Dining | Fashion | Travel | Podcast | Books (pure affinity, no health filter)'],
  ['community', '👥 Community', 'Find people with the same taste & needs'],
]

/** The signature cross-domain tab — gets a featured glow in the top nav. */
export const FEATURED_TAB: Tab = 'discover'