import { riskToken, type RiskLevel } from '../../lib/risk'

interface RiskBadgeProps {
  level: RiskLevel
  /** "High Risk" instead of "High". */
  long?: boolean
  className?: string
}

/** The only place a risk level becomes a coloured pill. */
export function RiskBadge({ level, long = false, className = '' }: RiskBadgeProps) {
  const token = riskToken(level)

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider ${token.badge} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${token.dot}`} />
      {long ? token.group : token.label}
    </span>
  )
}
