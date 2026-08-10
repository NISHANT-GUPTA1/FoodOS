import { useEffect, useMemo, useState } from 'react'
import { TimerReset } from 'lucide-react'
import { rulToken } from '../../lib/risk'
import { formatCountdown } from '../../utils/format'

interface RulCountdownProps {
  /** Remaining useful life in HOURS, as the contract returns it. */
  hours: number
  size?: 'sm' | 'lg'
  className?: string
}

/**
 * Remaining useful life, ticking.
 *
 * The contract hands over a scalar `rul_hours`, not a deadline, so the deadline is
 * anchored at mount. That also means the countdown can never render a negative number
 * mid-demo, which a fixed timestamp in mock data eventually would.
 */
export function RulCountdown({ hours, size = 'sm', className = '' }: RulCountdownProps) {
  const deadline = useMemo(() => Date.now() + hours * 3_600_000, [hours])
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const token = rulToken(hours)
  const remaining = deadline - now

  if (size === 'lg') {
    return (
      <div className={`rounded-2xl border ${token.border} ${token.bg} px-5 py-4 ${className}`}>
        <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-slate-500">
          <TimerReset className="h-3.5 w-3.5" />
          Remaining useful life
        </div>
        <div className={`mt-1 font-mono text-4xl font-extrabold tabular-nums ${token.text}`}>
          {formatCountdown(remaining)}
        </div>
        <div className="mt-1 text-xs font-medium text-slate-600">
          {Math.round(hours)} h at assessment · burning down in real time
        </div>
      </div>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-lg border px-2 py-0.5 font-mono text-xs font-bold tabular-nums ${token.border} ${token.bg} ${token.text} ${className}`}
    >
      <TimerReset className="h-3 w-3" />
      {formatCountdown(remaining)}
    </span>
  )
}
