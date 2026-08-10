import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Loader2, RotateCcw } from 'lucide-react'
import { getMarkets, getPlans, simulate } from '../../api/batchApi'
import type { CandidatePlan, MarketRow, SimulateRequest, TransportMode } from '../../api/batchContract'
import { SectionHeader } from '../../components/SectionHeader'
import { ErrorState, LoadingState } from '../../components/StatePanel'
import { AnimatedNumber } from '../../components/batch/AnimatedNumber'
import { SourceNote } from '../../components/batch/SourceNote'
import { RISK } from '../../lib/risk'
import { formatIndianInr, formatInrDelta, formatKgWhole, formatTonnes } from '../../utils/format'

const TRANSPORT_OPTIONS: Array<{ value: TransportMode; label: string; hint: string }> = [
  { value: 'open_truck', label: 'Open truck', hint: '₹14.88/km' },
  { value: 'tarpaulin', label: 'Tarpaulin', hint: '₹16.30/km' },
  { value: 'reefer', label: 'Reefer', hint: '₹24.50/km' },
]

const DEBOUNCE_MS = 120

/**
 * Screen 4 — What-If Simulator.
 *
 * Four controls, exactly the four the contract's simulate body carries. The baseline
 * stays on screen at all times so every figure is read as a delta, never as an
 * isolated number.
 *
 * This is the judge-interaction moment, so the debounce is 120 ms and the mock call is
 * 90 ms: a drag must feel like it is moving the number, not queuing a request.
 */
export function WhatIfScreen() {
  const { id = 'T1024' } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const plans = useQuery({ queryKey: ['plans', id], queryFn: () => getPlans(id) })
  const markets = useQuery({ queryKey: ['markets', 'tomato'], queryFn: () => getMarkets() })

  const baseline = plans.data?.plans.find((p) => p.is_baseline)
  const best = plans.data?.plans.find((p) => p.is_best)
  const qtyKg = baseline ? Math.round(baseline.terms.surviving_kg + baseline.loss_kg) : 10_000

  const [shift, setShift] = useState(0)
  const [transport, setTransport] = useState<TransportMode>('open_truck')
  const [selected, setSelected] = useState<string[]>(['delhi_apmc'])
  const [primaryShare, setPrimaryShare] = useState(60)

  // Deep-link from a plan matrix row: preload that candidate's shape.
  useEffect(() => {
    const planId = searchParams.get('plan')
    if (!planId || !best) return
    if (Number(planId) === best.id) {
      setShift(-6)
      setTransport('open_truck')
      setSelected(['delhi_apmc', 'jaipur_apmc'])
      setPrimaryShare(60)
    }
  }, [searchParams, best])

  const destinations = useMemo(() => {
    if (selected.length === 0) return []
    if (selected.length === 1) return [{ mandi: selected[0], qty_kg: qtyKg }]
    const primary = Math.round((qtyKg * primaryShare) / 100 / 100) * 100
    return [
      { mandi: selected[0], qty_kg: primary },
      { mandi: selected[1], qty_kg: qtyKg - primary },
      ...selected.slice(2).map((mandi) => ({ mandi, qty_kg: 0 })),
    ].filter((d) => d.qty_kg > 0)
  }, [selected, primaryShare, qtyKg])

  const request: SimulateRequest = useMemo(
    () => ({ departure_shift_hours: shift, transport, destinations }),
    [shift, transport, destinations],
  )

  const [debounced, setDebounced] = useState(request)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(request), DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [request])

  const simulation = useQuery({
    queryKey: ['simulate', id, debounced],
    queryFn: () => simulate(id, debounced),
    enabled: debounced.destinations.length > 0,
    placeholderData: (previous) => previous,
  })

  if (plans.isLoading) {
    return <LoadingState title="Loading the baseline" description="The simulator needs a baseline before it can show a delta." />
  }

  if (plans.isError || !baseline) {
    return (
      <ErrorState
        title="Simulator unavailable"
        description="Without a scored baseline every figure here would be an absolute with nothing to compare against, so the screen refuses to render one."
        action={
          <button type="button" className="button-primary" onClick={() => navigate(`/batches/${id}`)}>
            Back to batch intelligence
          </button>
        }
      />
    )
  }

  const result = simulation.data
  const reset = () => {
    setShift(0)
    setTransport('open_truck')
    setSelected(['delhi_apmc'])
    setPrimaryShare(60)
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow={`Screen 4 · What-If · ${id}`}
        title="Move a lever, watch the loss move"
        description="Every figure is scored through the same objective function that produced the recommendation. The baseline stays on screen so nothing is read in isolation."
        action={
          <div className="flex gap-2">
            <button
              type="button"
              onClick={reset}
              className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-700 transition hover:bg-slate-100 active:scale-95"
            >
              <RotateCcw className="h-4 w-4" />
              Reset
            </button>
            <button
              type="button"
              onClick={() => navigate(`/batches/${id}`)}
              className="inline-flex items-center gap-2 rounded-2xl border border-slate-900 bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white transition hover:bg-slate-800 active:scale-95"
            >
              <ArrowLeft className="h-4 w-4 text-emerald-400" />
              Batch
            </button>
          </div>
        }
      />

      <ComparisonBar baseline={baseline} result={result} pending={simulation.isFetching} />

      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <section className="space-y-5 rounded-3xl border-2 border-slate-300 bg-white/90 p-6 shadow-xl backdrop-blur-xl">
          <Control
            label="Departure shift"
            value={shift === 0 ? 'As scheduled' : shift < 0 ? `${Math.abs(shift)} h earlier` : `${shift} h later`}
            hint="Negative moves the load out of the midday thermal peak."
          >
            <input
              type="range"
              min={-12}
              max={12}
              step={1}
              value={shift}
              onChange={(event) => setShift(Number(event.target.value))}
              className="input-range"
              aria-label="Departure shift in hours"
            />
            <div className="mt-1 flex justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
              <span>−12 h</span>
              <span>0</span>
              <span>+12 h</span>
            </div>
          </Control>

          <Control label="Transport mode" hint="Cooling factor against cost per kilometre.">
            <div className="grid grid-cols-3 gap-2">
              {TRANSPORT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setTransport(option.value)}
                  className={`rounded-2xl border-2 px-3 py-2.5 text-center transition active:scale-95 ${
                    transport === option.value
                      ? 'border-emerald-500 bg-emerald-50'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <span className="block text-xs font-extrabold text-slate-900">{option.label}</span>
                  <span className="mt-0.5 block text-[10px] font-semibold text-slate-500">{option.hint}</span>
                </button>
              ))}
            </div>
          </Control>

          <Control
            label="Destinations"
            value={`${selected.length} selected`}
            hint="Pick two to split the batch. Order matters — the first takes the primary share."
          >
            <div className="grid gap-2 sm:grid-cols-2">
              {(markets.data?.markets ?? []).map((market: MarketRow) => {
                const index = selected.indexOf(market.mandi)
                const active = index >= 0
                return (
                  <button
                    key={market.mandi}
                    type="button"
                    onClick={() =>
                      setSelected((prev) =>
                        prev.includes(market.mandi)
                          ? prev.filter((m) => m !== market.mandi)
                          : [...prev, market.mandi].slice(-2),
                      )
                    }
                    className={`flex items-center justify-between gap-2 rounded-2xl border-2 px-3 py-2.5 text-left transition active:scale-[0.98] ${
                      active ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <span>
                      <span className="block text-xs font-extrabold text-slate-900">{market.name}</span>
                      <span className="mt-0.5 block text-[10px] font-semibold text-slate-500">
                        ₹{market.price_per_kg.toFixed(2)}/kg · {market.transit_hours} h
                      </span>
                    </span>
                    {active ? (
                      <span className="shrink-0 rounded-full bg-emerald-600 px-1.5 py-0.5 font-mono text-[10px] font-extrabold text-white">
                        {index + 1}
                      </span>
                    ) : null}
                  </button>
                )
              })}
            </div>
          </Control>

          <Control
            label="Split allocation"
            value={selected.length < 2 ? 'Single destination' : `${primaryShare}% / ${100 - primaryShare}%`}
            hint={selected.length < 2 ? 'Select a second destination to allocate a split.' : undefined}
          >
            <input
              type="range"
              min={10}
              max={90}
              step={5}
              value={primaryShare}
              disabled={selected.length < 2}
              onChange={(event) => setPrimaryShare(Number(event.target.value))}
              className="input-range disabled:opacity-40"
              aria-label="Primary destination share"
            />
            {destinations.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {destinations.map((leg) => (
                  <span
                    key={leg.mandi}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-[11px] font-bold text-slate-700"
                  >
                    {formatTonnes(leg.qty_kg)} → {markets.data?.markets.find((m) => m.mandi === leg.mandi)?.name ?? leg.mandi}
                  </span>
                ))}
              </div>
            ) : null}
          </Control>

          <SourceNote source={markets.data?.source} asOf={markets.data?.as_of} label="Mandi prices" />
        </section>

        <ResultPanel baseline={baseline} result={result} best={best} pending={simulation.isFetching} isError={simulation.isError} />
      </div>
    </div>
  )
}

function Control({
  label,
  value,
  hint,
  children,
}: {
  label: string
  value?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</span>
        {value ? <span className="font-mono text-sm font-extrabold text-slate-900">{value}</span> : null}
      </div>
      {hint ? <p className="mt-0.5 text-[11px] text-slate-500">{hint}</p> : null}
      <div className="mt-2.5">{children}</div>
    </div>
  )
}

function ComparisonBar({
  baseline,
  result,
  pending,
}: {
  baseline: CandidatePlan
  result: CandidatePlan | undefined
  pending: boolean
}) {
  const lossDelta = result ? result.loss_pct - baseline.loss_pct : 0
  const valueDelta = result ? result.net_value - baseline.net_value : 0
  const kgSaved = result ? baseline.loss_kg - result.loss_kg : 0

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Figure
        label="Expected loss"
        baselineText={`baseline ${baseline.loss_pct.toFixed(1)}%`}
        tone={lossDelta < 0 ? RISK.LOW : lossDelta > 0 ? RISK.HIGH : RISK.MEDIUM}
        pending={pending}
      >
        <AnimatedNumber
          value={result?.loss_pct ?? baseline.loss_pct}
          format={(v) => `${v.toFixed(1)}%`}
          className="text-5xl font-extrabold"
        />
        <span className="ml-2 text-sm font-bold">
          {lossDelta === 0 ? '—' : `${lossDelta > 0 ? '+' : '−'}${Math.abs(lossDelta).toFixed(1)} pt`}
        </span>
      </Figure>

      <Figure
        label="Net value V(a)"
        baselineText={`baseline ${formatIndianInr(baseline.net_value)}`}
        tone={valueDelta > 0 ? RISK.LOW : valueDelta < 0 ? RISK.HIGH : RISK.MEDIUM}
        pending={pending}
      >
        <AnimatedNumber
          value={result?.net_value ?? baseline.net_value}
          format={(v) => formatIndianInr(v)}
          className="text-4xl font-extrabold"
        />
        <span className="ml-2 text-sm font-bold">{valueDelta === 0 ? '—' : formatInrDelta(valueDelta)}</span>
      </Figure>

      <Figure
        label="Food kept in the system"
        baselineText={`baseline loses ${formatKgWhole(baseline.loss_kg)}`}
        tone={kgSaved > 0 ? RISK.LOW : kgSaved < 0 ? RISK.HIGH : RISK.MEDIUM}
        pending={pending}
      >
        <AnimatedNumber
          value={kgSaved}
          format={(v) => `${v >= 0 ? '+' : '−'}${Math.abs(Math.round(v)).toLocaleString('en-IN')} kg`}
          className="text-4xl font-extrabold"
        />
      </Figure>
    </div>
  )
}

function Figure({
  label,
  baselineText,
  tone,
  pending,
  children,
}: {
  label: string
  baselineText: string
  tone: typeof RISK.LOW
  pending: boolean
  children: React.ReactNode
}) {
  return (
    <div className={`rounded-3xl border-2 ${tone.border} ${tone.bg} p-5 shadow-sm transition-colors duration-300`}>
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
        {pending ? <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" /> : null}
      </div>
      <div className={`mt-2 flex items-baseline ${tone.text}`}>{children}</div>
      <p className="mt-1.5 text-[11px] font-semibold text-slate-500">{baselineText}</p>
    </div>
  )
}

function ResultPanel({
  baseline,
  result,
  best,
  pending,
  isError,
}: {
  baseline: CandidatePlan
  result: CandidatePlan | undefined
  best: CandidatePlan | undefined
  pending: boolean
  isError: boolean
}) {
  if (isError) {
    return (
      <ErrorState
        tone="warning"
        title="Simulation did not return"
        description="The last good result is still on screen above. Move a control to try again."
      />
    )
  }

  if (!result) {
    return (
      <section className="rounded-3xl border-2 border-dashed border-slate-300 bg-white/70 p-6 text-center">
        <p className="text-sm font-semibold text-slate-600">
          Allocate at least one destination to score a scenario.
        </p>
      </section>
    )
  }

  const rows: Array<[string, string, string]> = [
    ['Gross revenue', formatIndianInr(result.gross_revenue), formatIndianInr(baseline.gross_revenue)],
    ['Logistics cost', `− ${formatIndianInr(result.logistics_cost)}`, `− ${formatIndianInr(baseline.logistics_cost)}`],
    ['Surviving mass', formatKgWhole(result.terms.surviving_kg), formatKgWhole(baseline.terms.surviving_kg)],
    ['Expected price', `₹${result.terms.expected_price_per_kg.toFixed(2)}/kg`, `₹${baseline.terms.expected_price_per_kg.toFixed(2)}/kg`],
    [`Mass penalty (λ = ₹${result.terms.w_preserve}/kg)`, `− ${formatIndianInr(result.terms.mass_penalty)}`, `− ${formatIndianInr(baseline.terms.mass_penalty)}`],
    ['Ranking value', formatIndianInr(result.terms.ranking_value), formatIndianInr(baseline.terms.ranking_value)],
    ['RUL at these conditions', `${Math.round(result.rul_hours ?? 0)} h`, `${Math.round(baseline.rul_hours ?? 0)} h`],
  ]

  const beatsBest = best ? result.terms.ranking_value > best.terms.ranking_value : false

  return (
    <section className="rounded-3xl border-2 border-slate-300 bg-white/90 p-6 shadow-xl backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-4">
        <div>
          <h3 className="text-lg font-extrabold tracking-tight text-slate-900">This scenario</h3>
          <p className="mt-0.5 text-xs font-medium text-slate-600">{result.label}</p>
        </div>
        {pending ? <Loader2 className="h-4 w-4 animate-spin text-slate-400" /> : null}
      </div>

      <table className="mt-4 w-full text-left text-xs">
        <thead>
          <tr className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            <th className="pb-2">Term of V(a)</th>
            <th className="pb-2 text-right">This scenario</th>
            <th className="pb-2 text-right">Baseline</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(([term, now, base]) => (
            <tr key={term}>
              <td className="py-2 font-semibold text-slate-700">{term}</td>
              <td className="py-2 text-right font-mono font-extrabold tabular-nums text-slate-900">{now}</td>
              <td className="py-2 text-right font-mono tabular-nums text-slate-500">{base}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {best ? (
        <p
          className={`mt-4 rounded-2xl border px-4 py-3 text-xs font-semibold ${
            beatsBest ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-slate-200 bg-slate-50 text-slate-600'
          }`}
        >
          {beatsBest
            ? `This scenario beats the recommended plan by ${formatInrDelta(result.terms.ranking_value - best.terms.ranking_value)} on ranking value. Worth accepting as an override.`
            : `The recommended plan — ${best.label} — still ranks ${formatInrDelta(best.terms.ranking_value - result.terms.ranking_value)} higher.`}
        </p>
      ) : null}
    </section>
  )
}
