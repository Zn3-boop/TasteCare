import { useState, useEffect, useRef } from 'react'
import {
  qlooSearch, qlooRecommend, qlooCrossDomain, qlooStatus, chatWithAgent,
  tasteCareRecommend, sendTasteFeedback,
  type QlooEntity, type TasteCareResult,
} from './api'
import { SENIOR_PERSONA, CONSTRAINT_META } from './constants'
import { sx } from './components/ui'
import { SeniorDiningTab } from './components/tabs/SeniorDiningTab'
import { TastesTab } from './components/tabs/TastesTab'
import { DiscoverTab } from './components/tabs/DiscoverTab'
import { AgentTab } from './components/tabs/AgentTab'
import { WhyQlooTab } from './components/tabs/WhyQlooTab'
import { AblationTab } from './components/tabs/AblationTab'
import { DISCLAIMER_EN } from './constants'
import { ToastProvider, useToast } from './hooks/useToast'
import { useSearchHistory } from './hooks/useSearchHistory'

type ChatMsg = {
  id: string
  role: string
  text: string
  tasteEntities?: string[]
  tasteDataSource?: string
  qlooContext?: unknown
  feedback?: 'up' | 'down' | null
}

type Tab = 'tastecare' | 'recommend' | 'discover' | 'agent' | 'why' | 'ablation'

const TABS: [Tab, string, string][] = [
  ['tastecare', '🍽️ Senior Dining', 'The headline demo'],
  ['agent', '💬 Agent', 'Chat with cultural intelligence'],
  ['recommend', '💡 Tastes', 'Search & taste-based recs'],
  ['discover', '🔗 Discover', 'Cross-domain bridges'],
  ['why', '⚠️ Why Qloo', 'See the difference'],
  ['ablation', '🧪 Ablation', 'Variant A vs B comparison'],
]

function AppShell() {
  const [status, setStatus] = useState<{ enabled: boolean; api_key_set: boolean } | null>(null)
  const [tab, setTab] = useState<Tab>('tastecare')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [tcLikes, setTcLikes] = useState(SENIOR_PERSONA.likes)
  const [tcLocation, setTcLocation] = useState(SENIOR_PERSONA.location)
  const [tcConstraints, setTcConstraints] = useState<Record<string, boolean>>({ soft_chewable: true, low_sodium: true, low_sugar: false, medications: false })
  const [tcResult, setTcResult] = useState<TasteCareResult | null>(null)
  const [tcSearched, setTcSearched] = useState(false)

  const [domain, setDomain] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<QlooEntity[]>([])
  const [seeds, setSeeds] = useState<QlooEntity[]>([])
  const [recs, setRecs] = useState<QlooEntity[]>([])
  const [crossRes, setCrossRes] = useState<Record<string, QlooEntity[]>>({})

  const [chatMsg, setChatMsg] = useState('')
  const [chatHistory, setChatHistory] = useState<ChatMsg[]>([])
  const chatEndRef = useRef<HTMLDivElement>(null)
  const autoFiredRef = useRef(false)

  const [whyMode, setWhyMode] = useState<'qloo' | 'generic'>('qloo')

  const toast = useToast()
  const { history: tcHistory, add: addTcHistory, clear: clearTcHistory } = useSearchHistory('tasteCareHistory', 6)

  useEffect(() => { qlooStatus().then(setStatus) }, [])
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [chatHistory])

  const doTasteCare = async () => {
    const likes = tcLikes.split(/[,，\n]/).map(s => s.trim()).filter(Boolean)
    if (!likes.length) { setError('Enter at least one cultural interest (artist, cuisine, film…)'); return }
    setLoading(true); setError(''); setTcSearched(true)
    try {
      const res = await tasteCareRecommend({ cultural_likes: likes, location: tcLocation, constraints: tcConstraints, take: 12 })
      setTcResult(res)
      addTcHistory(likes.join(', '))
      toast('TasteCare suggestions ready — grounded in Qloo taste graph', 'success')
    }
    catch (e) { setError(String(e)); setTcResult(null); toast(String(e), 'error') }
    setLoading(false)
  }

  // G5: cold-start — auto-fire the default Maria query once Qloo is connected.
  useEffect(() => {
    if (status?.enabled && !tcSearched && !autoFiredRef.current && tab === 'tastecare') {
      autoFiredRef.current = true
      void doTasteCare()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, tab, tcSearched])

  const doSearch = async () => {
    if (!query.trim()) return
    setLoading(true); setError('')
    try { setResults(await qlooSearch(query, domain || undefined, 15)) } catch (e) { setError(String(e)) }
    setLoading(false)
  }

  const doRecommend = async () => {
    if (!seeds.length) return
    setLoading(true); setError('')
    try { const r = await qlooRecommend(seeds.map(s => s.id), domain || undefined, 12); setRecs(r.recommendations || []) } catch (e) { setError(String(e)) }
    setLoading(false)
  }

  const doCross = async () => {
    if (!seeds.length) return
    setLoading(true); setError('')
    try { setCrossRes((await qlooCrossDomain(seeds.map(s => s.id))).results || {}) } catch (e) { setError(String(e)) }
    setLoading(false)
  }

  const doChat = async () => {
    if (!chatMsg.trim()) return
    setLoading(true); setError('')
    setChatHistory(h => [...h, { id: crypto.randomUUID(), role: 'user', text: chatMsg }])
    try {
      const r = await chatWithAgent(chatMsg)
      setChatHistory(h => [...h, {
        id: crypto.randomUUID(),
        role: 'agent',
        text: r.reply || '',
        tasteEntities: r.taste_entities,
        tasteDataSource: r.taste_data_source,
        qlooContext: r.qloo_context,
        feedback: null,
      }])
    } catch (e) { setError(String(e)) }
    setChatMsg(''); setLoading(false)
  }

  const handleFeedback = async (messageId: string, thumb: 'up' | 'down') => {
    const target = chatHistory.find(m => m.id === messageId)
    if (!target) return
    setChatHistory(h => h.map(m => m.id === messageId ? { ...m, feedback: thumb } : m))
    try {
      const res = await sendTasteFeedback(messageId, thumb, target.tasteEntities)
      const hint = res.data_source === 'preview'
        ? 'Feedback saved to local preview memory'
        : 'Feedback saved to Qloo taste profile'
      toast(`${thumb === 'up' ? '👍' : '👎'} ${hint}`, 'success')
    } catch (e) {
      setChatHistory(h => h.map(m => m.id === messageId ? { ...m, feedback: null } : m))
      toast(`Feedback failed: ${String(e)}`, 'error')
    }
  }

  const activeConstraintCount = Object.values(tcConstraints).filter(Boolean).length
  const activeConstraintLabels = CONSTRAINT_META.filter((m) => tcConstraints[m.key]).map((m) => m.label).join(', ')
return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '20px 24px', minHeight: '100vh' }}>
      <header style={{ textAlign: 'center', marginBottom: 28 }}>
        <div style={{ fontSize: 11, color: '#F5A623', letterSpacing: 3, textTransform: 'uppercase', fontWeight: 600 }}>Qloo × LLM Hackathon</div>
        <h1 style={{ fontSize: 32, fontWeight: 800, margin: '8px 0 4px', background: 'linear-gradient(135deg, #FF6B35, #F5A623)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          TasteCare
        </h1>
        <p style={{ fontSize: 15, color: '#9CA3AF', maxWidth: 600, margin: '0 auto', lineHeight: 1.6 }}>
          Culturally intelligent dining for seniors.<br />
          <strong style={{ color: '#E5E7EB' }}>Not "what's healthy" — what <em>this person</em> would actually love</strong>, filtered for their health reality.
        </p>
        <div style={{ marginTop: 12, display: 'flex', gap: 8, justifyContent: 'center', alignItems: 'center' }}>
          <span style={{ fontSize: 11, padding: '4px 12px', borderRadius: 8, background: status?.enabled ? '#065F46' : '#374151', color: status?.enabled ? '#6EE7B7' : '#9CA3AF', fontWeight: 600 }}>
            {status?.enabled ? '✅ Qloo Taste Graph Connected' : '🔌 Qloo Not Configured'}
          </span>
          <span style={{ fontSize: 10, color: '#6B7280' }}>250M+ entities</span>
        </div>
      </header>

      <div style={{ marginBottom: 20, padding: '10px 16px', borderRadius: 10, background: '#7F1D1D22', border: '1px solid #7F1D1D44' }}>
        <span style={{ fontSize: 11.5, color: '#FCA5A5', lineHeight: 1.5, display: 'block' }}>⚠️ {DISCLAIMER_EN}</span>
      </div>

      <nav style={{ display: 'flex', gap: 6, marginBottom: 24, justifyContent: 'center', flexWrap: 'wrap' }}>
        {TABS.map(([k, label, title]) => (
          <button key={k} onClick={() => setTab(k)} title={title} style={{ padding: '8px 18px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: tab === k ? 700 : 400, background: tab === k ? '#FF6B35' : '#1F2937', color: tab === k ? '#fff' : '#9CA3AF', transition: 'background 0.15s, color 0.15s', boxShadow: tab === k ? '0 2px 8px #FF6B3533' : 'none' }}>
            {label}
          </button>
        ))}
      </nav>

      {error && <div style={{ color: '#F87171', fontSize: 12, marginBottom: 12, textAlign: 'center', padding: '8px 16px', borderRadius: 8, background: '#7F1D1D22', border: '1px solid #7F1D1D44' }}>{error}</div>}

      {tab === 'tastecare' && (
        <SeniorDiningTab
          tcLikes={tcLikes}
          setTcLikes={setTcLikes}
          tcLocation={tcLocation}
          setTcLocation={setTcLocation}
          tcConstraints={tcConstraints}
          setTcConstraints={setTcConstraints}
          tcResult={tcResult}
          tcSearched={tcSearched}
          doTasteCare={() => void doTasteCare()}
          activeConstraintCount={activeConstraintCount}
          activeConstraintLabels={activeConstraintLabels}
          loading={loading}
          searchHistory={tcHistory}
          onPickHistory={(v) => setTcLikes(v)}
          onClearHistory={clearTcHistory}
        />
      )}

      {tab === 'recommend' && (
        <TastesTab
          domain={domain}
          setDomain={setDomain}
          query={query}
          setQuery={setQuery}
          results={results}
          setResults={setResults}
          seeds={seeds}
          setSeeds={setSeeds}
          recs={recs}
          setRecs={setRecs}
          doSearch={() => void doSearch()}
          doRecommend={() => void doRecommend()}
          loading={loading}
        />
      )}

      {tab === 'discover' && (
        <DiscoverTab
          seeds={seeds}
          setSeeds={setSeeds}
          crossRes={crossRes}
          doCross={() => void doCross()}
          loading={loading}
          qlooEnabled={!!status?.enabled}
        />
      )}

      {tab === 'agent' && (
        <AgentTab
          chatMsg={chatMsg}
          setChatMsg={setChatMsg}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          chatEndRef={chatEndRef}
          doChat={() => void doChat()}
          onFeedback={handleFeedback}
          loading={loading}
          onOpenDiscover={() => setTab('discover')}
        />
      )}

      {tab === 'why' && (
        <WhyQlooTab
          whyMode={whyMode}
          setWhyMode={setWhyMode}
          tcResult={tcResult}
        />
      )}

      {tab === 'ablation' && <AblationTab />}

      <footer style={{ marginTop: 48, textAlign: 'center', fontSize: 11, color: '#4B5563', paddingBottom: 24 }}>
        <p style={{ fontWeight: 600, color: '#6B7280' }}>TasteCare — Cultural Intelligence for Senior Dining</p>
        <p>Without Qloo's taste graph, this would be just another "healthy meal" list. Cultural intelligence is the difference between "technically functional" and "actually good."</p>
      </footer>
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <AppShell />
    </ToastProvider>
  )
}
