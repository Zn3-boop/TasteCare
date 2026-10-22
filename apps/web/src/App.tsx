import { useCallback, useEffect, useRef, useState } from 'react'
import { SeniorDiningTab } from './components/tabs/SeniorDiningTab'
import { TastesTab } from './components/tabs/TastesTab'
import { DiscoverTab } from './components/tabs/DiscoverTab'
import { AgentTab } from './components/tabs/AgentTab'
import { EvidenceTab } from './components/tabs/EvidenceTab'
import { CommunityTab } from './components/tabs/CommunityTab'
import { Header } from './components/Header'
import { TabNav } from './components/TabNav'
import { type Tab } from './components/tabs'
import { Footer } from './components/Footer'
import { DisclaimerBanner } from './components/DisclaimerBanner'
import { ToastProvider } from './components/ToastProvider'
import { A11yToolbar } from './components/A11yToolbar'
import { useQlooStatus } from './hooks/useQlooStatus'
import { useTasteCare } from './hooks/useTasteCare'
import { useTastes } from './hooks/useTastes'
import { useChatAgent } from './hooks/useChatAgent'
import { useCommunity } from './hooks/useCommunity'
import { usePersona, personaConstraintKeys } from './hooks/usePersona'
import { useToast } from './hooks/useToast'
import { PersonaPicker } from './components/PersonaPicker'
import { ErrorBoundary } from './components/ErrorBoundary'

// Tab state survives page reloads via the URL hash (#tab=discover): a judge who
// refreshes lands back on the tab they were viewing. Persona + custom profiles
// are persisted in localStorage (tastecare.persona.v1) so a refresh keeps the
// selected person AND their anchors, not just the screen position.
const TAB_KEYS: readonly Tab[] = ['tastecare', 'recommend', 'discover', 'agent', 'evidence', 'community']

function initialTab(): Tab {
  const m = window.location.hash.match(/^#tab=([a-z]+)$/)
  return m && (TAB_KEYS as readonly string[]).includes(m[1]) ? (m[1] as Tab) : 'tastecare'
}

function AppShell() {
  const [tab, setTab] = useState<Tab>(initialTab)
  // Wrapped tab setter: also syncs the URL hash (replaceState keeps history clean);
  // the hashchange listener below makes back/forward buttons follow the same tab.
  const goTab = (t: Tab) => {
    setTab(t)
    try { window.history.replaceState(null, '', `#tab=${t}`) } catch { /* best-effort */ }
  }
  const [loading, setLoadingRaw] = useState(false)
  const [error, setError] = useState('')
  // Reference-counted setLoading: several async flows can run at once (cross-domain
  // preheat, auto-fire tastecare, persona switch, agent chat). A plain boolean setter
  // would flip `loading` on every completion, thrashing QlooStatusStrip's DOM
  // structure — under React 19 StrictMode that thrash desynced React's virtual tree
  // from the real DOM ("removeChild: node is not a child"). With the counter only
  // the FIRST caller turns loading ON and the LAST caller turns it OFF, so the strip
  // transitions exactly once. All Busy callers pair setLoading(true)/setLoading(false).
  const loadingCountRef = useRef(0)
  const setLoading = useCallback((v: boolean) => {
    loadingCountRef.current = Math.max(0, loadingCountRef.current + (v ? 1 : -1))
    setLoadingRaw(loadingCountRef.current > 0)
  }, [])
  const [whyMode, setWhyMode] = useState<'qloo' | 'generic'>('qloo')
  const autoFiredRef = useRef(false)
  const crossFiredRef = useRef(false)

  const { status } = useQlooStatus()
  const persona = usePersona()
  const toast = useToast()
  const tasteCare = useTasteCare({ setLoading, setError })
  const tastes = useTastes({ setLoading, setError })

  // ---- Agent tab persona binding ------------------------------
  // `agentBoundId` = null → the agent follows the GLOBAL current persona.
  // A non-null id pins the agent to a specific person (or the user clicks
  // "use only my message tastes" → we pass an empty anchors string so the
  // backend grounds ONLY on explicit likes in the message).
  const [agentBoundId, setAgentBoundId] = useState<string | null>(null)
  // Profile-lock switch for the Agent tab: when ON the backend grounds the
  // Qloo seeds ONLY on the current persona's saved anchors (no message-derived
  // likes, no fixed core anchors). Default OFF keeps free exploration.
  const [agentLocked, setAgentLocked] = useState(false)
  const bound = agentBoundId && agentBoundId !== 'unbound' ? persona.all.find(p => p.id === agentBoundId) || null : null
  // 'unbound' → no persona at all: send an empty name/anchors so the backend
  // grounds only on explicit likes inside the message + stored 👍 feedback.
  const effectiveName = agentBoundId === 'unbound' ? '' : (bound ? bound.name : persona.current.name)
  const effectiveAnchors = agentBoundId === 'unbound' ? '' : (bound ? bound.taste_anchors : persona.current.taste_anchors)

  const chat = useChatAgent({
    setLoading,
    setError,
    personaName: effectiveName,
    personaAnchors: effectiveAnchors,
    // Locking only makes sense when a persona profile is actually supplying
    // anchors — with 'unbound' (empty anchors) locked would leave the backend
    // with an empty seed list.
    personaMode: agentLocked && effectiveAnchors ? 'locked' : 'mixed',
    // Agent-resolved cultural entities ALSO feed the Taste Bridge (Discover),
    // not just this tab's transcript — so anything the agent grounds on (bound
    // persona anchors AND message tastes) shows up on the shared constellation.
    onTasteEntities: (names) => {
      if (!names?.length) return
      const anchors = names
        .map(n => (typeof n === 'string' ? n : String(n)).trim())
        .filter(Boolean)
        .map(name => ({ id: `seed-${name}`, name, type: 'taste' as const, domain: '' as const }))
      if (!anchors.length) return
      tastes.setSeeds(prev => {
        const seen = new Set(prev.map(s => s.name.toLowerCase()))
        return [...anchors.filter(a => !seen.has(a.name.toLowerCase())), ...prev]
      })
      if (status?.enabled) void tastes.doCrossFrom(anchors)
    },
  })
  const community = useCommunity()

  useEffect(() => {
    chat.chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.chatEndRef, chat.chatHistory])

  // Back / forward buttons and manual hash edits keep the active tab in sync.
  useEffect(() => {
    const onHash = () => {
      const m = window.location.hash.match(/^#tab=([a-z]+)$/)
      if (m && (TAB_KEYS as readonly string[]).includes(m[1])) setTab(m[1] as Tab)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // G5: cold-start — auto-fire the default Maria query once Qloo is connected.
  useEffect(() => {
    if (status?.enabled && !tasteCare.tcSearched && !autoFiredRef.current && tab === 'tastecare') {
      autoFiredRef.current = true
      void tasteCare.doTasteCare()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, tab, tasteCare.tcSearched])

  // "Try {Persona}'s Story" one-click demo — resets the form to the CURRENT global
  // persona (Maria preset or a custom person created in the PersonaPicker) and
  // fires the same TasteCare pipeline. Judges click once and watch the full
  // Qloo-grounded journey (grounding evidence + health screening + 👍 feedback).
  // The override is passed explicitly so the search uses the persona's profile
  // immediately (setState is async — without the override the stale input value
  // would be sent).
  const runPersonaStory = () => {
    goTab('tastecare')
    const p = persona.current
    const likes = p.taste_anchors || tasteCare.defaultLikes
    const location = p.location || tasteCare.defaultLocation
    const keys = personaConstraintKeys(p)
    const next = { soft_chewable: false, low_sodium: false, low_sugar: false, medications: false }
    keys.forEach(k => { next[k] = true })
    tasteCare.setTcLikes(likes)
    tasteCare.setTcLocation(location)
    tasteCare.setTcConstraints(next)
    autoFiredRef.current = true
    // Visible feedback so the one-click demo button never looks like a no-op —
    // even when the query just ran on cold boot with identical inputs, the reset
    // + toast + skeleton make it obvious something is happening.
    toast(`Loaded ${p.name}'s profile — re-running the Qloo-grounded recommendation`, 'info')
    syncBridgeFromLikes(likes)
    void tasteCare.doTasteCare({ likes, location })
  }

  // Taste Bridge follows the CURRENT taste input, not just the persona card's
  // FIRST-entered anchors. Whenever a search actually runs (manual edit + Find
  // Meals, or "Try {Persona}'s Story"), re-center the bridge seeds + cross-domain
  // results on the SAME likes that were just searched — so switching personas or
  // editing the taste box always refreshes the constellation (feedback: bridge
  // was stuck showing each persona card's first-entered anchors). An EMPTY likes
  // string also clears the bridge: never let a new persona inherit the previous
  // person's stale seeds/constellation.
  const syncBridgeFromLikes = (likesText: string) => {
    // Dedupe case-insensitively: a persona with "Jazz, jazz" must not create two
    // seeds with the same `seed-${name}` id (React 19 crashes on duplicate keys).
    const anchors = (likesText || '')
      .split(/[,，\n]/).map(s => s.trim()).filter(Boolean)
    const seen = new Set<string>()
    const uniqueAnchors = anchors.filter(n => { const k = n.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true })
      .map(name => ({ id: `seed-${name}`, name, type: 'taste' as const, domain: '' as const }))
    tastes.setSeeds(uniqueAnchors)
    if (uniqueAnchors.length) {
      if (status?.enabled) void tastes.doCrossFrom(uniqueAnchors)
    } else {
      tastes.setCrossRes({})
    }
  }

  // Cross-domain preheat — builds the Taste Bridge constellation on the first
  // screen as soon as Qloo connects (feedback #10: cross-domain discovery must be
  // front and center; without this the hero/Discover tab would need a manual
  // click before showing live data). useTastes resolves the 'seed-' placeholder
  // anchors to real Qloo entities before fetching.
  useEffect(() => {
    if (status?.enabled && !crossFiredRef.current) {
      crossFiredRef.current = true
      void tastes.doCross()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, tastes.doCross])

  // Global persona binding 终版契约②: the person selected in the top PersonaPicker
  // drives the whole app. When the profile changes (Maria preset or a custom
  // person), marshal its taste anchors / location / constraints into the Senior
  // Dining form so every tab talks about the SAME person. The persona id + custom
  // profiles persist in localStorage (see usePersona), so a page refresh falls
  // back into this same effect and re-populates the form with the saved person.
  //
  // STRICTMODE SAFETY (why this cannot use a plain "prev id" ref): React 19 in dev
  // runs every effect twice on first mount (setup → cleanup → setup). A naive
  // `prevPersonaIdRef.current === null` check breaks under that replay: the first
  // run writes the id into the ref, so the SECOND run already sees a non-null ref,
  // concludes "not booting", and re-marshals the profile over the user's persisted
  // constraint edits — exactly the "改了之后刷新又变回原来的" bug. Instead we track
  // "the persona id the form was LAST marshaled from" and skip when it MATCHES the
  // current id: idempotent, so the StrictMode replay is a no-op, while a real
  // person switch (id differs) still repopulates the form.
  //
  // SPLIT BEHAVIOUR: the form values (tcLikes/location/constraints) always resync
  // on a REAL switch (or a cold boot with no saved form), but the Taste Bridge
  // seeds ONLY reset when the persona id ACTUALLY changes — never on cold boot —
  // so anchors a judge added in the Tastes tab survive a page refresh and keep
  // rendering on the bridge (feedback: songs vanished on reload; they must
  // persist and still show on the constellation).
  const appliedPersonaIdRef = useRef<string | null>(null)
  useEffect(() => {
    const { id, taste_anchors, location } = persona.current
    // Idempotency guard: this exact persona was already marshaled into the form
    // (StrictMode replay, same-id re-render, or user re-selecting the same person)
    // → keep whatever the user currently has; never clobber manual edits.
    if (appliedPersonaIdRef.current === id) return
    // Maria is the DEFAULT person, not a no-op: switching BACK to Maria must
    // also re-center the app on Maria's anchors (feedback: profile habits must
    // flow into Tastes / Discover too — not just stay frozen on a custom person).
    const booting = appliedPersonaIdRef.current === null
    // Form values resync on a REAL persona switch, or on a cold boot when no
    // persisted Senior-Dining form exists. If the user manually edited the
    // constraint chips (or likes/location) and a refresh happens, the persisted
    // form wins — otherwise their edits would silently revert to the persona
    // profile (feedback: "健康约束改了之后刷新又变回原来的").
    if (!booting || !tasteCare.formHydrated) {
      tasteCare.setTcLikes(taste_anchors || tasteCare.defaultLikes)
      tasteCare.setTcLocation(location || tasteCare.defaultLocation)
      const keys = personaConstraintKeys(persona.current)
      const next = { soft_chewable: false, low_sodium: false, low_sugar: false, medications: false }
      keys.forEach(k => { next[k] = true })
      tasteCare.setTcConstraints(next)
    }
    // Persona-bound Taste Bridge: re-center seeds + re-cross ONLY on a real
    // persona switch (not the initial mount), preserving reload-persisted anchors.
    // EXCEPTION: if the persisted current person is a CUSTOM profile (not Maria),
    // a refresh must restore that person's OWN habits as the bridge seeds too —
    // otherwise the bridge shows Maria's Frank Sinatra default even though the
    // saved person was someone else (feedback: created-persona habits vanished).
    // Maria keeps the reload-persisted anchors (judge-added Tastes tab anchors).
    const changed = !booting
    const bootCustomPersona = booting && id !== 'maria'
    appliedPersonaIdRef.current = id
    if (changed || bootCustomPersona) {
      // 习惯爱好输入框已从新建人物表单移除（product decision），自定义人物
      // 不再有手填锚点。此时用人物名本身作为味觉桥中心锚点 —— 新建的人物
      // 永远进入星座（名字若是真实实体还能被 Qloo 实时解析出跨域数据）；
      // Maria 预置则继续用她的经典锚点。
      const anchorsText = (taste_anchors || '').trim()
      syncBridgeFromLikes(anchorsText || (id === 'maria' ? tasteCare.defaultLikes : persona.current.name))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persona.current.id])

  // ---- Tastes → persona single source of truth ---------------------------
  // Anchors gathered in Tastes / Discover (via taste seeds) are written back
  // into the BOUND custom person's profile, so the Agent tab grounds on the
  // SAME data the judge collected (persona-first seed priority on the backend).
  // Maria is read-only (her anchors are the preset); 'unbound' has no profile.
  useEffect(() => {
    const { id } = persona.current
    if (id === 'maria' || id === 'unbound') return
    const profile = persona.all.find(p => p.id === id)
    if (!profile) return
    const seedNames = tastes.seeds
      .map(s => s.name.trim())
      .filter(Boolean)
    if (!seedNames.length) return
    const existing = (profile.taste_anchors || '').split(/[,，、\n]/).map(s => s.trim()).filter(Boolean)
    const existingLower = new Set(existing.map(s => s.toLowerCase()))
    const merged = [...existing]
    let changed = false
    for (const n of seedNames) {
      if (existingLower.has(n.toLowerCase())) continue
      existingLower.add(n.toLowerCase())
      merged.push(n)
      changed = true
    }
    if (changed) {
      persona.update(id, { taste_anchors: merged.join(', ') })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persona.all, persona.current.id, tastes.seeds])

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '20px 24px', minHeight: '100vh' }}>
      <ErrorBoundary>
        <Header status={status} />
        <DisclaimerBanner />
        <TabNav tab={tab} setTab={goTab} />
        <PersonaPicker state={persona} />

      {error && <div style={{ color: '#F87171', fontSize: 12, marginBottom: 12, textAlign: 'center', padding: '8px 16px', borderRadius: 8, background: '#7F1D1D22', border: '1px solid #7F1D1D44' }}>{error}</div>}

      {/* .app-content marks the reading area — used by the A11y toolbar for
          "body-text only" scaling and read-aloud sentence highlighting. */}
      <main className="app-content">
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
          doTasteCare={() => { syncBridgeFromLikes(tasteCare.tcLikes); void tasteCare.doTasteCare() }}
          onRunMariaStory={runPersonaStory}
          activeConstraintCount={tasteCare.activeConstraintCount}
          activeConstraintLabels={tasteCare.activeConstraintLabels}
          loading={loading}
          searchHistory={tasteCare.tcHistory}
          onPickHistory={(v) => tasteCare.setTcLikes(v)}
          onClearHistory={tasteCare.clearTcHistory}
          bridgeCrossRes={tastes.crossRes}
          qlooEnabled={!!status?.enabled}
          bridgeAnchor={(persona.current.id !== 'maria' && !(persona.current.taste_anchors || '').trim())
            ? persona.current.name
            : (tasteCare.tcLikes.split(/[,，\n]/)[0]?.trim() || '')}
          onOpenDiscover={() => goTab('discover')}
          personaName={persona.current.name}
          personaProfile={persona.current.id === 'maria' ? null : persona.current}
          animateTextGraph={persona.current.id !== 'maria'}
          revealGraph={true}
          onOpenEvidence={() => goTab('evidence')}
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
          // Pass the optional domain through so the Tastes pills can re-filter
          // on the FIRST click (the old `() => doSearch()` wrapper dropped the
          // argument, so the pill's explicit override was ignored and users had
          // to click twice before results re-ran under the new domain).
          doSearch={(d) => void tastes.doSearch(d)}
          doRecommend={(d) => void tastes.doRecommend(d)}
          doRecommendFrom={(seed) => {
            // Clicking a search-result anchor in the Tastes tab must ALSO re-center
            // the Taste Bridge on that anchor (feedback: bridge only followed
            // persona switches, not the tab's own current search). Pin the clicked
            // anchor to the front of the seed list and re-cross when Qloo is on,
            // so the Discover constellation follows the judge's current search.
            tastes.setSeeds(prev => [seed, ...prev.filter(x => x.id !== seed.id)])
            if (status?.enabled) void tastes.doCrossFrom([seed])
            void tastes.doRecommendFrom(seed)
          }}
          personaName={persona.current.name}
          loading={loading}
          error={error}
          recommendTried={tastes.recommendTried}
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
          animateText={persona.current.id !== 'maria'}
          reveal={true}
          personaName={persona.current.name}
          personaHabits={persona.current.id === 'maria' ? [] : persona.current.taste_anchors.split(/[,，\n]/).map(s => s.trim()).filter(Boolean)}
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
          memory={chat.memory}
          personaName={effectiveName}
          personaAnchor={effectiveAnchors.split(',').map(a => a.trim()).filter(Boolean).join(' · ') || 'Frank Sinatra'}
          personas={persona.all.map(p => ({ id: p.id, name: p.name, taste_anchors: p.taste_anchors, health_constraints: p.health_constraints, location: p.location }))}
          globalPersonaId={persona.current.id}
          boundPersonaId={agentBoundId}
          onBindPersona={setAgentBoundId}
          locked={agentLocked}
          onToggleLocked={() => setAgentLocked(v => !v)}
        />
      )}

      {tab === 'evidence' && (
        <EvidenceTab
          whyMode={whyMode}
          setWhyMode={setWhyMode}
          tcResult={tasteCare.tcResult}
        />
      )}

      {tab === 'community' && (
        <CommunityTab
          community={community}
          qlooEnabled={!!status?.enabled}
          personaName={persona.current.name}
          personaAnchors={persona.current.taste_anchors}
        />
      )}
      </main>
      </ErrorBoundary>

      <A11yToolbar />
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
