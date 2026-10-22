import type { Dispatch, SetStateAction } from 'react'
import type { TasteCareResult } from '../../api'
import { WhyQlooTab } from './WhyQlooTab'
import { AblationTab } from './AblationTab'
import { sx } from '../sx'

/**
 * Evidence tab — the proof, stacked as one story.
 *
 * Top: Why Qloo (same prompt, grounded vs ungrounded — a single-variable
 * ablation). Bottom: the full Variant A/B comparison. Kept in one tab so the
 * judge sees the entire evidence narrative without tab-hopping.
 */
type Props = {
  whyMode: 'qloo' | 'generic'
  setWhyMode: Dispatch<SetStateAction<'qloo' | 'generic'>>
  tcResult: TasteCareResult | null
}

export function EvidenceTab(props: Props) {
  const { whyMode, setWhyMode, tcResult } = props

  return (
    <section>
      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #F5A62344' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#F5A623', marginBottom: 8 }}>💡 Why Qloo?</h2>
        <p style={{ fontSize: 13, color: '#9CA3AF', lineHeight: 1.6 }}>
          Two independent comparisons — why grounding in a taste graph beats a plain LLM, and how the
          full pipeline performs head-to-head. Same prompt, same profile; <strong style={{ color: '#E5E7EB' }}>only Qloo differs</strong>.
        </p>
      </div>

      <div style={{ ...sx.card, marginBottom: 20, border: '1px solid #F5A62333' }}>
        <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: 0.8, color: '#F5A623', marginBottom: 10, textTransform: 'uppercase' as const }}>
          Part 1 · Why Qloo
        </div>
        <WhyQlooTab whyMode={whyMode} setWhyMode={setWhyMode} tcResult={tcResult} />
      </div>

      <div style={{ ...sx.card, border: '1px solid #8B5CF633' }}>
        <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: 0.8, color: '#C4B5FD', marginBottom: 10, textTransform: 'uppercase' as const }}>
          Part 2 · Variant A vs B ablation
        </div>
        <AblationTab />
      </div>
    </section>
  )
}