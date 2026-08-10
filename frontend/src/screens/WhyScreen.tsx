import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
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
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Why"
        title="What actually caused the waste?"
        description="The chart ranks the largest drivers so the judge can see the problem move from a vague loss bucket to a specific operational cause."
      />

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="panel p-5">
          <div className="mb-5 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-[#1c1b1b]">Attribution by driver</h2>
            <span className="text-sm text-[#646464]">Percent of avoidable loss</span>
          </div>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.attribution} layout="vertical" margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(196,199,200,0.7)" />
                <XAxis type="number" stroke="rgba(68,71,72,0.9)" tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" stroke="rgba(68,71,72,0.9)" tickLine={false} axisLine={false} width={120} />
                <Tooltip
                  contentStyle={{
                    background: '#ffffff',
                    border: '1px solid #c4c7c8',
                    borderRadius: '16px',
                    color: '#1c1b1b',
                  }}
                />
                <Bar dataKey="value" fill="#4ade80" radius={[0, 12, 12, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="space-y-4">
          <div className="panel p-5">
            <h2 className="text-lg font-semibold text-[#1c1b1b]">Top contributors</h2>
            <div className="mt-4 space-y-3">
              {data.contributors.map((item) => (
                <div key={item.label} className="rounded-2xl border border-[#c4c7c8] bg-[#f6f3f2] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-[#1c1b1b]">{item.label}</div>
                      <div className="text-sm text-[#444748]">{item.note}</div>
                    </div>
                    <div className="text-lg font-semibold text-[#1c1b1b]">{item.value}%</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel border-[#c4c7c8] bg-gradient-to-br from-[#f6f3f2] to-white p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-[#646464]">Trim callout</p>
            <p className="mt-3 text-sm leading-7 text-[#1c1b1b]">{data.callout}</p>
          </div>
        </section>
      </div>
    </div>
  )
}