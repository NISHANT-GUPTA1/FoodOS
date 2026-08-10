import { useState, useEffect } from 'react'
import { Check, Clock3, Flame, RotateCcw, Timer } from 'lucide-react'
import type { RecommendationData } from '../mocks/dashboard'
import { formatCo2e, formatInr } from '../utils/format'

interface RecommendationCardProps {
  data: RecommendationData
}

const horizonStyles: Record<RecommendationData['horizon'], { border: string; chip: string; icon: React.ReactNode }> = {
  PREVENT: {
    border: 'border-emerald-500/40',
    chip: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    icon: <Flame className="h-4 w-4" />,
  },
  PRESERVE: {
    border: 'border-amber-500/40',
    chip: 'bg-amber-100 text-amber-900 border-amber-300',
    icon: <Clock3 className="h-4 w-4" />,
  },
  RECOVER: {
    border: 'border-rose-500/40',
    chip: 'bg-rose-100 text-rose-900 border-rose-300',
    icon: <RotateCcw className="h-4 w-4" />,
  },
}

export function RecommendationCard({ data }: RecommendationCardProps) {
  const style = horizonStyles[data.horizon]

  // Parse initial minutes from string like "84 min"
  const initialMinutes = parseInt(data.expiresIn) || 45
  const [secondsLeft, setSecondsLeft] = useState(initialMinutes * 60)

  // Real-time ticking timer countdown
  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const minutes = Math.floor(secondsLeft / 60)
  const seconds = secondsLeft % 60
  const formattedTimer = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`

  return (
    <article className={`rounded-3xl border-2 ${style.border} bg-white/80 backdrop-blur-xl p-6 text-slate-900 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:bg-white/90 hover:shadow-2xl`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border shadow-sm ${style.chip}`}>
              {style.icon} <span>{data.horizon}</span>
            </span>

            <span className="rounded-full bg-slate-100 border border-slate-300 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-slate-700">
              Confidence {Math.round(data.confidence * 100)}%
            </span>

            {/* LIVE REAL-TIME COUNTDOWN TIMER BADGE */}
            <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 border border-rose-300 px-3 py-1 text-xs font-bold text-rose-700 shadow-sm animate-pulse">
              <Timer className="h-3.5 w-3.5 text-rose-600" />
              <span>Expires in {formattedTimer} min</span>
            </span>
          </div>

          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">{data.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-700 font-medium">{data.subtitle}</p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-300/80 bg-slate-50/90 backdrop-blur-md px-5 py-4 text-right shadow-sm">
          <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Quantity Transition</div>
          <div className="mt-1 text-3xl font-extrabold text-slate-900">
            {data.beforeQty} <span className="text-slate-400 font-light">→</span> {data.afterQty}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[1.3fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Decision Driver (Why)</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-800 font-medium">{data.why}</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Preservation Metrics</p>
          <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
            <div className="bg-white/80 p-2 rounded-xl border border-slate-200 text-center">
              <div className="text-[11px] text-slate-500 font-semibold">kg Saved</div>
              <div className="mt-0.5 font-bold text-emerald-700">{data.saves.kg} kg</div>
            </div>
            <div className="bg-white/80 p-2 rounded-xl border border-slate-200 text-center">
              <div className="text-[11px] text-slate-500 font-semibold">₹ Saved</div>
              <div className="mt-0.5 font-bold text-emerald-700">{formatInr(data.saves.inr)}</div>
            </div>
            <div className="bg-white/80 p-2 rounded-xl border border-slate-200 text-center">
              <div className="text-[11px] text-slate-500 font-semibold">CO₂e</div>
              <div className="mt-0.5 font-bold text-emerald-700">{formatCo2e(data.saves.co2e)}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
        <div className="text-xs text-slate-600 font-medium">
          <span className="font-bold text-slate-900">{Math.round(data.confidence * 100)}% forecast confidence</span> from cluster node contract.
        </div>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold uppercase text-white shadow-md hover:bg-emerald-700 active:scale-95 transition-all">
            <Check className="h-4 w-4" />
            Accept Plan
          </button>
          <button type="button" className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold uppercase text-slate-700 shadow-sm hover:bg-slate-100 active:scale-95 transition-all">
            Override
          </button>
        </div>
      </div>
    </article>
  )
}