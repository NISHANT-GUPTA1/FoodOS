import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Check, ChevronRight, Clock3, Coins, RefreshCw, Scale, ShieldCheck } from 'lucide-react'
import { fetchTodayDashboard } from '../api/mockApi'
import { KpiCard } from '../components/KpiCard'
import { RecommendationCard } from '../components/RecommendationCard'
import { EmptyState, ErrorState, LoadingState } from '../components/StatePanel'
import { SectionHeader } from '../components/SectionHeader'
import heroImage from '../assets/hero.png'

export function TodayScreen() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['today-dashboard'],
    queryFn: fetchTodayDashboard,
  })

  if (isLoading) {
    return <LoadingState title="Loading today’s recommendations" description="Pulling the latest mock recommendations into the shell." />
  }

  if (isError || !data) {
    return <ErrorState title="Today failed to load" description="The shell is intact, but the mock response did not return. Retry once the data layer is connected." />
  }

  return (
    <div className="space-y-8">
      <SectionHeader
        eyebrow="PREVENT / PRESERVE / RECOVER"
        title="Today"
        description={data.hero}
        action={
          <div className="flex items-center gap-2 rounded-full border border-[#c4c7c8] bg-[#f1edec] px-4 py-2 text-sm text-[#444748] shadow-[4px_4px_0px_0px_#0ea5e9]">
            Ranked by expected value
            <ArrowRight className="h-4 w-4" />
          </div>
        }
      />

      <section className="grid grid-cols-1 gap-6 md:grid-cols-12">
        <div className="relative overflow-hidden border border-[#c4c7c8] bg-[#f1edec] p-6 md:col-span-8 lg:p-8">
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute inset-0 bg-gradient-to-r from-[#f1edec] via-[#f1edec]/95 to-[#f1edec]/40" />
            {/* Bundled, not fetched — see §8 H33-36, the wifi-off rehearsal. */}
            <img
              alt="Culinary craft"
              className="h-full w-full object-cover opacity-25"
              src={heroImage}
            />
          </div>

          <div className="absolute left-0 top-0 z-10 flex items-center gap-2 bg-[#ba1a1a] px-3 py-1 text-xs font-semibold uppercase tracking-widest text-white">
            <ShieldCheck className="h-3.5 w-3.5" />
            Critical Action • Prevent
          </div>

          <div className="relative z-10 mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
            <div className="flex flex-col justify-between">
              <div>
                <h2 className="mb-4 text-4xl font-semibold tracking-tighter text-[#1c1b1b] lg:text-6xl">Waste Less, Feed More: Biryani Prep Tuning</h2>
                <p className="max-w-2xl text-lg leading-8 text-[#444748]">Forecast indicates 20% drop in expected demand due to severe weather alerts across Zone B delivery hubs.</p>
              </div>

              <div className="mt-8 flex items-end gap-4">
                <div className="flex flex-col">
                  <span className="mb-1 text-xs uppercase tracking-[0.24em] text-[#646464]">Current Plan</span>
                  <span className="text-6xl font-semibold text-[#1c1b1b] line-through opacity-50">80</span>
                </div>
                <div className="mb-4 text-[#c4c7c8]">
                  <ChevronRight className="h-9 w-9" />
                </div>
                <div className="flex flex-col">
                  <span className="mb-1 text-xs uppercase tracking-[0.24em] text-[#5d5f5f]">Optimized</span>
                  <span className="text-6xl font-semibold text-[#ba1a1a]">63<span className="ml-1 text-lg font-normal text-[#444748]">ptns</span></span>
                </div>
              </div>
            </div>

            <div className="flex flex-col justify-between border-l border-[#c4c7c8] pl-8">
              <div className="w-full border border-[#c4c7c8] bg-[#f6f3f2] p-6">
                <h3 className="mb-4 text-xs font-bold uppercase tracking-widest text-[#646464]">Respecting the Ingredient</h3>
                <div className="flex flex-col gap-4">
                  <div className="flex items-center justify-between border-b border-[#c4c7c8] pb-2">
                    <div className="flex items-center gap-2 text-[#1c1b1b]">
                      <Scale className="h-4 w-4 text-emerald-600" />
                      <span className="text-base">Waste Avoided</span>
                    </div>
                    <span className="font-semibold">8.4 kg</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[#c4c7c8] pb-2">
                    <div className="flex items-center gap-2 text-[#1c1b1b]">
                      <Coins className="h-4 w-4 text-emerald-600" />
                      <span className="text-base">Value Preserved</span>
                    </div>
                    <span className="font-semibold">₹1,500</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[#1c1b1b]">
                      <RefreshCw className="h-4 w-4 text-emerald-600" />
                      <span className="text-base">CO2e Saved</span>
                    </div>
                    <span className="font-semibold">21 kg</span>
                  </div>
                </div>
              </div>

              <div className="mt-8 flex gap-4">
                <button className="flex-1 border-2 border-[#c4c7c8] bg-[#fcf8f8] py-4 text-sm font-bold uppercase text-[#1c1b1b] transition hover:-translate-x-1 hover:-translate-y-1 hover:shadow-[4px_4px_0px_0px_#ef4444]">
                  Override
                </button>
                <button className="flex-1 border border-[#1c1b1b] bg-[#f8fafc] py-4 text-sm font-bold uppercase text-[#0f172a] transition hover:-translate-x-1 hover:-translate-y-1 hover:shadow-[4px_4px_0px_0px_#10b981]">
                  Accept Plan
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="md:col-span-4 flex flex-col gap-6">
          {data.recommendations.slice(0, 2).map((item) => (
            <div key={item.id} className="border border-[#c4c7c8] bg-[#ebe7e7] p-6">
              <div className={`inline-flex items-center gap-2 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-white ${item.horizon === 'PREVENT' ? 'bg-[#ba1a1a]' : item.horizon === 'PRESERVE' ? 'bg-[#0ea5e9]' : 'bg-[#10b981]'}`}>
                {item.horizon === 'PREVENT' ? <ShieldCheck className="h-3.5 w-3.5" /> : item.horizon === 'PRESERVE' ? <Clock3 className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />}
                {item.horizon === 'PREVENT' ? 'Prevent' : item.horizon === 'PRESERVE' ? 'Preserve' : 'Recover'}
              </div>
              <div className="mt-8">
                <h3 className="text-2xl font-semibold tracking-tight text-[#1c1b1b]">{item.title}</h3>
                <p className="mt-2 text-base leading-7 text-[#444748]">{item.subtitle}</p>
              </div>
              <div className="mt-6 flex items-end justify-between border-t border-[#c4c7c8] pt-4">
                <div className="flex flex-col">
                  <span className="text-xs uppercase tracking-[0.24em] text-[#646464]">Recommendation</span>
                  <span className="text-2xl font-semibold text-[#1c1b1b]">{item.beforeQty} → {item.afterQty}</span>
                </div>
                <span className="text-[#747878]">
                  <ArrowRight className="h-6 w-6" />
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* §7 H3-8: "3 KPIs (kg at risk, ₹ at risk, % preventable)". */}
      <section className="grid gap-4 md:grid-cols-3">
        {data.kpis.map((kpi) => (
          <KpiCard key={kpi.label} data={kpi} />
        ))}
      </section>

      <section className="space-y-4 pt-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold tracking-tight text-[#1c1b1b]">Ranked actions</h2>
          <span className="text-sm uppercase tracking-[0.16em] text-[#646464]">All actions are derived from the mock contract.</span>
        </div>
        {data.recommendations.length === 0 ? (
          <EmptyState
            title="Nothing at risk right now"
            description="Every batch is inside its shelf life and no dish is over-prepped. This screen fills as the day runs."
          />
        ) : (
          <div className="space-y-4">
            {data.recommendations.map((item) => (
              <RecommendationCard key={item.id} data={item} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}