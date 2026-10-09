import { useEffect, useRef, useState } from 'react'
import { SeniorDiningTab } from './components/tabs/SeniorDiningTab'
import { TastesTab } from './components/tabs/TastesTab'
import { DiscoverTab } from './components/tabs/DiscoverTab'
import { AgentTab } from './components/tabs/AgentTab'
import { WhyQlooTab } from './components/tabs/WhyQlooTab'
import { AblationTab } from './components/tabs/AblationTab'
import { Header } from './components/Header'
import { TabNav } from './components/TabNav'
import { type Tab } from './components/tabs'
import { Footer } from './components/Footer'
import { DisclaimerBanner } from './components/DisclaimerBanner'
import { ToastProvider } from './components/ToastProvider'
import { useQlooStatus } from './hooks/useQlooStatus'
import { useTasteCare } from './hooks/useTasteCare'
import { useTastes } from './hooks/useTastes'
import { useChatAgent } from './hooks/useChatAgent'

function AppShell() {
  const [tab, setTab] = useState<Tab>('tastecare')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [whyMode, setWhyMode] = useState<'qloo' | 'generic'>('qloo')
  const autoFiredRef = useRef(false)

  const { status } = useQlooStatus()
  const tasteCare = useTasteCare({ setLoading, setError })
  const tastes = useTastes({ setLoading, setError })
  const chat = useChatAgent({ setLoading, setError })

  useEffect(() => {
    chat.chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.chatEndRef, chat.chatHistory])

  // G5: cold-start — auto-fire the default Maria query once Qloo is connected.
  useEffect(() => {
    if (status?.enabled && !tasteCare.tcSearched && !autoFiredRef.current && tab === 'tastecare') {
      autoFiredRef.current = true
      void tasteCare.doTasteCare()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, tab, tasteCare.tcSearched])

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '20px 24px', minHeight: '100vh' }}>
      <Header status={status} />
      <DisclaimerBanner />
      <TabNav tab={tab} setTab={setTab} />

      {error && <div style={{ color: '#F87171', fontSize: 12, marginBottom: 12, textAlign: 'center', padding: '8px 16px', borderRadius: 8, background: '#7F1D1D22', border: '1px solid #7F1D1D44' }}>{error}</div>}

      {tab === 'tastecare' && (
        <SeniorDiningTab
          tcLikes={tasteCare.tcLikes}
          setTcLikes={tasteCare.setTcLikes}
          tcLocation={tasteCare.tcLocation}
          setTcLocation={tasteCare.setTcLocation}
          tcConstraints={tasteCare.tcConstraints}
          setTcConstraints={tasteCare.setTcConstraints}
          tcResult={tasteCare.tcResult}
          tcSearched={tasteCare.tcSearched}
          doTasteCare={() => void tasteCare.doTasteCare()}
          activeConstraintCount={tasteCare.activeConstraintCount}
          activeConstraintLabels={tasteCare.activeConstraintLabels}
          loading={loading}
          searchHistory={tasteCare.tcHistory}
          onPickHistory={(v) => tasteCare.setTcLikes(v)}
          onClearHistory={tasteCare.clearTcHistory}
        />
      )}

      {tab === 'recommend' && (
        <TastesTab
          domain={tastes.domain}
          setDomain={tastes.setDomain}
          query={tastes.query}
          setQuery={tastes.setQuery}
          results={tastes.results}
          seeds={tastes.seeds}
          setSeeds={tastes.setSeeds}
          recs={tastes.recs}
          doSearch={() => void tastes.doSearch()}
          doRecommend={() => void tastes.doRecommend()}
          loading={loading}
        />
      )}

      {tab === 'discover' && (
        <DiscoverTab
          seeds={tastes.seeds}
          setSeeds={tastes.setSeeds}
          crossRes={tastes.crossRes}
          doCross={() => void tastes.doCross()}
          loading={loading}
          qlooEnabled={!!status?.enabled}
        />
      )}

      {tab === 'agent' && (
        <AgentTab
          chatMsg={chat.chatMsg}
          setChatMsg={chat.setChatMsg}
          chatHistory={chat.chatHistory}
          setChatHistory={chat.setChatHistory}
          chatEndRef={chat.chatEndRef}
          doChat={() => void chat.doChat()}
          onFeedback={chat.handleFeedback}
          loading={loading}
          onOpenDiscover={() => setTab('discover')}
        />
      )}

      {tab === 'why' && (
        <WhyQlooTab
          whyMode={whyMode}
          setWhyMode={setWhyMode}
          tcResult={tasteCare.tcResult}
        />
      )}

      {tab === 'ablation' && <AblationTab />}

      <Footer />
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
