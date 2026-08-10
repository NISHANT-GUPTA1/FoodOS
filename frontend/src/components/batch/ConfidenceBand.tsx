import type { BatchRisk } from '../../api/batchContract'
import { CONFIDENCE_LABEL, confidenceToken, riskToken } from '../../lib/risk'
import { formatKgWhole, formatLossPct } from '../../utils/format'

interface ConfidenceBandProps {
  risk: BatchRisk
}

/**
 * Expected loss rendered as a BAND, not a point.
 *
 * Screen 3 spec: "loss % with its confidence band rendered as a band and not a point."
 * A single number invites a judge to ask how precise it is; the interval answers first.
 */
export function ConfidenceBand({ risk }: ConfidenceBandProps) {
  const token = riskToken(risk.level)
  const confidence = confidenceToken(risk.confidence)

  // Scale the axis a little wider than the interval so the band never touches the edges.
  const axisMin = 0
  const axisMax = Math.max(risk.high * 1.35, risk.loss_pct * 1.5, 12)
  const pct = (value: number) => `${(((value - axisMin) / (axisMax - axisMin)) * 100).toFixed(2)}%`

  return (
    <div className="rounded-2xl border border-slate-200 bg-white/80 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Expected loss</p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={`text-5xl font-extrabold tabular-nums ${token.text}`}>{formatLossPct(risk.loss_pct)}</span>
            <span className="text-sm font-semibold text-slate-600">{formatKgWhole(risk.loss_kg)}</span>
          </div>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider ${confidence.badge}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${confidence.dot}`} />
          {CONFIDENCE_LABEL[risk.confidence] ?? risk.confidence}
        </span>
      </div>

      <div className="mt-6">
        <div className="relative h-3 w-full rounded-full bg-slate-200/80">
          <div
            className={`absolute top-0 h-3 rounded-full ${token.bar} opacity-35`}
            style={{ left: pct(risk.low), width: `calc(${pct(risk.high)} - ${pct(risk.low)})` }}
          />
          <div
            className={`absolute -top-1 h-5 w-1 rounded-full ${token.bar}`}
            style={{ left: pct(risk.loss_pct) }}
            title={`Point estimate ${formatLossPct(risk.loss_pct)}`}
          />
        </div>

        <div className="relative mt-2 h-8 text-[11px] font-semibold tabular-nums text-slate-600">
          <span className="absolute -translate-x-1/2" style={{ left: pct(risk.low) }}>
            q10 {formatLossPct(risk.low)}
          </span>
          <span className="absolute -translate-x-1/2" style={{ left: pct(risk.high) }}>
            q90 {formatLossPct(risk.high)}
          </span>
        </div>
      </div>

      <p className="mt-1 text-xs leading-relaxed text-slate-600">
        Quantile heads at q10/q90 from the loss model. The point estimate is what the optimiser
        scores; the band is what you should plan against.
      </p>
    </div>
  )
}
