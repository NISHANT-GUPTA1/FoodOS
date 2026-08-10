import { useQuery } from '@tanstack/react-query'
import { ErrorState, LoadingState } from '../components/StatePanel'
import { fetchRescueDashboard } from '../api/mockApi'
import { SectionHeader } from '../components/SectionHeader'

export function RescueScreen() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['rescue-dashboard'],
    queryFn: fetchRescueDashboard,
  })

  if (isLoading) {
    return <LoadingState title="Loading rescue channels" description="Preparing ranked exits and eligibility gates." />
  }

  if (isError || !data) {
    return <ErrorState title="Rescue data failed to load" description="The recovery ranking cannot render until the mock response arrives." />
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Recover"
        title="Ranked exits for at-risk food"
        description="The safety gate stays visible and the excluded channels are greyed out so the judge can see why each option is or is not eligible."
      />

      <div className="grid gap-4 xl:grid-cols-2">
        {data.rows.map((row) => (
          <div key={row.channel} className={`panel p-5 ${row.eligible ? 'border-[#c4c7c8]' : 'border-[#c4c7c8] opacity-75'}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-[#1c1b1b]">{row.channel}</h2>
                <p className="mt-2 text-sm text-[#444748]">{row.reason}</p>
              </div>
              <span className={`chip border border-[#c4c7c8] bg-[#f1edec] ${row.eligible ? 'text-[#0f766e]' : 'text-[#646464]'}`}>
                {row.eligible ? 'Eligible' : 'Excluded'}
              </span>
            </div>
            <div className="mt-5 flex items-center justify-between border-t border-[#c4c7c8] pt-4 text-sm text-[#444748]">
              <span>{row.amount}</span>
              <span className="font-semibold text-[#1c1b1b]">{row.recovery}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}