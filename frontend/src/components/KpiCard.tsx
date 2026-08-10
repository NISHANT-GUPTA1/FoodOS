import { ArrowUpRight } from 'lucide-react'
import type { KpiCardData } from '../mocks/dashboard'
import { formatPercent } from '../utils/format'

interface KpiCardProps {
  data: KpiCardData
}

const toneClasses: Record<KpiCardData['tone'], string> = {
  prevent: 'from-emerald-500/25 to-emerald-500/5 border-emerald-400/20',
  preserve: 'from-amber-500/25 to-amber-500/5 border-amber-400/20',
  recover: 'from-rose-500/25 to-rose-500/5 border-rose-400/20',
}

export function KpiCard({ data }: KpiCardProps) {
  return (
    <div className={`panel bg-gradient-to-br ${toneClasses[data.tone]} p-5 text-[#1c1b1b]`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-[#646464]">{data.label}</p>
          <div className="mt-4 text-4xl font-semibold tracking-tight text-[#1c1b1b]">{data.value}</div>
        </div>
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-[#c4c7c8] bg-[#f6f3f2] text-[#5d5f5f]">
          <ArrowUpRight className="h-4 w-4" />
        </span>
      </div>
      <div className="mt-5 flex items-center gap-2 text-sm text-[#1c1b1b]">
        <span className="chip border border-[#c4c7c8] bg-[#f1edec] text-[#1c1b1b]">{data.delta}</span>
        <span className="text-[#444748]">{data.note}</span>
      </div>
      <div className="mt-4 text-xs text-[#646464]">Tone marker: {formatPercent(data.tone === 'prevent' ? 0.63 : data.tone === 'preserve' ? 0.52 : 0.41)}</div>
    </div>
  )
}