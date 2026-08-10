import { CheckCircle2, Sparkles } from 'lucide-react'
import type { ActionPlanCandidate } from '../mocks/dashboard'

interface ActionMatrixTableProps {
  candidates: ActionPlanCandidate[]
  onSelectCandidate?: (candidate: ActionPlanCandidate) => void
}

export function ActionMatrixTable({ candidates, onSelectCandidate }: ActionMatrixTableProps) {
  return (
    <div className="rounded-3xl border-2 border-slate-300 bg-white/90 backdrop-blur-xl p-6 shadow-xl text-slate-900 font-sans space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700 font-bold">
              <Sparkles className="h-4 w-4" />
            </span>
            <h3 className="text-xl font-extrabold tracking-tight text-slate-900">
              Deterministic Action Evaluation Matrix
            </h3>
          </div>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Single-objective maximization kernel: <code className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-mono font-bold">max V(a) = P_exp · V_sale - C_loss - C_logistics - C_div - w · L_mass</code>
          </p>
        </div>

        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800 shadow-sm">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          5 Candidate Actions Evaluated
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-300 bg-slate-100/90 text-slate-700 font-extrabold uppercase tracking-wider">
              <th className="p-3.5 rounded-l-xl">Candidate Action Plan</th>
              <th className="p-3.5 text-center">Projected Loss %</th>
              <th className="p-3.5 text-center">Mass Lost (kg)</th>
              <th className="p-3.5 text-right">Logistics Cost (₹)</th>
              <th className="p-3.5 text-right">Gross Revenue (₹)</th>
              <th className="p-3.5 text-right">Net Value Realization V(a)</th>
              <th className="p-3.5 text-center rounded-r-xl">Recommendation Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 font-medium">
            {candidates.map((plan) => (
              <tr
                key={plan.id}
                onClick={() => onSelectCandidate?.(plan)}
                className={`cursor-pointer transition-all ${
                  plan.isRecommended
                    ? 'bg-emerald-50/90 hover:bg-emerald-100/90 font-bold border-l-4 border-l-emerald-600'
                    : 'hover:bg-slate-50 text-slate-800'
                }`}
              >
                <td className="p-3.5">
                  <div className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                    {plan.name}
                    {plan.isRecommended && (
                      <span className="rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-extrabold text-white uppercase">
                        BEST ACTION
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500 font-normal mt-0.5 line-clamp-1">{plan.description}</div>
                </td>

                <td className="p-3.5 text-center">
                  <span
                    className={`inline-block px-2.5 py-1 rounded-full font-extrabold ${
                      plan.lossPercent <= 4.0
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                        : plan.lossPercent <= 6.5
                        ? 'bg-amber-100 text-amber-900 border border-amber-300'
                        : 'bg-rose-100 text-rose-900 border border-rose-300'
                    }`}
                  >
                    {plan.lossPercent}%
                  </span>
                </td>

                <td className="p-3.5 text-center font-bold text-slate-900">{plan.massLostKg} kg</td>

                <td className="p-3.5 text-right text-slate-600">₹{plan.logisticsCostInr.toLocaleString()}</td>

                <td className="p-3.5 text-right font-semibold text-slate-800">₹{plan.grossRevenueInr.toLocaleString()}</td>

                <td className="p-3.5 text-right font-extrabold text-sm text-slate-900">
                  <span className={plan.isRecommended ? 'text-emerald-700 text-base font-extrabold' : ''}>
                    ₹{plan.netRealizationInr.toLocaleString()}
                  </span>
                </td>

                <td className="p-3.5 text-center">
                  {plan.isRecommended ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 text-white px-3 py-1 text-[11px] font-extrabold shadow-sm">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Recommended
                    </span>
                  ) : (
                    <span className="text-[11px] text-slate-500 font-medium">Sub-optimal</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
