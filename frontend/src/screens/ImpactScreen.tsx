import { useQuery } from '@tanstack/react-query'
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fetchImpactDashboard } from '../api/mockApi'
import { SectionHeader } from '../components/SectionHeader'
import { ErrorState, LoadingState } from '../components/StatePanel'

export function ImpactScreen() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['impact-dashboard'],
    queryFn: fetchImpactDashboard,
  })

  if (isLoading) {
    return <LoadingState title="Loading backtest" description="Preparing the held-out forecast comparison chart." />
  }

  if (isError || !data) {
    return <ErrorState title="Impact data failed to load" description="The backtest needs the mock series before it can render." />
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Impact"
        title="Backtest against a held-out window"
        description="The chart compares actuals, forecast, and baseline, with the held-out days shaded to make the evaluation explicit."
      />

      <div className="grid gap-4 md:grid-cols-3">
        {[
          { label: 'MAPE', value: data.accuracy.mape },
          { label: 'RMSE', value: data.accuracy.rmse },
          { label: 'Acceptance rate', value: data.accuracy.acceptance },
        ].map((metric) => (
          <div key={metric.label} className="panel p-5">
            <p className="text-xs uppercase tracking-[0.28em] text-[#646464]">{metric.label}</p>
            <div className="mt-3 text-3xl font-semibold text-[#1c1b1b]">{metric.value}</div>
          </div>
        ))}
      </div>

      <section className="panel p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-[#1c1b1b]">Forecast vs actual vs baseline</h2>
          <span className="text-sm text-[#646464]">Held-out window shaded from day 11 onward</span>
        </div>
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.rows} margin={{ top: 16, right: 24, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(196,199,200,0.7)" />
              <XAxis dataKey="day" stroke="rgba(68,71,72,0.9)" tickLine={false} axisLine={false} />
              <YAxis stroke="rgba(68,71,72,0.9)" tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  background: '#ffffff',
                  border: '1px solid #c4c7c8',
                  borderRadius: '16px',
                  color: '#1c1b1b',
                }}
              />
              <ReferenceArea x1="Day 11" x2="Day 14" fill="rgba(251,113,133,0.12)" />
              <Line type="monotone" dataKey="actual" stroke="#4ade80" strokeWidth={3} dot={false} />
              <Line type="monotone" dataKey="forecast" stroke="#38bdf8" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="baseline" stroke="#f59e0b" strokeWidth={2} dot={false} strokeDasharray="6 6" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  )
}