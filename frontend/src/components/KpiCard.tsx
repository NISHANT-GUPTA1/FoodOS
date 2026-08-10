import { ArrowUpRight } from 'lucide-react'
import type { KpiCardData } from '../mocks/dashboard'

interface KpiCardProps {
  data: KpiCardData
}

// Horizon tokens, same single definition as index.css / tailwind.config.js.
const toneClasses: Record<KpiCardData['tone'], string> = {
  prevent: 'from-prevent/25 to-prevent/5 border-prevent/20',
  preserve: 'from-preserve/25 to-preserve/5 border-preserve/20',
  recover: 'from-recover/25 to-recover/5 border-recover/20',
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
    </div>
  )
}