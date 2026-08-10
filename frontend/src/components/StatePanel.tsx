import { AlertTriangle, Loader2 } from 'lucide-react'

interface StatePanelProps {
  title: string
  description: string
  tone?: 'neutral' | 'warning' | 'critical'
  action?: React.ReactNode
}

const toneClasses: Record<NonNullable<StatePanelProps['tone']>, string> = {
  neutral: 'border-[#c4c7c8] bg-[#f1edec] text-[#1c1b1b]',
  warning: 'border-[#f59e0b] bg-[#fff7e6] text-[#1c1b1b]',
  critical: 'border-[#ef4444] bg-[#fff1f2] text-[#1c1b1b]',
}

export function LoadingState({ title, description }: StatePanelProps) {
  return (
    <div className={`panel flex min-h-[40vh] items-center justify-center ${toneClasses.neutral}`}>
      <div className="flex items-center gap-3 text-[#1c1b1b]">
        <Loader2 className="h-5 w-5 animate-spin text-[#5d5f5f]" />
        <span>
          <span className="block font-medium text-[#1c1b1b]">{title}</span>
          <span className="block text-sm text-[#444748]">{description}</span>
        </span>
      </div>
    </div>
  )
}

export function ErrorState({ title, description, tone = 'critical', action }: StatePanelProps) {
  return (
    <div className={`panel p-8 ${toneClasses[tone]}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-1 h-5 w-5 text-[#ba1a1a]" />
        <div>
          <h2 className="text-xl font-semibold text-[#1c1b1b]">{title}</h2>
          <p className="mt-2 text-sm leading-7 text-[#444748]">{description}</p>
          {action ? <div className="mt-4">{action}</div> : null}
        </div>
      </div>
    </div>
  )
}

export function EmptyState({ title, description, tone = 'neutral', action }: StatePanelProps) {
  return (
    <div className={`panel p-8 ${toneClasses[tone]}`}>
      <h2 className="text-xl font-semibold text-[#1c1b1b]">{title}</h2>
      <p className="mt-2 text-sm leading-7 text-[#444748]">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}