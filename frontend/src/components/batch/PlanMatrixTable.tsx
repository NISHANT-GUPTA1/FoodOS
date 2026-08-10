import { useState } from 'react'
import { Ban, CheckCircle2, ChevronDown, Sparkles } from 'lucide-react'
import type { CandidatePlan } from '../../api/batchContract'
import { RISK } from '../../lib/risk'
import { formatIndianInr, formatInrDelta, formatKgWhole, formatLossPct } from '../../utils/format'

interface PlanMatrixTableProps {
  plans: CandidatePlan[]
  wPreserve: number
  modelRunId?: string
  onSimulate?: (plan: CandidatePlan) => void
}

function lossTone(pct: number) {
  if (pct <= 4.5) return RISK.LOW
  if (pct <= 7) return RISK.MEDIUM
  return RISK.HIGH
}

/**
 * The Action Evaluation Matrix.
 *
 * Every candidate the planner scored, including the ones it threw out. Excluded rows
 * are greyed WITH THEIR REASON VISIBLE — never dropped — because a judge asking "why
 * not just use a reefer?" should find the answer already on screen.
 *
 * Expanding a row shows every term of V(a), so no number here is unattributable.
 */
export function PlanMatrixTable({ plans, wPreserve, modelRunId, onSimulate }: PlanMatrixTableProps) {
  const [expanded, setExpanded] = useState<number | null>(null)
  const excluded = plans.filter((p) => !p.feasible).length

  return (
    <section className="rounded-3xl border-2 border-slate-300 bg-white/90 p-6 shadow-xl backdrop-blur-xl">
      <header className="flex flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700">
              <Sparkles className="h-4 w-4" />
            </span>
            <h3 className="text-xl font-extrabold tracking-tight text-slate-900">Action evaluation matrix</h3>
          </div>
          <p className="mt-1.5 text-xs font-medium text-slate-600">
            One objective function, every candidate:{' '}
            <code className="rounded bg-emerald-50 px-1.5 py-0.5 font-mono font-bold text-emerald-700">
              max V(a) = Σ surviving_kg · price − C_logistics − C_diversion
            </code>{' '}
            ranked by <code className="font-mono font-bold text-slate-700">V(a) − λ·L_mass</code>, λ = ₹{wPreserve}/kg.
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-start gap-1.5 sm:items-end">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
            <CheckCircle2 className="h-4 w-4" />
            {plans.length} candidates evaluated
          </span>
          {excluded > 0 ? (
            <span className="text-[11px] font-semibold text-slate-500">{excluded} excluded, shown with reason</span>
          ) : null}
        </div>
      </header>

      {/* The negative margin pulled the scroll box wider than its padded
          parent, so the last column (STATUS) sat under the panel edge and read
          as "STATU". Scrolls within its own bounds now, and the min-width is
          the narrowest the nine columns actually need. */}
      <div className="mt-4 w-full overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-slate-300 bg-slate-100/90 text-[11px] font-extrabold uppercase tracking-wider text-slate-700">
              <th className="rounded-l-xl p-3">Candidate action</th>
              <th className="p-3 text-center">Loss %</th>
              <th className="p-3 text-center">Mass lost</th>
              <th className="p-3 text-right">Logistics</th>
              <th className="p-3 text-right">Gross revenue</th>
              <th className="p-3 text-right">Net value V(a)</th>
              <th className="p-3 text-right">Δ vs baseline</th>
              <th className="rounded-r-xl p-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 font-medium">
            {plans.map((plan) => {
              const tone = lossTone(plan.loss_pct)
              const isOpen = expanded === plan.id

              return [
                <tr
                  key={plan.id}
                  onClick={() => setExpanded(isOpen ? null : plan.id)}
                  className={`cursor-pointer transition-all ${
                    !plan.feasible
                      ? 'bg-slate-50/70 text-slate-400 hover:bg-slate-100/70'
                      : plan.is_best
                        ? 'border-l-4 border-l-emerald-600 bg-emerald-50/90 font-bold hover:bg-emerald-100/90'
                        : 'text-slate-800 hover:bg-slate-50'
                  }`}
                >
                  <td className="p-3">
                    <div className="flex items-center gap-1.5 text-sm font-bold">
                      <ChevronDown
                        className={`h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                      />
                      <span className={plan.feasible ? 'text-slate-900' : 'text-slate-500 line-through decoration-slate-300'}>
                        {plan.label}
                      </span>
                      {plan.is_best ? (
                        <span className="rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-extrabold uppercase text-white">
                          Best action
                        </span>
                      ) : null}
                      {plan.is_baseline ? (
                        <span className="rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] font-extrabold uppercase text-slate-600">
                          Baseline
                        </span>
                      ) : null}
                    </div>
                    {plan.exclusion_reason ? (
                      <div className="mt-1 flex items-start gap-1 text-[11px] font-semibold text-slate-500">
                        <Ban className="mt-0.5 h-3 w-3 shrink-0" />
                        <span>{plan.exclusion_reason}</span>
                      </div>
                    ) : plan.note ? (
                      <div className="mt-0.5 text-[11px] font-normal text-slate-500">{plan.note}</div>
                    ) : null}
                  </td>

                  <td className="p-3 text-center">
                    <span
                      className={`inline-block rounded-full border px-2.5 py-1 font-extrabold ${
                        plan.feasible ? `${tone.border} ${tone.bg} ${tone.text}` : 'border-slate-200 bg-white text-slate-400'
                      }`}
                    >
                      {formatLossPct(plan.loss_pct)}
                    </span>
                  </td>
                  <td className="p-3 text-center font-bold tabular-nums">{formatKgWhole(plan.loss_kg)}</td>
                  <td className="p-3 text-right tabular-nums">{formatIndianInr(plan.logistics_cost)}</td>
                  <td className="p-3 text-right font-semibold tabular-nums">{formatIndianInr(plan.gross_revenue)}</td>
                  <td
                    className={`p-3 text-right font-extrabold tabular-nums ${
                      plan.is_best && plan.feasible ? 'text-base text-emerald-700' : ''
                    }`}
                  >
                    {formatIndianInr(plan.net_value)}
                  </td>
                  <td
                    className={`p-3 text-right font-bold tabular-nums ${
                      !plan.feasible
                        ? 'text-slate-400'
                        : plan.delta_vs_baseline > 0
                          ? 'text-emerald-700'
                          : plan.delta_vs_baseline < 0
                            ? 'text-rose-700'
                            : 'text-slate-500'
                    }`}
                  >
                    {plan.is_baseline ? '—' : formatInrDelta(plan.delta_vs_baseline)}
                  </td>
                  <td className="p-3 text-center">
                    {!plan.feasible ? (
                      <span className="text-[11px] font-bold uppercase text-slate-400">Excluded</span>
                    ) : plan.is_best ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-3 py-1 text-[11px] font-extrabold text-white">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Recommended
                      </span>
                    ) : (
                      <span className="text-[11px] font-medium text-slate-500">Sub-optimal</span>
                    )}
                  </td>
                </tr>,

                isOpen ? (
                  <tr key={`${plan.id}-terms`} className="bg-slate-50/90">
                    <td colSpan={8} className="p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">
                          Every term of V(a) for this candidate
                        </p>
                        {onSimulate && plan.feasible ? (
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation()
                              onSimulate(plan)
                            }}
                            className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-[11px] font-bold uppercase text-slate-700 transition hover:bg-slate-100 active:scale-95"
                          >
                            Open in simulator
                          </button>
                        ) : null}
                      </div>
                      <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                        {[
                          ['Surviving mass', formatKgWhole(plan.terms.surviving_kg)],
                          ['Expected price', `₹${plan.terms.expected_price_per_kg.toFixed(2)}/kg`],
                          ['Gross revenue', formatIndianInr(plan.terms.gross_revenue)],
                          ['Logistics cost', `− ${formatIndianInr(plan.terms.logistics_cost)}`],
                          ['Loss (opportunity) cost', formatIndianInr(plan.terms.loss_cost)],
                          ['Diversion cost', `− ${formatIndianInr(plan.terms.diversion_cost)}`],
                          [`Mass penalty (λ = ₹${plan.terms.w_preserve}/kg)`, `− ${formatIndianInr(plan.terms.mass_penalty)}`],
                          ['Ranking value', formatIndianInr(plan.terms.ranking_value)],
                        ].map(([term, value]) => (
                          <div key={term} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                            <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{term}</dt>
                            <dd className="mt-0.5 font-mono text-sm font-bold tabular-nums text-slate-900">{value}</dd>
                          </div>
                        ))}
                      </dl>
                    </td>
                  </tr>
                ) : null,
              ]
            })}
          </tbody>
        </table>
      </div>

      {modelRunId ? (
        <p className="mt-4 border-t border-slate-200 pt-3 font-mono text-[10px] text-slate-400">
          Scored by model run {modelRunId} · simulator and optimiser call the same score()
        </p>
      ) : null}
    </section>
  )
}
