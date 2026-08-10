import { useQuery } from '@tanstack/react-query'
import {
  CheckCircle2,
  SlidersHorizontal,
  Sparkles,
  Truck,
} from 'lucide-react'
import { startTransition, useState } from 'react'
import { fetchPlanDashboard } from '../api/mockApi'
import { SectionHeader } from '../components/SectionHeader'
import { ErrorState, LoadingState } from '../components/StatePanel'

export function PlanScreen() {
  const [lambda, setLambda] = useState(0.35)
  const [departureShift, setDepartureShift] = useState(-6) // -6h early departure
  const [truckType, setTransportType] = useState<'OPEN' | 'TARPAULIN' | 'REFRIGERATED'>('TARPAULIN')
  const [delhiSplitPercent, setDelhiSplitPercent] = useState(60) // 60% Delhi, 40% Jaipur

  const { data, isLoading, isError } = useQuery({
    queryKey: ['plan-dashboard', lambda],
    queryFn: () => fetchPlanDashboard({ lambda }),
    placeholderData: (previous) => previous,
  })

  // Calculate live What-If scenario results dynamically
  const baseLoss = 8.4
  const departureDelta = (departureShift + 6) * 0.4
  const truckFactor = truckType === 'REFRIGERATED' ? -3.5 : truckType === 'TARPAULIN' ? -1.8 : 0
  const splitFactor = (100 - delhiSplitPercent) * 0.02
  const simulatedLossPercent = Math.max(2.1, Number((baseLoss + departureDelta + truckFactor - splitFactor).toFixed(1)))
  const simulatedLossKg = Math.round((simulatedLossPercent / 100) * 10000)
  const savedKg = Math.max(0, 840 - simulatedLossKg)

  const truckCost = truckType === 'REFRIGERATED' ? 44000 : truckType === 'TARPAULIN' ? 36000 : 32000
  const grossRevenue = Math.round(154000 - simulatedLossKg * 16)
  const simulatedNetRealization = grossRevenue - truckCost

  const simulatedRulHours = Math.round(31 + (6 - departureShift) * 1.5 + (truckType === 'REFRIGERATED' ? 24 : truckType === 'TARPAULIN' ? 8 : 0))

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
    <div className="space-y-8 font-sans text-slate-900">
      <SectionHeader
        eyebrow="WHAT-IF SCENARIO SIMULATOR (SCREEN 4)"
        title="What-If Decision Simulator"
        description="Model real-time trade-offs across departure shifts, truck transport upgrades, multi-mandi splitting, and lambda objectives for Batch #T1024 (10,000 kg Tomatoes)."
        action={
          <div className="flex items-center gap-2 rounded-full border border-slate-300 bg-white/90 px-4 py-2 text-xs font-bold text-slate-800 shadow-md backdrop-blur-md">
            <SlidersHorizontal className="h-4 w-4 text-emerald-600" />
            <span>Multi-Agent Simulation Engine</span>
          </div>
        }
      />

      {/* Interactive What-If Controls Grid */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Sliders Column (8 Cols) */}
        <div className="lg:col-span-8 space-y-6 rounded-3xl border-2 border-slate-300 bg-white/80 backdrop-blur-xl p-6 lg:p-8 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-200 pb-4">
            <h3 className="text-xl font-extrabold text-slate-900 flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-emerald-600" />
              Live Scenario Simulation Knobs
            </h3>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Batch #T1024 (10,000 kg)
            </span>
          </div>

          {/* Slider 1: Departure Time Shift */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-bold">
              <label className="text-slate-700 uppercase tracking-wider">1. Departure Shift (-6h Early to +6h Late)</label>
              <span className="rounded-full bg-emerald-100 border border-emerald-300 px-3 py-1 text-emerald-900 font-extrabold">
                {departureShift === 0 ? 'Baseline (10:00 AM)' : `${departureShift} Hours (${0 + 10 + departureShift}:00 AM)`}
              </span>
            </div>
            <input
              type="range"
              min={-6}
              max={6}
              step={1}
              value={departureShift}
              onChange={(e) => setDepartureShift(Number(e.target.value))}
              className="w-full accent-emerald-600"
            />
            <div className="flex justify-between text-[11px] font-semibold text-slate-500">
              <span>-6h (Pre-dawn 04:00 AM • Optimal)</span>
              <span>Baseline (10:00 AM)</span>
              <span>+6h (Peak Heat 04:00 PM)</span>
            </div>
          </div>

          {/* Control 2: Transport Mode Selection */}
          <div className="space-y-2 pt-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">
              2. Vehicle Transport & Insulation Upgrade
            </label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: 'OPEN', label: 'Open Truck (Baseline)', cost: '₹32,000', note: 'High ambient solar risk' },
                { id: 'TARPAULIN', label: 'Tarpaulin Covered', cost: '₹36,000', note: 'Insulated cover (-1.8% loss)' },
                { id: 'REFRIGERATED', label: 'Cold Refrigerated', cost: '₹44,000', note: 'Active chilling (-3.5% loss)' },
              ].map((truck) => (
                <button
                  key={truck.id}
                  onClick={() => setTransportType(truck.id as any)}
                  className={`rounded-2xl border-2 p-3 text-left transition ${
                    truckType === truck.id
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-900 font-bold shadow-sm'
                      : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="text-xs font-extrabold flex items-center justify-between">
                    <span>{truck.label}</span>
                    <Truck className="h-4 w-4 text-emerald-600" />
                  </div>
                  <div className="text-[11px] text-emerald-700 font-bold mt-1">{truck.cost}</div>
                  <div className="text-[10px] text-slate-500 font-normal mt-0.5">{truck.note}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Slider 3: Multi-Mandi Split Ratio */}
          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between text-xs font-bold">
              <label className="text-slate-700 uppercase tracking-wider">3. Multi-Mandi Destination Allocation</label>
              <span className="rounded-full bg-emerald-100 border border-emerald-300 px-3 py-1 text-emerald-900 font-extrabold">
                {delhiSplitPercent}% Delhi / {100 - delhiSplitPercent}% Jaipur
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={10}
              value={delhiSplitPercent}
              onChange={(e) => setDelhiSplitPercent(Number(e.target.value))}
              className="w-full accent-emerald-600"
            />
            <div className="flex justify-between text-[11px] font-semibold text-slate-500">
              <span>100% Jaipur (7h transit)</span>
              <span>60/40 Split (Recommended)</span>
              <span>100% Delhi (14h transit)</span>
            </div>
          </div>

          {/* Slider 4: Lambda Objective (Profit vs Planet Food Loss) */}
          <div className="space-y-2 pt-2 border-t border-slate-200">
            <div className="flex items-center justify-between text-xs font-bold">
              <label className="text-slate-700 uppercase tracking-wider">4. Lambda Weighting (Objective Multiplier λ = {lambda.toFixed(2)})</label>
              <span className="text-xs text-emerald-700 font-bold">
                {lambda < 0.3 ? 'Profit First' : lambda > 0.7 ? 'Planet Food Loss First' : 'Balanced Objective'}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={lambda}
              onChange={(e) => handleLambdaChange(Number(e.target.value))}
              className="w-full accent-emerald-600"
            />
          </div>
        </div>

        {/* Real-time Output Cards Column (4 Cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="rounded-3xl border-2 border-emerald-500/40 bg-white/90 backdrop-blur-xl p-6 shadow-xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h4 className="text-base font-extrabold text-slate-900 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                Live Simulation Output
              </h4>
              <span className="rounded-full bg-emerald-100 border border-emerald-300 px-2 py-0.5 text-[10px] font-bold text-emerald-800 uppercase">
                Real-Time
              </span>
            </div>

            {/* Simulated Loss % */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Projected Food Loss %</div>
              <div className="mt-1 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-emerald-700">{simulatedLossPercent}%</span>
                <span className="text-xs font-extrabold text-rose-600 line-through">8.4% baseline</span>
              </div>
              <p className="mt-1 text-[11px] text-emerald-800 font-semibold">
                ✨ Saves {savedKg} kg edible produce ({simulatedLossKg} kg physical loss)
              </p>
            </div>

            {/* Simulated RUL */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Remaining Useful Life (RUL)</div>
              <div className="mt-1 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-sky-700">{simulatedRulHours} Hours</span>
                <span className="text-xs font-semibold text-slate-500">Baseline 31h</span>
              </div>
              <p className="mt-1 text-[11px] text-sky-800 font-semibold">
                ⏱️ +{simulatedRulHours - 31}h shelf-life buffer preserved
              </p>
            </div>

            {/* Net Financial Realization V(a) */}
            <div className="rounded-2xl border border-emerald-300 bg-emerald-500/10 p-4">
              <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-900">Net Value Realization V(a)</div>
              <div className="mt-1 text-3xl font-extrabold text-slate-900">
                ₹{simulatedNetRealization.toLocaleString()}
              </div>
              <p className="mt-1 text-xs font-bold text-emerald-700">
                💰 Net Gain +₹{(simulatedNetRealization - 114560).toLocaleString()} vs baseline
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Prep Table Section */}
      <section className="rounded-3xl border-2 border-slate-300 bg-white/80 backdrop-blur-xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <h3 className="text-lg font-bold text-slate-900">Prep Recommendation Table</h3>
          <span className="text-xs text-slate-500 font-bold uppercase tracking-wider">Lambda {lambda.toFixed(2)}</span>
        </div>

        <div className="overflow-hidden rounded-2xl border border-slate-300">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs font-sans">
            <thead className="bg-slate-100 text-slate-700 font-extrabold uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Batch / Commodity</th>
                <th className="px-4 py-3 text-right">Old Qty (kg)</th>
                <th className="px-4 py-3 text-right">Recommended Qty (kg)</th>
                <th className="px-4 py-3 text-right">Delta (Δ)</th>
                <th className="px-4 py-3 text-right">Value Saving (₹)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white/90 font-medium">
              {data.rows.map((row) => (
                <tr key={row.dish} className="text-slate-900 hover:bg-slate-50">
                  <td className="px-4 py-4 font-bold text-slate-900">{row.dish}</td>
                  <td className="px-4 py-4 text-right text-slate-600">{row.oldQty.toLocaleString()}</td>
                  <td className="px-4 py-4 text-right font-extrabold text-emerald-700">{row.recommendedQty.toLocaleString()}</td>
                  <td className={`px-4 py-4 text-right font-bold ${row.delta > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{row.delta}</td>
                  <td className="px-4 py-4 text-right font-extrabold text-slate-900">₹{row.saving.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-slate-100 font-bold text-slate-900">
              <tr>
                <td className="px-4 py-4">Total Cluster Volume</td>
                <td className="px-4 py-4 text-right">{data.totals.oldQty.toLocaleString()} kg</td>
                <td className="px-4 py-4 text-right text-emerald-800">{data.totals.recommendedQty.toLocaleString()} kg</td>
                <td className="px-4 py-4 text-right">-</td>
                <td className="px-4 py-4 text-right text-emerald-700 text-sm">₹{data.totals.saving.toLocaleString()}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    </div>
  )
}