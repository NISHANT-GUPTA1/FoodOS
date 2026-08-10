import { Check, Clock3, Flame, RotateCcw } from 'lucide-react'
import type { RecommendationData } from '../mocks/dashboard'
import { formatCo2e, formatInr } from '../utils/format'

interface RecommendationCardProps {
  data: RecommendationData
}

const horizonStyles: Record<RecommendationData['horizon'], { border: string; chip: string; icon: React.ReactNode }> = {
  PREVENT: {
    border: 'border-emerald-400/20',
    chip: 'bg-emerald-400/15 text-emerald-200',
    icon: <Flame className="h-4 w-4" />,
  },
  PRESERVE: {
    border: 'border-amber-400/20',
    chip: 'bg-amber-400/15 text-amber-100',
    icon: <Clock3 className="h-4 w-4" />,
  },
  RECOVER: {
    border: 'border-rose-400/20',
    chip: 'bg-rose-400/15 text-rose-100',
    icon: <RotateCcw className="h-4 w-4" />,
  },
}

export function RecommendationCard({ data }: RecommendationCardProps) {
  const style = horizonStyles[data.horizon]

  return (
    <article className={`panel ${style.border} p-5 text-[#1c1b1b] transition hover:-translate-y-0.5 hover:border-[#747878]`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`chip border border-[#c4c7c8] bg-[#f1edec] ${style.chip.includes('emerald') ? 'text-emerald-700' : style.chip.includes('amber') ? 'text-[#9a6700]' : 'text-[#ba1a1a]'}`}>{style.icon} <span className="ml-2">{data.horizon}</span></span>
            <span className="text-xs uppercase tracking-[0.25em] text-[#646464]">Confidence {Math.round(data.confidence * 100)}%</span>
            <span className="text-xs uppercase tracking-[0.25em] text-[#646464]">Expires in {data.expiresIn}</span>
          </div>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-[#1c1b1b]">{data.title}</h2>
            <p className="mt-2 text-sm leading-7 text-[#444748]">{data.subtitle}</p>
          </div>
        </div>
        <div className="rounded-3xl border border-[#c4c7c8] bg-[#f6f3f2] px-5 py-4 text-right">
          <div className="text-xs uppercase tracking-[0.25em] text-[#646464]">Qty</div>
          <div className="mt-2 text-3xl font-semibold text-[#1c1b1b]">
            {data.beforeQty} <span className="text-[#747878]">→</span> {data.afterQty}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[1.3fr_0.9fr]">
        <div className="rounded-3xl border border-[#c4c7c8] bg-[#f6f3f2] p-4">
          <p className="text-xs uppercase tracking-[0.28em] text-[#646464]">Why</p>
          <p className="mt-3 text-sm leading-7 text-[#1c1b1b]">{data.why}</p>
        </div>
        <div className="rounded-3xl border border-[#c4c7c8] bg-[#f6f3f2] p-4">
          <p className="text-xs uppercase tracking-[0.28em] text-[#646464]">Saves</p>
          <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-[#646464]">kg</div>
              <div className="mt-1 font-semibold text-[#1c1b1b]">{data.saves.kg}</div>
            </div>
            <div>
              <div className="text-[#646464]">₹</div>
              <div className="mt-1 font-semibold text-[#1c1b1b]">{formatInr(data.saves.inr)}</div>
            </div>
            <div>
              <div className="text-[#646464]">CO₂e</div>
              <div className="mt-1 font-semibold text-[#1c1b1b]">{formatCo2e(data.saves.co2e)}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#c4c7c8] pt-4">
        <div className="text-sm text-[#444748]">
          <span className="font-medium text-[#1c1b1b]">{Math.round(data.confidence * 100)}%</span> confidence from the current mock contract.
        </div>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="button-primary">
            <Check className="h-4 w-4" />
            Accept
          </button>
          <button type="button" className="button-ghost">
            Override
          </button>
        </div>
      </div>
    </article>
  )
}