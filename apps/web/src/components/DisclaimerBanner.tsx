import { DISCLAIMER_EN } from '../constants'

/** Page-top medical / dietary disclaimer. */
export function DisclaimerBanner() {
  return (
    <div style={{ marginBottom: 20, padding: '10px 16px', borderRadius: 10, background: '#7F1D1D22', border: '1px solid #7F1D1D44' }}>
      <span style={{ fontSize: 11.5, color: '#FCA5A5', lineHeight: 1.5, display: 'block' }}>⚠️ {DISCLAIMER_EN}</span>
    </div>
  )
}
