import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Database, Sparkles } from 'lucide-react'
import { fetchWhyDashboard } from '../api/mockApi'
import { SectionHeader } from '../components/SectionHeader'
import { ErrorState, LoadingState } from '../components/StatePanel'

export function WhyScreen() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['why-dashboard'],
    queryFn: fetchWhyDashboard,
  })

  if (isLoading) {
    return <LoadingState title="Loading attribution" description="Collecting the largest loss drivers for the current cluster." />
  }

  if (isError || !data) {
    return <ErrorState title="Attribution data failed to load" description="The chart cannot render until the mock response returns." />
  }

  return (
    <div className="space-y-8 font-sans text-slate-900">
      <SectionHeader
        eyebrow="ARRHENIUS DECAY & NABCONS ATTRIBUTION"
        title="What Actually Caused the Food Loss?"
        description="Combines Ministry of Food Processing Industries (MoFPI/NABCONS) baseline statistics with Arrhenius kinetic respiration decay models: k = A · exp(-Ea / RT)."
      />

      {/* NABCONS MoFPI Macro Loss Statistics Card */}
      {data.nabconsBaseline && (
        <section className="rounded-3xl border-2 border-slate-300 bg-white/90 backdrop-blur-xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-emerald-600" />
              <h3 className="text-xl font-extrabold text-slate-900">
                NABCONS MoFPI Macro Food Loss Baseline (India Statistics)
              </h3>
            </div>
            <span className="rounded-full bg-emerald-100 border border-emerald-300 px-3 py-1 text-xs font-bold text-emerald-900">
              Annual Target: Farm-Gate Aggregation
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs font-semibold">
            <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200">
              <span className="text-slate-500 uppercase font-bold text-[10px] block">Annual Post-Harvest Loss</span>
              <span className="text-xl font-extrabold text-rose-700 block mt-1">{data.nabconsBaseline.annualLossInr}</span>
            </div>
            <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200">
              <span className="text-slate-500 uppercase font-bold text-[10px] block">Fruits & Vegetables Loss Range</span>
              <span className="text-xl font-extrabold text-slate-900 block mt-1">{data.nabconsBaseline.fruitsVegLossRange}</span>
            </div>
            <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200">
              <span className="text-slate-500 uppercase font-bold text-[10px] block">Tomato Post-Harvest Loss</span>
              <span className="text-xl font-extrabold text-rose-700 block mt-1">{data.nabconsBaseline.tomatoLossPercent}</span>
            </div>
            <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200">
              <span className="text-slate-500 uppercase font-bold text-[10px] block">Guava Post-Harvest Loss</span>
              <span className="text-xl font-extrabold text-rose-700 block mt-1">{data.nabconsBaseline.guavaLossPercent}</span>
            </div>
          </div>
        </section>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-3xl border-2 border-slate-300 bg-white/80 backdrop-blur-xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h2 className="text-lg font-bold text-slate-900">Attribution by Primary Driver</h2>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Percent of Avoidable Loss</span>
          </div>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.attribution} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(203,213,225,0.7)" />
                <XAxis type="number" stroke="#475569" tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" stroke="#334155" tickLine={false} axisLine={false} width={140} />
                <Tooltip
                  contentStyle={{
                    background: '#ffffff',
                    border: '1px solid #cbd5e1',
                    borderRadius: '16px',
                    color: '#0f172a',
                    fontWeight: 'bold',
                  }}
                />
                <Bar dataKey="value" fill="#10b981" radius={[0, 12, 12, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="space-y-4">
          <div className="rounded-3xl border-2 border-slate-300 bg-white/80 backdrop-blur-xl p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Top Loss Contributors</h2>
            <div className="space-y-3">
              {data.contributors.map((item) => (
                <div key={item.label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-bold text-slate-900 text-sm">{item.label}</div>
                      <div className="text-xs text-slate-600 mt-0.5">{item.note}</div>
                    </div>
                    <div className="text-xl font-extrabold text-emerald-700">{item.value}%</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border-2 border-emerald-300 bg-emerald-500/10 backdrop-blur-xl p-6 shadow-xl">
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-900 flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-emerald-600" /> Biophysical Decay Callout
            </p>
            <p className="mt-2 text-sm leading-relaxed text-slate-800 font-medium">{data.callout}</p>
          </div>
        </section>
      </div>
    </div>
  )
}