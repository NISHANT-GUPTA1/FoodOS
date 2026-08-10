import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, CirclePlus, MoveRight } from 'lucide-react'
import { getBatches } from '../../api/batchApi'
import type { BatchListRow } from '../../api/batchContract'
import { KpiCard } from '../../components/KpiCard'
import { SectionHeader } from '../../components/SectionHeader'
import { EmptyState, ErrorState, LoadingState } from '../../components/StatePanel'
import { TrackChip } from '../../components/batch/DownstreamLots'
import { RiskBadge } from '../../components/batch/RiskBadge'
import { RulCountdown } from '../../components/batch/RulCountdown'
import { SourceNote } from '../../components/batch/SourceNote'
import { RISK, RISK_ORDER, riskToken, type RiskLevel } from '../../lib/risk'
import { formatIndianInr, formatKgWhole, formatLossPct } from '../../utils/format'

/**
 * Screen 1 — Command Center.
 *
 * A work queue, not a dashboard. Batches are grouped by risk, worst first, and every
 * row ends in an action. Nothing here is a vanity metric: if a number does not change
 * what someone does in the next hour, it is not on this screen.
 */
export function CommandCenterScreen() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<RiskLevel | ''>('')

  const query = useQuery({
    queryKey: ['batches', filter],
    queryFn: () => getBatches({ risk: filter }),
  })

  const grouped = useMemo(() => {
    const rows = query.data?.batches ?? []
    return RISK_ORDER.map((level) => ({ level, rows: rows.filter((row) => row.level === level) })).filter(
      (group) => group.rows.length > 0,
    )
  }, [query.data])

  const kpis = useMemo(() => {
    const rows = query.data?.batches ?? []
    const atRiskKg = rows.reduce((sum, row) => sum + row.loss_kg, 0)
    const recoverable = rows.reduce((sum, row) => sum + Math.max(0, row.delta_vs_baseline), 0)
    const actionable = rows.filter((row) => row.delta_vs_baseline > 0).length

    return [
      {
        label: 'kg at risk today',
        value: formatKgWhole(atRiskKg),
        delta: `${rows.length} live batches`,
        tone: 'recover' as const,
        note: 'Expected physical loss across every consignment under the baseline plan.',
      },
      {
        label: 'recoverable value',
        value: formatIndianInr(recoverable),
        delta: `${actionable} batches with a better plan`,
        tone: 'prevent' as const,
        note: 'Sum of Δ vs baseline on the best feasible plan for each batch.',
      },
      {
        label: 'needs a decision now',
        value: String(query.data?.counts.HIGH ?? 0),
        delta: 'RUL under 24 h',
        tone: 'preserve' as const,
        note: 'High-risk batches where the dispatch window is still open.',
      },
    ]
  }, [query.data])

  if (query.isLoading) {
    return <LoadingState title="Loading the batch queue" description="Reading consignments, risk scores and best plans." />
  }

  if (query.isError) {
    return (
      <ErrorState
        title="Batch queue unavailable"
        description="The batches endpoint did not answer. Nothing has been lost — retry, or keep working from the last loaded queue."
        action={
          <button type="button" className="button-primary" onClick={() => query.refetch()}>
            Retry
          </button>
        }
      />
    )
  }

  const counts = query.data?.counts

  return (
    <div className="space-y-8">
      <SectionHeader
        eyebrow="Screen 1 · Command Center"
        title="Every live consignment, worst first"
        description={
          counts
            ? `${counts.HIGH} High Risk · ${counts.LOW} Stable · ${counts.MEDIUM} Need Attention. Each row carries the one action that changes its outcome.`
            : 'Live consignments grouped by risk.'
        }
        action={
          <button
            type="button"
            onClick={() => navigate('/batches/new')}
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-900 bg-slate-900 px-5 py-3 text-xs font-bold uppercase tracking-wider text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-slate-800 active:scale-95"
          >
            <CirclePlus className="h-4 w-4 text-emerald-400" />
            Register batch
          </button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} data={kpi} />
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <FilterChip active={filter === ''} onClick={() => setFilter('')} label="All batches" />
          {RISK_ORDER.map((level) => (
            <FilterChip
              key={level}
              active={filter === level}
              onClick={() => setFilter(level)}
              label={`${RISK[level].group}${counts ? ` · ${counts[level]}` : ''}`}
              token={level}
            />
          ))}
        </div>
        <SourceNote source={query.data?.source} asOf={query.data?.as_of} label="Queue" />
      </div>

      {grouped.length === 0 ? (
        <EmptyState
          title="Nothing in this band"
          description="No consignment currently sits at this risk level. Clear the filter to see the full queue."
          action={
            <button type="button" className="button-ghost" onClick={() => setFilter('')}>
              Show all batches
            </button>
          }
        />
      ) : (
        <div className="space-y-8">
          {grouped.map((group) => (
            <section key={group.level} className="space-y-3">
              <div className="flex items-center gap-3">
                <span className={`h-2.5 w-2.5 rounded-full ${riskToken(group.level).dot}`} />
                <h2 className="text-lg font-extrabold tracking-tight text-slate-900">
                  {riskToken(group.level).group}
                </h2>
                <span className="rounded-full border border-slate-300 bg-white/80 px-2.5 py-0.5 text-xs font-bold text-slate-600">
                  {group.rows.length}
                </span>
              </div>

              <ul className="space-y-3">
                {group.rows.map((row) => (
                  <BatchQueueRow key={row.id} row={row} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}

function FilterChip({
  active,
  onClick,
  label,
  token,
}: {
  active: boolean
  onClick: () => void
  label: string
  token?: RiskLevel
}) {
  const risk = token ? riskToken(token) : null

  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider transition ${
        active
          ? risk
            ? `${risk.border} ${risk.bg} ${risk.text}`
            : 'border-slate-900 bg-slate-900 text-white'
          : 'border-slate-300 bg-white/80 text-slate-600 hover:bg-slate-100'
      }`}
    >
      {label}
    </button>
  )
}

function BatchQueueRow({ row }: { row: BatchListRow }) {
  const token = riskToken(row.level)

  return (
    <li>
      <Link
        to={`/batches/${row.id}`}
        className={`block rounded-2xl border-2 border-l-4 border-slate-200 ${token.accent} bg-white/85 p-4 shadow-sm backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lg`}
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-extrabold text-slate-900">{row.id}</span>
              <RiskBadge level={row.level} />
              <span className="text-sm font-bold capitalize text-slate-800">{row.commodity}</span>
              <span className="text-sm font-semibold text-slate-600">{formatKgWhole(row.qty_kg)}</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                {row.status.replace('_', ' ')}
              </span>
              {/* Shows only once the code has been taken into a node, so the
                  queue distinguishes "delivered" from "actually in someone's
                  stock" — two different states that `status` collapses. */}
              <TrackChip code={row.id} />
            </div>

            <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold text-slate-600">
              <span>{row.origin}</span>
              <MoveRight className="h-3.5 w-3.5 text-slate-400" />
              <span>{row.destination}</span>
            </div>

            <p className="flex items-start gap-1.5 text-sm font-medium text-slate-800">
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              <span>{row.best_action}</span>
            </p>
          </div>

          <div className="grid shrink-0 grid-cols-3 gap-4 lg:w-[22rem]">
            <Metric label="RUL">
              <RulCountdown hours={row.rul_hours} />
            </Metric>
            <Metric label="Loss">
              <span className={`font-mono text-lg font-extrabold tabular-nums ${token.text}`}>
                {formatLossPct(row.loss_pct)}
              </span>
              <span className="block text-[11px] font-semibold text-slate-500">{formatKgWhole(row.loss_kg)}</span>
            </Metric>
            <Metric label="Δ available">
              <span
                className={`font-mono text-lg font-extrabold tabular-nums ${
                  row.delta_vs_baseline > 0 ? 'text-emerald-700' : 'text-slate-400'
                }`}
              >
                {row.delta_vs_baseline > 0 ? formatIndianInr(row.delta_vs_baseline) : '—'}
              </span>
            </Metric>
          </div>
        </div>
      </Link>
    </li>
  )
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
      <div className="mt-1">{children}</div>
    </div>
  )
}
