import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Coins,
  Pause,
  Play,
  PlusCircle,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
  Timer,
} from 'lucide-react'
import { fetchTodayDashboard } from '../api/mockApi'
import { RecommendationCard } from '../components/RecommendationCard'
import { ActionMatrixTable } from '../components/ActionMatrixTable'
import { CreateBatchModal } from '../components/CreateBatchModal'
import { ErrorState, LoadingState } from '../components/StatePanel'
import { SectionHeader } from '../components/SectionHeader'
import type { RecommendationData } from '../mocks/dashboard'

export function TodayScreen() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['today-dashboard'],
    queryFn: fetchTodayDashboard,
  })

  const [activeCardIndex, setActiveCardIndex] = useState(0)
  const [isAnimating, setIsAnimating] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)

  const recommendations = data?.recommendations ?? []
  const actionMatrix = data?.actionMatrix ?? []
  const batchProfile = data?.batchProfile

  // Fast Carousel Speed: Auto-cycles every 2 seconds (2000ms)!
  useEffect(() => {
    if (recommendations.length <= 1 || isPaused) return
    const timer = setInterval(() => {
      handleNext()
    }, 2000)
    return () => clearInterval(timer)
  }, [recommendations.length, isPaused, activeCardIndex])

  // Live ticking countdown for current active card
  const activeCard: RecommendationData | undefined = recommendations[activeCardIndex] || recommendations[0]
  const initialMinutes = activeCard ? (parseInt(activeCard.expiresIn) || 42) : 42
  const [secondsLeft, setSecondsLeft] = useState(initialMinutes * 60)

  useEffect(() => {
    setSecondsLeft(initialMinutes * 60)
  }, [activeCardIndex, initialMinutes])

  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const minutes = Math.floor(secondsLeft / 60)
  const seconds = secondsLeft % 60
  const formattedTimer = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`

  const handleNext = () => {
    if (isAnimating) return
    setIsAnimating(true)
    setActiveCardIndex((prev) => (prev + 1) % Math.max(1, recommendations.length))
    setTimeout(() => setIsAnimating(false), 350)
  }

  const handlePrev = () => {
    if (isAnimating) return
    setIsAnimating(true)
    setActiveCardIndex((prev) => (prev - 1 + recommendations.length) % Math.max(1, recommendations.length))
    setTimeout(() => setIsAnimating(false), 350)
  }

  const handleSelectCard = (index: number) => {
    if (index === activeCardIndex || isAnimating) return
    setIsAnimating(true)
    setActiveCardIndex(index)
    setTimeout(() => setIsAnimating(false), 350)
  }

  if (isLoading) {
    return <LoadingState title="Loading today’s recommendations" description="Pulling the latest mock recommendations into the shell." />
  }

  if (isError || !data || recommendations.length === 0 || !activeCard) {
    return <ErrorState title="Today failed to load" description="The shell is intact, but the mock response did not return. Retry once the data layer is connected." />
  }

  const sideCards = recommendations
    .map((item, idx) => ({ ...item, originalIndex: idx }))
    .filter((_, idx) => idx !== activeCardIndex)

  return (
    <div className="space-y-8 font-sans">
      {/* Create Batch Modal Trigger */}
      <CreateBatchModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onBatchCreated={(newBatch) => console.log('Created batch:', newBatch)}
      />

      <SectionHeader
        eyebrow="BATCH INTELLIGENCE & COMMAND CENTER"
        title="Today"
        description={data.hero}
        action={
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center gap-2 rounded-2xl bg-emerald-600 px-4 py-2.5 text-xs font-bold uppercase text-white shadow-lg shadow-emerald-600/30 hover:bg-emerald-700 active:scale-95 transition"
            >
              <PlusCircle className="h-4 w-4" />
              <span>Create New Batch</span>
            </button>
            <button
              onClick={() => setIsPaused(!isPaused)}
              className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-2 text-xs font-bold text-slate-800 shadow-md transition hover:bg-slate-50"
            >
              {isPaused ? <Play className="h-3.5 w-3.5 text-emerald-600" /> : <Pause className="h-3.5 w-3.5 text-amber-600" />}
              <span>{isPaused ? 'Resume Carousel' : 'Pause Carousel'}</span>
            </button>
          </div>
        }
      />

      {/* Atomic Entity: Batch #T1024 Live Biological Telemetry Card (Blueprint Section 3) */}
      {batchProfile && (
        <section className="rounded-3xl border-2 border-slate-300 bg-white/90 backdrop-blur-xl p-6 shadow-xl text-slate-900 font-sans">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-200 pb-5">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 border border-emerald-300 font-extrabold text-lg shadow-sm">
                🍅
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-2xl font-extrabold tracking-tight text-slate-900">{batchProfile.id}</h3>
                  <span className="rounded-full bg-rose-100 border border-rose-300 px-2.5 py-0.5 text-xs font-bold text-rose-800 uppercase animate-pulse">
                    Risk Status: {batchProfile.riskLevel}
                  </span>
                </div>
                <p className="text-xs text-slate-600 font-semibold mt-0.5">
                  {batchProfile.commodity} • {batchProfile.quantityKg.toLocaleString()} kg | {batchProfile.origin} → {batchProfile.destination}
                </p>
              </div>
            </div>

            {/* Quick Metrics Badges */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-2xl border border-slate-300 bg-slate-100 px-4 py-2 text-center">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Quality Score (Q)</div>
                <div className="text-lg font-extrabold text-slate-900">{batchProfile.qualityScore} / 100 <span className="text-xs text-emerald-700 font-semibold">(Grade B+)</span></div>
              </div>
              <div className="rounded-2xl border border-slate-300 bg-slate-100 px-4 py-2 text-center">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Remaining Useful Life</div>
                <div className="text-lg font-extrabold text-emerald-700">{batchProfile.rulHours} Hours</div>
              </div>
              <div className="rounded-2xl border border-slate-300 bg-rose-100 px-4 py-2 text-center">
                <div className="text-[10px] font-bold uppercase tracking-wider text-rose-700">Baseline Loss Risk</div>
                <div className="text-lg font-extrabold text-rose-800">{batchProfile.expectedLossPercent}% ({batchProfile.expectedLossKg} kg)</div>
              </div>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="bg-slate-50 p-3 rounded-2xl border border-slate-200">
              <span className="block text-[10px] uppercase font-bold text-slate-500">Physiological Maturity</span>
              <span className="font-extrabold text-slate-900 mt-0.5 block">{batchProfile.maturity}</span>
            </div>
            <div className="bg-slate-50 p-3 rounded-2xl border border-slate-200">
              <span className="block text-[10px] uppercase font-bold text-slate-500">Mechanical Damage</span>
              <span className="font-extrabold text-slate-900 mt-0.5 block">{batchProfile.mechanicalDamage}</span>
            </div>
            <div className="bg-slate-50 p-3 rounded-2xl border border-slate-200">
              <span className="block text-[10px] uppercase font-bold text-slate-500">Accumulated Field Heat</span>
              <span className="font-extrabold text-slate-900 mt-0.5 block">{batchProfile.fieldHeatHours} Hours at &gt;30°C</span>
            </div>
            <div className="bg-slate-50 p-3 rounded-2xl border border-slate-200">
              <span className="block text-[10px] uppercase font-bold text-slate-500">Recommended Intervention</span>
              <span className="font-extrabold text-emerald-700 mt-0.5 block">Plan 4 (Split + Early Departure)</span>
            </div>
          </div>
        </section>
      )}

      {/* Main Grid: Transparent Glass Big Screen & Side Swapping Cards */}
      <section className="grid grid-cols-1 gap-6 md:grid-cols-12">
        {/* Big Featured Screen with Transparent Glass & Rounded Rectangles */}
        <div
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => setIsPaused(false)}
          className={`relative overflow-hidden rounded-3xl border-2 border-slate-300 bg-white/80 backdrop-blur-2xl p-6 md:col-span-8 lg:p-8 shadow-2xl transition-all duration-500 ease-out ${
            isAnimating ? 'opacity-70 scale-[0.98]' : 'opacity-100 scale-100'
          }`}
        >
          {/* Subtle background image */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute inset-0 bg-gradient-to-r from-white/90 via-white/85 to-white/60 z-10" />
            <img
              alt="Culinary craft"
              className="h-full w-full object-cover opacity-30 transition-opacity duration-500"
              src={
                activeCard.horizon === 'PREVENT'
                  ? 'https://lh3.googleusercontent.com/aida-public/AB6AXuBvBjqGiRZpP-OOpAO-MPwti4iwe_mfDUbfdTZMscv7jsL1ohZBD2-SEHefCuSNX6FO59v80CatLC8a4lVN6Lu-5SmQGKfrqACZnhyVco5MiuOn7AofHfuzHZxyiv1jz4XI93nCgmVNrgvmydUnUhG5YW4IVXBLq6O_W2dVfPExc96BrKbICRcd8CfOTZWyi5mHBR6tudi4DujrAzZQQ2WRAVL2qAok_BJGmOwWv-r6cPw-Dz1pGkvCKw'
                  : activeCard.horizon === 'PRESERVE'
                  ? 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1600&q=80'
                  : 'https://images.unsplash.com/photo-1642615835477-d303d7dc9ee9?w=1600&q=80'
              }
            />
          </div>

          {/* Horizon Badge, Live Timer & Navigation */}
          <div className="relative z-20 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1 text-xs font-bold uppercase tracking-widest text-white shadow-md ${
                  activeCard.horizon === 'PREVENT'
                    ? 'bg-emerald-600'
                    : activeCard.horizon === 'PRESERVE'
                    ? 'bg-sky-600'
                    : 'bg-teal-600'
                }`}
              >
                {activeCard.horizon === 'PREVENT' ? (
                  <ShieldCheck className="h-3.5 w-3.5" />
                ) : activeCard.horizon === 'PRESERVE' ? (
                  <Clock3 className="h-3.5 w-3.5" />
                ) : (
                  <Check className="h-3.5 w-3.5" />
                )}
                <span>Critical Action • {activeCard.horizon}</span>
              </div>

              {/* LIVE EXPIRY COUNTDOWN TIMER BADGE */}
              <div className="flex items-center gap-1.5 rounded-full bg-rose-100 border border-rose-300 px-3 py-1 text-xs font-extrabold text-rose-800 shadow-sm animate-pulse">
                <Timer className="h-3.5 w-3.5 text-rose-600" />
                <span>Expires in {formattedTimer}</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handlePrev}
                className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-700 shadow-sm transition hover:bg-slate-100 hover:scale-105"
                title="Previous recommendation"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={handleNext}
                className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-700 shadow-sm transition hover:bg-slate-100 hover:scale-105"
                title="Next recommendation"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Main Card Content */}
          <div className="relative z-20 mt-6 grid grid-cols-1 gap-8 lg:grid-cols-2">
            <div className="flex flex-col justify-between">
              <div>
                <h2 className="mb-3 text-3xl font-extrabold tracking-tight text-slate-900 lg:text-5xl">
                  {activeCard.title}
                </h2>
                <p className="max-w-2xl text-base leading-relaxed text-slate-700 font-medium">{activeCard.subtitle}</p>
                <p className="mt-3 text-xs font-medium text-slate-700 bg-slate-100/90 border border-slate-300 p-3 rounded-2xl shadow-sm">
                  💡 <span className="font-bold text-slate-900">Driver:</span> {activeCard.why}
                </p>
              </div>

              <div className="mt-6 flex items-end gap-4">
                <div className="flex flex-col">
                  <span className="mb-1 text-xs uppercase tracking-widest text-slate-500 font-bold">Current Plan</span>
                  <span className="text-5xl font-semibold text-slate-400 line-through">
                    {activeCard.beforeQty}
                  </span>
                </div>
                <div className="mb-3 text-slate-400">
                  <ChevronRight className="h-8 w-8" />
                </div>
                <div className="flex flex-col">
                  <span className="mb-1 text-xs uppercase tracking-widest text-emerald-700 font-bold">Optimized</span>
                  <span className="text-5xl font-extrabold text-emerald-600">
                    {activeCard.afterQty}
                    <span className="ml-1 text-base font-medium text-slate-700">kg</span>
                  </span>
                </div>
              </div>
            </div>

            <div className="flex flex-col justify-between border-t lg:border-t-0 lg:border-l border-slate-300 pt-6 lg:pt-0 lg:pl-8">
              <div className="w-full rounded-2xl border border-slate-300 bg-white/90 backdrop-blur-md p-5 shadow-md">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-extrabold uppercase tracking-widest text-slate-600">
                    Ingredient Preservation
                  </h3>
                  <span className="text-xs font-bold text-emerald-800 bg-emerald-100 border border-emerald-300 px-2.5 py-0.5 rounded-full">
                    Confidence {(activeCard.confidence * 100).toFixed(0)}%
                  </span>
                </div>

                <div className="flex flex-col gap-3.5">
                  <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                    <div className="flex items-center gap-2 text-slate-900 font-medium">
                      <Scale className="h-4 w-4 text-emerald-600" />
                      <span className="text-sm">Waste Avoided</span>
                    </div>
                    <span className="font-extrabold text-slate-900">{activeCard.saves.kg} kg</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                    <div className="flex items-center gap-2 text-slate-900 font-medium">
                      <Coins className="h-4 w-4 text-emerald-600" />
                      <span className="text-sm">Value Preserved</span>
                    </div>
                    <span className="font-extrabold text-emerald-700">₹{activeCard.saves.inr.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-slate-900 font-medium">
                      <RefreshCw className="h-4 w-4 text-emerald-600" />
                      <span className="text-sm">CO2e Saved</span>
                    </div>
                    <span className="font-extrabold text-slate-900">{activeCard.saves.co2e} kg</span>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex gap-3">
                <button className="flex-1 rounded-2xl border-2 border-slate-300 bg-white py-3.5 text-xs font-extrabold uppercase text-slate-800 shadow-md hover:bg-slate-100 transition-all active:scale-95">
                  Override
                </button>
                <button className="flex-1 rounded-2xl bg-emerald-600 py-3.5 text-xs font-extrabold uppercase text-white shadow-lg shadow-emerald-600/30 hover:bg-emerald-700 transition-all active:scale-95">
                  Accept Plan
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Side Column Queue with Rounded Rectangles & Glassmorphism */}
        <div className="md:col-span-4 flex flex-col gap-4">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-700 px-1">
            <span>Side Queue (Click to Swap)</span>
            <Sparkles className="h-3.5 w-3.5 text-emerald-600 animate-pulse" />
          </div>

          {sideCards.map((item) => (
            <div
              key={item.id}
              onClick={() => handleSelectCard(item.originalIndex)}
              className="group relative cursor-pointer rounded-3xl border-2 border-slate-300/80 bg-white/80 backdrop-blur-xl p-5 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-emerald-500 hover:bg-white/95 hover:shadow-2xl"
            >
              <div className="flex items-center justify-between mb-2.5">
                <div
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-widest text-white shadow-sm ${
                    item.horizon === 'PREVENT'
                      ? 'bg-emerald-600'
                      : item.horizon === 'PRESERVE'
                      ? 'bg-sky-600'
                      : 'bg-teal-600'
                  }`}
                >
                  {item.horizon === 'PREVENT' ? (
                    <ShieldCheck className="h-3 w-3" />
                  ) : item.horizon === 'PRESERVE' ? (
                    <Clock3 className="h-3 w-3" />
                  ) : (
                    <Check className="h-3 w-3" />
                  )}
                  <span>{item.horizon}</span>
                </div>

                <span className="text-[10px] font-extrabold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                  Click to Swap ↗
                </span>
              </div>

              <div>
                <h3 className="text-lg font-bold tracking-tight text-slate-900 group-hover:text-emerald-700 transition">
                  {item.title}
                </h3>
                <p className="mt-1 text-xs leading-relaxed text-slate-600 line-clamp-2">{item.subtitle}</p>
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3 text-xs">
                <div className="flex flex-col">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Qty</span>
                  <span className="font-bold text-slate-900">
                    {item.beforeQty} → {item.afterQty} kg
                  </span>
                </div>
                <div className="flex items-center gap-1 text-emerald-700 font-extrabold">
                  <span>Saves ₹{item.saves.inr}</span>
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Deterministic Action Evaluation Matrix (Blueprint Section 5) */}
      <section className="pt-2">
        <ActionMatrixTable candidates={actionMatrix} />
      </section>

      {/* Full Ranked Actions List */}
      <section className="space-y-4 pt-2">
        <div className="flex items-center justify-between gap-3 border-b border-slate-300 pb-2">
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Ranked Actions List</h2>
          <span className="text-xs uppercase tracking-wider font-bold text-slate-500">
            All actions derived from cluster decision engine.
          </span>
        </div>
        <div className="space-y-4">
          {data.recommendations.map((item, idx) => (
            <div
              key={item.id}
              onClick={() => handleSelectCard(idx)}
              className={`cursor-pointer transition rounded-3xl ${
                idx === activeCardIndex ? 'ring-4 ring-emerald-500/50 rounded-3xl shadow-xl' : ''
              }`}
            >
              <RecommendationCard data={item} />
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}