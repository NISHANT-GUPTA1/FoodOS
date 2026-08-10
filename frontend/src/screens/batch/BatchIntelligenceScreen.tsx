import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Check, MoveRight, SlidersHorizontal, ThermometerSun } from 'lucide-react'
import { acceptPlan, getBatch, getMarkets, getPlans, overridePlan } from '../../api/batchApi'
import type { BatchProfile, CandidatePlan } from '../../api/batchContract'
import { RecommendationCard } from '../../components/RecommendationCard'
import { SectionHeader } from '../../components/SectionHeader'
import { EmptyState, ErrorState, LoadingState } from '../../components/StatePanel'
import { ConfidenceBand } from '../../components/batch/ConfidenceBand'
import { DriverBars } from '../../components/batch/DriverBars'
import { PlanMatrixTable } from '../../components/batch/PlanMatrixTable'
import { RiskBadge } from '../../components/batch/RiskBadge'
import { RulCountdown } from '../../components/batch/RulCountdown'
import { SourceNote } from '../../components/batch/SourceNote'
import { riskToken } from '../../lib/risk'
import { formatIndianInr, formatKgWhole, formatTimestamp } from '../../utils/format'

/**
 * Screen 3 — Batch Intelligence. The hero.
 *
 * Quality, maturity, field heat, RUL as a live countdown, expected loss as a band,
 * ranked model drivers, the recommended plan, and every candidate the planner scored
 * underneath it. This is the screen the demo lives on.
 */
export function BatchIntelligenceScreen() {
  const { id = 'T1024' } = useParams()
  const navigate = useNavigate()

  const batch = useQuery({ queryKey: ['batch', id], queryFn: () => getBatch(id) })
  const plans = useQuery({ queryKey: ['plans', id], queryFn: () => getPlans(id) })
  const markets = useQuery({ queryKey: ['markets', 'tomato'], queryFn: () => getMarkets() })

  if (batch.isLoading) {
    return <LoadingState title="Loading batch intelligence" description="Fetching state, risk, drivers and the candidate plans." />
  }

  if (batch.isError || !batch.data) {
    return (
      <ErrorState
        title="Batch not available"
        description="This consignment could not be loaded. It may not have been assessed yet, or the batch endpoint is down."
        action={
          <button type="button" className="button-primary" onClick={() => navigate('/command')}>
            Back to Command Center
          </button>
        }
      />
    )
  }

  const profile = batch.data

  return (
    <div className="space-y-8">
      <BatchHeader profile={profile} onSimulate={() => navigate(`/batches/${profile.id}/simulate`)} />

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-5">
          <StateGrid profile={profile} />
          <ConfidenceBand risk={profile.risk} />
        </div>
        {/* `drivers[]` may be empty — hide the block rather than render an empty chart. */}
        {profile.drivers.length > 0 ? (
          <DriverBars drivers={profile.drivers} modelRunId={profile.model_run_id ?? undefined} />
        ) : (
          <EmptyState
            title="No driver attribution yet"
            description="This batch was scored without a model run, so there is no ranked contribution to show. The loss figure above still stands — it came from the deterministic fallback."
          />
        )}
      </div>

      {/* `best_plan_id` and `recommendation` are null until plans are generated. */}
      {profile.recommendation && profile.best_plan_id !== null ? (
        <section className="space-y-3">
          <h2 className="text-lg font-extrabold tracking-tight text-slate-900">Recommended plan</h2>
          <RecommendationCard data={profile.recommendation} showActions={false} />
          <PlanActions planId={profile.best_plan_id} />
        </section>
      ) : (
        <EmptyState
          title="No plan recommended yet"
          description="The planner has not scored candidate actions for this consignment. Nothing is wrong — the batch is registered and its risk is above."
        />
      )}

      {plans.isLoading ? (
        <LoadingState title="Scoring candidate actions" description="Running every candidate through the objective function." />
      ) : plans.isError ? (
        <ErrorState
          tone="warning"
          title="Plan matrix unavailable"
          description="The recommendation above still stands — only the full candidate table failed to load."
          action={
            <button type="button" className="button-ghost" onClick={() => plans.refetch()}>
              Retry
            </button>
          }
        />
      ) : plans.data && plans.data.plans.length > 0 ? (
        <PlanMatrixTable
          plans={plans.data.plans}
          wPreserve={plans.data.w_preserve}
          modelRunId={plans.data.model_run_id}
          onSimulate={(plan: CandidatePlan) => navigate(`/batches/${profile.id}/simulate?plan=${plan.id}`)}
        />
      ) : (
        <EmptyState
          title="No candidate actions"
          description="The planner returned no alternatives for this consignment — the booked lane is the only feasible one."
        />
      )}

      <MarketPanel
        markets={markets.data}
        isLoading={markets.isLoading}
        isError={markets.isError}
        onRetry={() => markets.refetch()}
      />
    </div>
  )
}

function BatchHeader({ profile, onSimulate }: { profile: BatchProfile; onSimulate: () => void }) {
  const token = riskToken(profile.risk.level)

  return (
    <div className={`rounded-3xl border-2 ${token.border} bg-white/90 p-6 shadow-xl backdrop-blur-xl`}>
      <SectionHeader
        eyebrow={`Screen 3 · Batch Intelligence · ${profile.id}`}
        title={`${formatKgWhole(profile.qty_kg)} ${profile.commodity}`}
        description={`Harvested ${formatTimestamp(profile.harvested_at)} · ${profile.transport.replace('_', ' ')} · ${profile.packaging.replace(/_/g, ' ')}`}
        action={
          <button
            type="button"
            onClick={onSimulate}
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-900 bg-slate-900 px-5 py-3 text-xs font-bold uppercase tracking-wider text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-slate-800 active:scale-95"
          >
            <SlidersHorizontal className="h-4 w-4 text-emerald-400" />
            Open what-if
          </button>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <RiskBadge level={profile.risk.level} long />
        <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-700">
          {profile.origin}
          <MoveRight className="h-4 w-4 text-slate-400" />
          {profile.destination}
        </span>
        <SourceNote source={profile.source} label="Route & weather" />
      </div>
    </div>
  )
}

function StateGrid({ profile }: { profile: BatchProfile }) {
  const { state, risk } = profile

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white/80 p-5">
        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Quality score</p>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-5xl font-extrabold tabular-nums text-slate-900">
            {state.quality_score ?? '—'}
          </span>
          <span className="text-sm font-bold text-slate-500">/ 100</span>
          {state.grade ? (
            <span className="ml-auto rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-extrabold text-slate-700">
              Grade {state.grade}
            </span>
          ) : null}
        </div>
        <div className="mt-4 h-2 w-full rounded-full bg-slate-200/80">
          <div className="h-2 rounded-full bg-slate-800" style={{ width: `${state.quality_score ?? 0}%` }} />
        </div>
        {state.quality_score === null ? (
          <p className="mt-2 text-xs font-medium text-slate-500">
            Not scored yet — the questionnaire has not been submitted for this batch.
          </p>
        ) : null}
        <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
          <div>
            <dt className="font-bold uppercase tracking-wider text-slate-500">Maturity</dt>
            <dd className="mt-0.5 font-bold capitalize text-slate-900">{state.maturity ?? 'Not assessed'}</dd>
          </div>
          <div>
            <dt className="font-bold uppercase tracking-wider text-slate-500">Mechanical damage</dt>
            <dd className="mt-0.5 font-bold capitalize text-slate-900">{state.damage_factor ?? 'Not assessed'}</dd>
          </div>
        </dl>
      </div>

      <div className="space-y-4">
        <RulCountdown hours={risk.rul_hours} size="lg" />
        <div className="rounded-2xl border border-slate-200 bg-white/80 px-5 py-4">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-slate-500">
            <ThermometerSun className="h-3.5 w-3.5" />
            Field heat over 30 °C
          </div>
          <div className="mt-1 text-3xl font-extrabold tabular-nums text-slate-900">
            {state.field_heat_hours_over_30c === null ? '—' : `${state.field_heat_hours_over_30c} h`}
          </div>
          <p className="mt-1 text-xs font-medium text-slate-600">
            {state.field_heat_hours_over_30c === null
              ? 'Not captured yet — this comes from the condition step of the questionnaire.'
              : 'Accumulated between cutting and loading. The single largest driver below.'}
          </p>
        </div>
      </div>
    </div>
  )
}

function PlanActions({ planId }: { planId: number }) {
  const [reason, setReason] = useState('')
  const [showOverride, setShowOverride] = useState(false)

  const accept = useMutation({ mutationFn: () => acceptPlan(planId) })
  const override = useMutation({ mutationFn: () => overridePlan(planId, reason) })

  if (accept.isSuccess) {
    return (
      <p className="flex items-center gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800">
        <Check className="h-4 w-4" />
        Plan {planId} accepted and logged against this consignment.
      </p>
    )
  }

  if (override.isSuccess) {
    return (
      <p className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-bold text-amber-900">
        Plan {planId} overridden. Reason recorded — it becomes training signal, not a discarded click.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={accept.isPending}
          onClick={() => accept.mutate()}
          className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold uppercase text-white shadow-md transition hover:bg-emerald-700 active:scale-95 disabled:opacity-50"
        >
          <Check className="h-4 w-4" />
          Accept plan {planId}
        </button>
        <button
          type="button"
          onClick={() => setShowOverride((prev) => !prev)}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold uppercase text-slate-700 shadow-sm transition hover:bg-slate-100 active:scale-95"
        >
          Override
        </button>
      </div>

      {showOverride ? (
        <div className="flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white/80 p-4 sm:flex-row">
          <input
            type="text"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Why is this plan wrong? (recorded against the batch)"
            className="w-full rounded-xl border-2 border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          />
          <button
            type="button"
            disabled={reason.trim().length < 3 || override.isPending}
            onClick={() => override.mutate()}
            className="shrink-0 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold uppercase text-white transition hover:bg-slate-800 active:scale-95 disabled:opacity-40"
          >
            Record override
          </button>
        </div>
      ) : null}

      {(accept.isError || override.isError) ? (
        <p className="text-xs font-semibold text-rose-700">
          That did not reach the server. The plan is unchanged — try again.
        </p>
      ) : null}
    </div>
  )
}

function MarketPanel({
  markets,
  isLoading,
  isError,
  onRetry,
}: {
  markets: import('../../api/batchContract').MarketsResponse | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}) {
  if (isLoading) {
    return <LoadingState title="Loading mandi prices" description="Reading the destination price context." />
  }

  if (isError || !markets) {
    return (
      <ErrorState
        tone="warning"
        title="Mandi prices unavailable"
        description="Destination price context could not be loaded. Plan values above were scored with the last committed snapshot."
        action={
          <button type="button" className="button-ghost" onClick={onRetry}>
            Retry
          </button>
        }
      />
    )
  }

  return (
    <section className="rounded-3xl border-2 border-slate-300 bg-white/90 p-6 shadow-xl backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-4">
        <h3 className="text-lg font-extrabold tracking-tight text-slate-900">Destination price context</h3>
        <SourceNote source={markets.source} asOf={markets.as_of} label="Mandi prices" />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {markets.markets.map((market) => (
          <div key={market.mandi} className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-sm font-extrabold text-slate-900">{market.name}</p>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="font-mono text-2xl font-extrabold tabular-nums text-slate-900">
                ₹{market.price_per_kg.toFixed(2)}
              </span>
              <span className="text-xs font-bold text-slate-500">/kg</span>
              <span
                className={`ml-auto text-[11px] font-bold uppercase ${
                  market.trend === 'up' ? 'text-emerald-700' : market.trend === 'down' ? 'text-rose-700' : 'text-slate-500'
                }`}
              >
                {market.trend}
              </span>
            </div>
            <dl className="mt-3 space-y-1 text-[11px] font-medium text-slate-600">
              <div className="flex justify-between">
                <dt>Transit</dt>
                <dd className="font-bold tabular-nums text-slate-800">{market.transit_hours} h</dd>
              </div>
              <div className="flex justify-between">
                <dt>Distance</dt>
                <dd className="font-bold tabular-nums text-slate-800">{market.distance_km.toLocaleString('en-IN')} km</dd>
              </div>
              <div className="flex justify-between">
                <dt>Daily absorption</dt>
                <dd className="font-bold tabular-nums text-slate-800">
                  {formatIndianInr(market.daily_absorption_kg).replace('₹', '')} kg
                </dd>
              </div>
            </dl>
          </div>
        ))}
      </div>
    </section>
  )
}
