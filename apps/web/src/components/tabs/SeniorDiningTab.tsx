import type { Dispatch, SetStateAction } from 'react'
import type { QlooEntity, TasteCareResult } from '../../api'
import {
  CONSTRAINT_META, DISCLAIMER_EN,
  EN_CONSTRAINT_ICON, EN_CONSTRAINT_LABEL,
  SENIOR_SCENARIO_PROMPTS,
} from '../../constants'
import { SkeletonRow, TasteCareCard } from '../ui'
import { sx } from '../sx'
import { uniqueBy } from '../../utils/list'
import { QlooGroundingPanel } from '../QlooGroundingPanel'
import { TasteBridgeHero } from '../TasteBridgeHero'
import { QlooStatusStrip } from '../QlooStatusStrip'
import { splitTasteAnchors } from '../../utils/tasteAnchors'

type Props = {
  tcLikes: string
  setTcLikes: (v: string) => void
  tcLocation: string
  setTcLocation: (v: string) => void
  tcConstraints: Record<string, boolean>
  setTcConstraints: Dispatch<SetStateAction<Record<string, boolean>>>
  tcResult: TasteCareResult | null
  tcSearched: boolean
  doTasteCare: () => void
  onRunMariaStory: () => void
  activeConstraintCount: number
  activeConstraintLabels: string
  loading: boolean
  searchHistory: string[]
  onPickHistory: (v: string) => void
  onClearHistory: () => void
  bridgeCrossRes: Record<string, QlooEntity[]>
  qlooEnabled: boolean
  bridgeAnchor: string
  onOpenDiscover: () => void
  personaName?: string
  /** Non-Maria profile → templated card instead of Maria's bio. */
  personaProfile?: { location: string; taste_anchors: string; health_constraints: string } | null
  animateTextGraph?: boolean
  revealGraph?: boolean
  onOpenEvidence?: () => void
}

export function SeniorDiningTab(props: Props) {
  const {
    tcLikes, setTcLikes, tcLocation, setTcLocation,
    tcConstraints, setTcConstraints, tcResult, tcSearched,
    doTasteCare, onRunMariaStory, activeConstraintCount, activeConstraintLabels, loading,
    searchHistory, onPickHistory, onClearHistory,
    bridgeCrossRes, qlooEnabled, bridgeAnchor, onOpenDiscover,
    personaName = 'Maria', personaProfile = null, animateTextGraph = false, revealGraph = false,
    onOpenEvidence,
  } = props

  // Health-screening buckets for the demo list. We split the single Qloo-ordered
  // candidate list into two visually distinct groups — 🟢 Passed (fully meets
  // active constraints) and ⚠️ Needs Menu Review (culturally matched, but some
  // items may violate constraints). The backend already returns a structured
  // `screening` field; we fall back to `health.passes` so old responses still work.
  const tcRecs = uniqueBy(tcResult?.recommendations ?? [], r => r.id || r.name || '')
  // Persona's own anchors, split + deduped + capped once (comma-safe: a Qloo
  // entity name may contain commas, e.g. "Nature's Point, luxury holiday homes
  // by Together Travel" — never let it be truncated or repeated).
  const profileAnchors = personaProfile ? splitTasteAnchors(personaProfile.taste_anchors) : []
  const screeningOf = (r: TasteCareResult['recommendations'][number]): 'pass' | 'review' =>
    r.screening ?? (r.health?.passes ? 'pass' : 'review')
  const passedRecs = tcRecs
    .map((r, i) => ({ r, rank: i + 1 }))
    .filter(({ r }) => screeningOf(r) === 'pass')
  const reviewRecs = tcRecs
    .map((r, i) => ({ r, rank: i + 1 }))
    .filter(({ r }) => screeningOf(r) !== 'pass')

  return (
    <section>
      <TasteBridgeHero
        anchor={bridgeAnchor}
        crossRes={bridgeCrossRes}
        qlooEnabled={qlooEnabled}
        onExplore={onOpenDiscover}
        personaName={personaName}
        personaHabits={profileAnchors}
        animateText={animateTextGraph}
        reveal={revealGraph}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 12, padding: '10px 14px', borderRadius: 10, background: '#0B1220', border: '1px solid #374151' }}>
        <span style={{ fontSize: 11, letterSpacing: 0.8, color: '#9CA3AF', fontWeight: 800 }}>🚀 ONE DEMO ·</span>
        <span style={{ fontSize: 12, color: '#D1D5DB' }}>Persona → Search &amp; Health Screening → Taste Bridge → Why Qloo</span>
        <span style={{ flex: 1 }} />
        {onOpenEvidence && (
          <button onClick={onOpenEvidence} style={{ fontSize: 11, padding: '4px 12px', borderRadius: 999, background: '#1F2937', border: '1px solid #F5A62355', color: '#F5A623', cursor: 'pointer' }}>💡 Why Qloo?</button>
        )}
      </div>
      <div style={{ marginBottom: 14, padding: '10px 14px', borderRadius: 8, background: '#FF6B3512', border: '1px solid #FF6B3544' }}>
        <span style={{ fontSize: 12, color: '#E5E7EB', lineHeight: 1.55 }}>
          <strong style={{ color: '#FF6B35' }}>Health-screened dining.</strong> Unlike the <strong>Tastes → Dining</strong> pill (pure Qloo culture affinity, no health filters), Senior Dining takes the cultural match and then screens every candidate against this person&apos;s active health constraints — 🟢 passed vs ⚠️ needs menu review below.
        </span>
      </div>
      <button
        onClick={onRunMariaStory}
        disabled={loading}
        title={`Runs the full demo: fills ${personaName}'s profile, searches the live Qloo taste graph, screens for health constraints, and shows the Why Qloo grounding panel.`}
        style={{
          width: '100%', padding: '14px 18px', borderRadius: 12, cursor: 'pointer',
          fontSize: 14, fontWeight: 800, letterSpacing: 0.3,
          color: '#fff', border: '1px solid #6EE7B766',
          background: 'linear-gradient(135deg, #FF6B35, #8B5CF6)',
          boxShadow: '0 4px 20px #FF6B3544',
          marginBottom: 6, opacity: loading ? 0.6 : 1,
        }}
      >
        🍽️ Try {personaName}'s Story — one click, live Qloo demo
      </button>
      <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 16, lineHeight: 1.5 }}>
        * Resets all health constraints and taste preferences to {personaName}'s canonical baseline profile, then re-runs the live demo.
      </div>
      <QlooStatusStrip
        loading={loading}
        matched={tcSearched && tcResult ? tcResult.recommendations.length : null}
        detail={qlooEnabled ? 'live Qloo grounding' : 'demo preview grounding'}
      />
      <div style={{ marginBottom: 16 }}>
        <label style={sx.label}>Quick scenarios (click to try)</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
          {SENIOR_SCENARIO_PROMPTS.map((prompt, i) => (
            <button
              key={i}
              onClick={() => setTcLikes(prompt)}
              style={{ fontSize: 11, padding: '6px 12px', borderRadius: 8, background: '#1F2937', color: '#D1D5DB', border: '1px solid #374151', cursor: 'pointer', textAlign: 'left', maxWidth: 280 }}
              title={prompt}
            >
              🎯 {i + 1}. {prompt.slice(0, 40)}…
            </button>
          ))}
        </div>
      </div>
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #FF6B3533', background: 'linear-gradient(135deg, #FF6B3510, #111827)' }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' as const }}>
          <div style={{ width: 56, height: 56, borderRadius: 50, flexShrink: 0, background: 'linear-gradient(135deg, #FF6B35, #C77DFF)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, color: '#fff', fontWeight: 800 }}>
            {personaName.slice(0, 1) || '👤'}
          </div>
          <div style={{ flex: 1, minWidth: 280 }}>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: '#FF6B35', marginBottom: 6 }}>Meet {personaName}</h2>
            {personaProfile ? (
              <>
                <p style={{ fontSize: 14, color: '#D1D5DB', lineHeight: 1.7, marginBottom: 8 }}>
                  Lives in <strong style={{ color: '#FF6B35' }}>{personaProfile.location || '—'}</strong> · Loves{' '}
                  <strong style={{ color: '#FF6B35' }}>{profileAnchors.slice(0, 12).join(', ')}{profileAnchors.length > 12 ? ' …' : ''}</strong>.
                </p>
                <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
                  Health needs: <strong style={{ color: '#F5A623' }}>{personaProfile.health_constraints || 'none specified'}</strong>. Qloo finds what they&apos;d actually love — then we filter for their health.
                </p>
              </>
            ) : (
              <>
                <p style={{ fontSize: 14, color: '#D1D5DB', lineHeight: 1.7, marginBottom: 8 }}>
                  82 years old. Grew up in Little Italy, New York. Her kitchen smelled of garlic and basil while Sinatra played on the radio. She still loves <strong style={{ color: '#FF6B35' }}>jazz</strong>, <strong style={{ color: '#FF6B35' }}>Bob Dylan</strong>, and <strong style={{ color: '#FF6B35' }}>classic Hollywood films</strong>.
                </p>
                <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
                  But now she needs <em>easy-to-chew</em> food (dentures), watches her <em>sodium</em> (blood pressure), and takes <em>medications</em> that interact with certain foods.
                </p>
              </>
            )}
            <p style={{ fontSize: 13, color: '#F5A623', marginTop: 8, fontWeight: 600 }}>
              A generic "healthy senior meal" list misses everything that makes her <em>her</em>. Qloo finds what she'd actually love — then we filter for her health.
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 16 }}>
        <div>
          <label style={sx.label}>🫑 {personaName}'s cultural tastes (Qloo taste anchors — artists, cuisines, films)</label>
          <textarea value={tcLikes} onChange={e => setTcLikes(e.target.value)} style={{ ...sx.input, minHeight: 56, resize: 'vertical' as const, flex: 1 }} placeholder="Frank Sinatra, Italian cuisine, Jazz…" />
        </div>
        {searchHistory.length > 0 && (
          <div>
            <label style={sx.label}>Recent searches</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
              {Array.from(new Set(searchHistory)).map(h => (
                <button key={h} onClick={() => onPickHistory(h)} style={{ padding: '4px 10px', borderRadius: 8, border: '1px solid #374151', background: '#1F2937', color: '#E5E7EB', fontSize: 11, cursor: 'pointer' }}>{h}</button>
              ))}
              <button onClick={onClearHistory} style={{ padding: '4px 10px', borderRadius: 8, border: 'none', background: 'none', color: '#6B7280', fontSize: 11, cursor: 'pointer', textDecoration: 'underline' }}>Clear</button>
            </div>
          </div>
        )}
        <div>
          <label style={sx.label}>📍 Location</label>
          <input value={tcLocation} onChange={e => setTcLocation(e.target.value)} style={sx.input} placeholder="New York" />
        </div>
        <div>
          <label style={sx.label}>⚕ Health constraints{activeConstraintCount > 0 && <span style={{ color: '#FF6B35', marginLeft: 8 }}>{activeConstraintCount} active</span>}</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {CONSTRAINT_META.map(c => (
              <label key={c.key} title={c.hint} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: tcConstraints[c.key] ? '#E5E7EB' : '#9CA3AF', cursor: 'pointer', background: tcConstraints[c.key] ? '#FF6B3520' : '#1F2937', border: `1px solid ${tcConstraints[c.key] ? '#FF6B35' : '#374151'}`, padding: '8px 14px', borderRadius: 10, transition: 'all 0.15s', fontWeight: tcConstraints[c.key] ? 600 : 400 }}>
                <input type="checkbox" checked={!!tcConstraints[c.key]} onChange={e => setTcConstraints(p => ({ ...p, [c.key]: e.target.checked }))} style={{ accentColor: '#FF6B35' }} />
                <span>{c.icon}</span> {c.label}
              </label>
            ))}
          </div>
        </div>
      </div>


      <button onClick={doTasteCare} disabled={loading} style={{ ...sx.btnPrimary, width: '100%', marginBottom: 20, opacity: loading ? 0.7 : 1 }}>
        {loading ? 'Searching Qloo taste graph…' : `🍽️ Find Meals ${personaName} Would Actually Love`}
      </button>

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {[1, 2, 3].map(i => <SkeletonRow key={i} />)}
        </div>
      )}

      {!loading && tcResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Qloo grounding — LIVE when the key is set (real anchors used, real search
              context); honest demo preview only when QLOO_API_KEY is missing. */}
          <div style={{ marginBottom: 4 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 8, background: tcResult.data_source === 'live' ? '#065F46' : '#78350F', color: tcResult.data_source === 'live' ? '#6EE7B7' : '#FCD34D', whiteSpace: 'nowrap' }}>
                {tcResult.data_source === 'live' ? '🟢 Live Qloo data' : '⚠️ Demo preview data'}
              </span>
              <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 8, background: '#1F2937', color: '#D1D5DB', whiteSpace: 'nowrap' }}>
                🎯 Fit scores = Qloo cultural affinity
              </span>
            </div>
            <QlooGroundingPanel
              tasteEntities={splitTasteAnchors(tcLikes).slice(0, 8)}
              tasteDataSource={tcResult.data_source === 'live' ? 'live' : 'preview'}
              tasteLocation={tcResult.data_source === 'live' ? (tcResult.location || tcLocation) : undefined}
              qlooContext={tcResult.data_source === 'live'
                ? {
                    anchors: splitTasteAnchors(tcLikes),
                    location: tcResult.location || tcLocation,
                    screened_for: activeConstraintLabels,
                    ordering: 'Scores are Qloo popularity; results ordered by Qloo taste affinity.',
                    search_note: 'Live Qloo taste-graph search, screened for the active health constraints.',
                  }
                : { note: 'QLOO_API_KEY not set — demo preview pool. Set the key to load live Qloo taste-graph grounding.' }}
            />
            <p style={{ fontSize: 10, color: '#6B7280', fontStyle: 'italic', marginTop: 6 }}>
              {tcResult.data_source === 'live'
                ? 'Live Qloo grounding — culture matched first, then screened for the active health constraints. Scores are Qloo popularity; ordering is Qloo taste affinity.'
                : 'Demo preview grounding panel — the meal list above is the clearly-labelled demo pool. Add QLOO_API_KEY to load the live Qloo entity payload.'}
            </p>
          </div>
          {tcResult && tcResult.recommendations.length > 0 && (
            <div style={{ padding: '12px 16px', borderRadius: 10, background: '#1F293744', border: '1px solid #374151', marginBottom: 8 }}>
              <p style={{ fontSize: 13, color: '#E5E7EB', lineHeight: 1.6 }}>
                <strong style={{ color: '#FF6B35' }}>#1 pick for {personaName}</strong> — {tcResult.recommendations[0]?.name}.
              </p>
              <p style={{ fontSize: 12, color: '#9CA3AF', lineHeight: 1.6, marginTop: 6 }}>
                {splitTasteAnchors(tcLikes).slice(0, 3).join(', ')} anchored a Qloo taste-graph search{tcLocation ? ` near ${tcLocation}` : ''}, then every result was screened for{activeConstraintLabels ? ` ${activeConstraintLabels}` : ' your active health constraints'}. Scores are Qloo popularity; results are ordered by Qloo taste affinity.
              </p>
            </div>
          )}
          {tcResult.active_constraints && tcResult.active_constraints.length > 0 && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' as const }}>
              {Array.from(new Set(tcResult.active_constraints)).map(c => (<span key={c}
                style={{ fontSize: 11, color: '#F5A623', background: '#F5A62318', padding: '3px 10px', borderRadius: 6, fontWeight: 600 }}>
                  {EN_CONSTRAINT_ICON[c] || '🚦'} {EN_CONSTRAINT_LABEL[c] || c}
              </span>))}
            </div>
          )}
          {tcRecs.length > 0 && (
            <div style={{ padding: '12px 16px', borderRadius: 10, background: '#1F293766', border: '1px solid #374151', marginBottom: 10 }}>
              <div style={{ fontSize: 12.5, color: '#D1D5DB', lineHeight: 1.6 }}>
                These <strong style={{ color: '#FFFFFF' }}>{tcRecs.length} culturally-matched candidates</strong> from Qloo have all been evaluated against your active health constraints.{' '}
                <span style={{ color: '#6EE7B7', fontWeight: 700 }}>🟢 Passed:</span> fully meets low-sugar &amp; low-sodium rules{' '}
                <span style={{ color: '#FBBF24', fontWeight: 700 }}>⚠️ Review needed:</span> culturally well-matched, but menu items may violate health constraints; requires careful menu selection.
              </div>
            </div>
          )}
          {passedRecs.length > 0 && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 2, paddingBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: '#34D399' }}>🟢 Passed Health Screening</span>
                <span style={{ fontSize: 11, color: '#6EE7B7', background: '#065F4633', padding: '2px 8px', borderRadius: 6 }}>{passedRecs.length}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 10 }}>
                {passedRecs.map(({ r, rank }) => <TasteCareCard key={r.id || `pass-${rank}`} rec={r} rank={rank} activeConstraints={tcResult?.active_constraints || []} showFitScore />)}
              </div>
            </>
          )}
          {reviewRecs.length > 0 && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 2, paddingBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: '#FBBF24' }}>⚠️ Needs Menu Review</span>
                <span style={{ fontSize: 11, color: '#FBBF24', background: '#B4530922', padding: '2px 8px', borderRadius: 6 }}>{reviewRecs.length}</span>
              </div>
              <div style={{ padding: '10px 14px', borderRadius: 8, background: '#B4530933', border: '1px solid #B4530966', marginBottom: 8 }}>
                <div style={{ fontSize: 11.5, color: '#FDE68A', lineHeight: 1.6 }}>
                  These restaurants have strong cultural affinity, but some menu items may exceed your low sugar / low sodium requirements. You should only select specific dishes instead of ordering freely.
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {reviewRecs.map(({ r, rank }) => <TasteCareCard key={r.id || `review-${rank}`} rec={r} rank={rank} activeConstraints={tcResult?.active_constraints || []} showFitScore />)}
              </div>
            </>
          )}
          {tcResult.recommendations.length === 0 && (
            <div style={{ textAlign: 'center', padding: 32, color: '#6B7280', fontSize: 14 }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>🚦</div>
              No matching meals returned. Try adjusting tastes or constraints.
            </div>
          )}
          {(tcResult.disclaimer || tcResult.recommendations.length > 0) && (
            <div style={{ marginTop: 12, padding: '12px 16px', borderRadius: 10, background: '#1F293722', border: '1px solid #37415144' }}>
              <p style={{ fontSize: 11, color: '#9CA3AF', lineHeight: 1.5 }}>{DISCLAIMER_EN}</p>
            </div>
          )}
        </div>
      )}

      {!loading && !tcResult && tcSearched && (
        <div style={{ textAlign: 'center', padding: 32, color: '#6B7280', fontSize: 14 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🚫</div>
          No results. The Qloo API might not be configured — check that QLOO_API_KEY is set.
        </div>
      )}

      {!loading && !tcResult && !tcSearched && (
        <div style={{ textAlign: 'center', padding: 24, color: '#6B7280', fontSize: 13 }}>
          Press the button above to see Qloo find meals that match {personaName}'s tastes, filtered by their health constraints.
        </div>
      )}
    </section>
  )
}
