export type Tab = 'tastecare' | 'recommend' | 'discover' | 'agent' | 'why' | 'ablation' | 'community'

export const TABS: [Tab, string, string][] = [
  ['tastecare', '🍽️ Senior Dining', 'The headline demo'],
  ['discover', '🌌 Taste Bridge', 'Cross-domain discovery: one taste → music · dining · film · fashion · travel'],
  ['agent', '💬 Agent', 'Chat with cultural intelligence'],
  ['recommend', '💡 Tastes', 'Search & taste-based recs'],
  ['why', '⚠️ Why Qloo', 'See the difference'],
  ['ablation', '🧪 Ablation', 'Variant A vs B comparison'],
  ['community', '👥 Community', 'Find people with the same taste & needs'],
]

/** The signature cross-domain tab — gets a featured glow in the top nav. */
export const FEATURED_TAB: Tab = 'discover'