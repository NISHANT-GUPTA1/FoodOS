import { Database, Wifi } from 'lucide-react'
import type { SourceStamp } from '../../api/batchContract'
import { formatTimestamp } from '../../utils/format'

interface SourceNoteProps {
  source: SourceStamp | undefined
  asOf?: string
  label?: string
}

/**
 * `source` is never hidden — Ruling 3. But a snapshot is the DESIGNED behaviour, not a
 * fault, so it renders as a quiet grey note and never as a warning.
 */
export function SourceNote({ source, asOf, label = 'Data' }: SourceNoteProps) {
  if (!source) return null

  const live = source === 'live'
  const Icon = live ? Wifi : Database

  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
      <Icon className="h-3 w-3" />
      {label}: {live ? 'live connector' : 'committed snapshot'}
      {asOf ? ` · ${formatTimestamp(asOf)}` : ''}
    </span>
  )
}
