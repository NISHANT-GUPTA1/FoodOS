/**
 * Risk colour tokens — ONE definition, used everywhere.
 *
 * Team Split v2 §5, H0-3: "Risk colour tokens: HIGH red / MEDIUM amber / LOW green —
 * one definition, used everywhere."
 *
 * Nothing in `frontend/` may hardcode a risk colour. Import from here.
 */

export type RiskLevel = 'HIGH' | 'MEDIUM' | 'LOW'
export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW'

export interface RiskToken {
  /** Row-group heading on the Command Center. */
  group: string
  /** Short badge text. */
  label: string
  text: string
  bg: string
  border: string
  dot: string
  bar: string
  /** Solid hex for Recharts / SVG, which cannot take Tailwind classes. */
  hex: string
  /** Full badge recipe, so a badge never gets assembled twice. */
  badge: string
  /** Left accent for a list row. */
  accent: string
}

export const RISK: Record<RiskLevel, RiskToken> = {
  HIGH: {
    group: 'High Risk',
    label: 'High',
    text: 'text-rose-800',
    bg: 'bg-rose-50',
    border: 'border-rose-300',
    dot: 'bg-rose-500',
    bar: 'bg-rose-500',
    hex: '#e11d48',
    badge: 'border-rose-300 bg-rose-50 text-rose-800',
    accent: 'border-l-rose-500',
  },
  MEDIUM: {
    group: 'Need Attention',
    label: 'Medium',
    text: 'text-amber-900',
    bg: 'bg-amber-50',
    border: 'border-amber-300',
    dot: 'bg-amber-500',
    bar: 'bg-amber-500',
    hex: '#f59e0b',
    badge: 'border-amber-300 bg-amber-50 text-amber-900',
    accent: 'border-l-amber-500',
  },
  LOW: {
    group: 'Stable',
    label: 'Low',
    text: 'text-emerald-800',
    bg: 'bg-emerald-50',
    border: 'border-emerald-300',
    dot: 'bg-emerald-500',
    bar: 'bg-emerald-500',
    hex: '#10b981',
    badge: 'border-emerald-300 bg-emerald-50 text-emerald-800',
    accent: 'border-l-emerald-500',
  },
}

/** Command Center group order — worst first, because the screen is a work queue. */
export const RISK_ORDER: RiskLevel[] = ['HIGH', 'MEDIUM', 'LOW']

export function riskToken(level: RiskLevel | string | undefined): RiskToken {
  return RISK[(level as RiskLevel) ?? 'LOW'] ?? RISK.LOW
}

/**
 * Confidence reuses the same three tokens so a MEDIUM band and a MEDIUM risk read
 * as the same amber. Only the wording changes.
 */
export const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  HIGH: 'High confidence',
  MEDIUM: 'Medium confidence',
  LOW: 'Low confidence',
}

/**
 * Confidence is inverted against risk: HIGH confidence is the good outcome, so it
 * takes the green token and LOW takes red.
 */
export function confidenceToken(level: ConfidenceLevel | string | undefined): RiskToken {
  if (level === 'HIGH') return RISK.LOW
  if (level === 'LOW') return RISK.HIGH
  return RISK.MEDIUM
}

/** RUL urgency shares the risk palette so the countdown never invents a fourth colour. */
export function rulToken(hours: number): RiskToken {
  if (hours <= 24) return RISK.HIGH
  if (hours <= 48) return RISK.MEDIUM
  return RISK.LOW
}
