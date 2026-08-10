import { useQuery } from '@tanstack/react-query'
import { SlidersHorizontal } from 'lucide-react'
import { startTransition, useState } from 'react'
import { fetchPlanDashboard } from '../api/mockApi'
import { SectionHeader } from '../components/SectionHeader'
import { ErrorState, LoadingState } from '../components/StatePanel'

export function PlanScreen() {
  const [lambda, setLambda] = useState(0.35)
  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ['plan-dashboard', lambda],
    queryFn: () => fetchPlanDashboard({ lambda }),
    placeholderData: (previous) => previous,
  })

  const handleLambdaChange = (value: number) => {
    startTransition(() => setLambda(value))
  }

  if (isLoading && !data) {
    return <LoadingState title="Building the prep plan" description="Waiting for the mock lambda response before rendering the table." />
  }

  if (isError || !data) {
    return <ErrorState title="Prep plan data failed to load" description="The lambda table cannot render until the query returns." />
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Plan"
        title="Lambda-driven prep table"
        description="Drag lambda to shift the recommendation between profit-first and planet-first. The table updates live from the mock query."
        action={
          <div className="panel-soft flex items-center gap-3 px-4 py-3 text-[#1c1b1b]">
            <SlidersHorizontal className="h-4 w-4 text-[#5d5f5f]" />
            <div className="text-sm text-[#444748]">Live refetch {isFetching ? 'in progress' : 'idle'}</div>
          </div>
        }
      />

      <section className="panel p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-[#646464]">Lambda</p>
            <div className="mt-2 text-3xl font-semibold text-[#1c1b1b]">{lambda.toFixed(2)}</div>
          </div>
          <div className="w-full max-w-xl">
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={lambda}
              onChange={(event) => handleLambdaChange(Number(event.target.value))}
              className="input-range"
              aria-label="Lambda slider"
            />
            <div className="mt-2 flex justify-between text-xs uppercase tracking-[0.25em] text-[#646464]">
              <span>Profit</span>
              <span>Balance</span>
              <span>Planet</span>
            </div>
          </div>
        </div>

        <div className="mt-6 overflow-hidden rounded-3xl border border-[#c4c7c8]">
          <table className="min-w-full divide-y divide-[#c4c7c8] text-left text-sm">
            <thead className="bg-[#f1edec] text-xs uppercase tracking-[0.24em] text-[#646464]">
              <tr>
                <th className="px-4 py-3">Dish</th>
                <th className="px-4 py-3">Old qty</th>
                <th className="px-4 py-3">Recommended qty</th>
                <th className="px-4 py-3">Δ</th>
                <th className="px-4 py-3">Saving</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#c4c7c8] bg-white">
              {data.rows.map((row) => (
                <tr key={row.dish} className="text-[#1c1b1b]">
                  <td className="px-4 py-4 font-medium text-[#1c1b1b]">{row.dish}</td>
                  <td className="px-4 py-4">{row.oldQty}</td>
                  <td className="px-4 py-4">{row.recommendedQty}</td>
                  <td className={`px-4 py-4 ${row.delta > 0 ? 'text-[#0f766e]' : 'text-[#ba1a1a]'}`}>{row.delta}</td>
                  <td className="px-4 py-4 text-[#1c1b1b]">₹{row.saving}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-[#f1edec] text-sm text-[#1c1b1b]">
              <tr>
                <td className="px-4 py-4 font-semibold text-[#1c1b1b]">Total</td>
                <td className="px-4 py-4">{data.totals.oldQty}</td>
                <td className="px-4 py-4">{data.totals.recommendedQty}</td>
                <td className="px-4 py-4">-</td>
                <td className="px-4 py-4 font-semibold text-[#1c1b1b]">₹{data.totals.saving}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section className="print-card print-keep print-only hidden">
        <div className="text-xs uppercase tracking-[0.3em] text-[#646464]">A5 prep card</div>
        <div className="mt-3 text-2xl font-semibold text-[#1c1b1b]">{data.rows[0]?.dish ?? 'Prep plan'}</div>
        <p className="mt-2 text-sm text-[#444748]">Lambda {lambda.toFixed(2)}. Recommended total qty {data.totals.recommendedQty}. Saving ₹{data.totals.saving}.</p>
      </section>
    </div>
  )
}