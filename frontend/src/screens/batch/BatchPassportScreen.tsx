import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  getBatchProfile,
  getTimeline,
  qrSrc,
  reportEvent,
  splitBatch,
  type BatchEvent,
  type BatchProfile,
  type BatchRisk,
  type ReportEvent,
  type Timeline,
} from '../../api/passportApi'
import { SectionHeader } from '../../components/SectionHeader'
import { ErrorState, LoadingState } from '../../components/StatePanel'
import { RiskBadge } from '../../components/batch/RiskBadge'
import type { RiskLevel } from '../../lib/risk'
import { formatKgWhole, formatTimestamp } from '../../utils/format'

/**
 * Screen 5 — the Batch Passport.
 *
 * What a QR scan opens, and the screen the demo drives. Three jobs:
 *
 *  1. **Identity** — this crate is TOM-KLR-00124, it came from Kolar, and these
 *     are the hands it has passed through. The code never changes.
 *  2. **Timeline** — everything that has happened, with the model's belief at
 *     each point, so the before/after is on screen rather than asserted.
 *  3. **Report** — the demo controls. Click "+6 h delay" and the numbers move,
 *     because a judge watching the system react beats a judge being told it
 *     would.
 *
 * Every figure comes from the API. No arithmetic here beyond formatting.
 */

const LADDER = [
  'created',
  'assessed',
  'ready_for_dispatch',
  'in_transit',
  'arrived',
  'received',
  'in_inventory',
] as const

const EVENT_LABEL: Record<string, string> = {
  harvest: 'Harvested',
  field_hold: 'Held in field',
  packed: 'Packed',
  assessed: 'Assessed',
  photos_added: 'Photos added',
  dispatched: 'Dispatched',
  delay: 'Delayed',
  temperature_exposure: 'Heat exposure',
  arrived: 'Arrived',
  handoff: 'Handed over',
  received: 'Received',
  split: 'Split',
  diverted: 'Diverted',
  sold: 'Sold',
  processed: 'Processed',
  donated: 'Donated',
  wasted: 'Written off',
}

const title = (value: string) =>
  value.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

/** One line of plain English for an event's payload. */
function describe(event: BatchEvent): string | null {
  const p = event.payload ?? {}
  switch (event.type) {
    case 'delay':
      return `${p.duration_hours} h${p.cause ? ` — ${p.cause}` : ''}`
    case 'temperature_exposure':
      return `${p.temp_c} °C for ${p.hours} h`
    case 'handoff':
      return `${p.from_party ?? 'origin'} → ${p.to_party}${
        Number(p.rejected_kg) > 0 ? ` · ${p.rejected_kg} kg rejected at the gate` : ''
      }`
    case 'split':
      return `into ${(p.children as unknown[] | undefined)?.length ?? 0} child batches`
    case 'wasted':
      return `${event.qty_kg} kg${p.reason ? ` — ${title(String(p.reason))}` : ''}`
    default:
      return null
  }
}

export function BatchPassportScreen() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  /** The last re-score, held on screen so the movement stays visible. */
  const [delta, setDelta] = useState<{ before: BatchRisk; after: BatchRisk } | null>(null)
  const [refused, setRefused] = useState<string | null>(null)

  const profileQuery = useQuery({
    queryKey: ['passport', id],
    queryFn: () => getBatchProfile(id),
  })
  const timelineQuery = useQuery({
    queryKey: ['timeline', id],
    queryFn: () => getTimeline(id),
  })

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['passport', id] })
    void queryClient.invalidateQueries({ queryKey: ['timeline', id] })
  }

  const event = useMutation({
    mutationFn: (body: ReportEvent) => reportEvent(id, body),
    onSuccess: (outcome) => {
      setRefused(null)
      if (outcome.previous && outcome.current) {
        setDelta({ before: outcome.previous, after: outcome.current })
      }
      refresh()
    },
    // A 409 is the lifecycle refusing an illegal move — the system working,
    // not failing. Shown as a note rather than as a crash.
    onError: (e: Error) => setRefused(e.message),
  })

  const split = useMutation({
    mutationFn: (allocations: Parameters<typeof splitBatch>[1]) =>
      splitBatch(id, allocations),
    onSuccess: () => {
      setRefused(null)
      refresh()
    },
    onError: (e: Error) => setRefused(e.message),
  })

  const busy = event.isPending || split.isPending

  if (profileQuery.isLoading || timelineQuery.isLoading) {
    return (
      <LoadingState
        title="Loading batch passport"
        description="Fetching identity, custody chain and the full event history."
      />
    )
  }

  if (profileQuery.isError || !profileQuery.data || !timelineQuery.data) {
    return (
      <ErrorState
        title={`Batch ${id} could not be loaded`}
        description="The backend must be running and seeded — `python -m foodos.ingest.seed`. Unlike the four Contract 2b screens, the passport has no mock: invented history would be worse than none."
        action={
          <button type="button" className="button-primary" onClick={() => navigate('/command')}>
            Back to Command Center
          </button>
        }
      />
    )
  }

  const profile: BatchProfile = profileQuery.data
  const timeline: Timeline = timelineQuery.data
  const risk = profile.risk
  const stageIndex = LADDER.indexOf(profile.lifecycle as (typeof LADDER)[number])

  const fireEvent = (body: ReportEvent) => () => event.mutate(body)

  return (
    <div className="space-y-8">
      <SectionHeader
        eyebrow="Batch passport"
        title={profile.id}
        description="One physical batch, one digital identity. The code survives every change of hands, and every event on it re-runs the physics from the top rather than patching the last answer."
        action={
          <button
            type="button"
            className="button-ghost"
            onClick={() => navigate(`/batches/${profile.id}`)}
          >
            Intelligence view
          </button>
        }
      />

      {/* ------------------------------------------------ identity card */}
      <section className="card flex flex-wrap items-start justify-between gap-6 p-6">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            {risk && <RiskBadge level={risk.level as RiskLevel} long />}
            <span className="rounded-full border border-[#c4c7c8] bg-[#f1edec] px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-[#444748]">
              {title(profile.lifecycle)}
            </span>
            {profile.current_owner && (
              <span className="text-sm text-[#444748]">
                held by <strong className="text-[#1c1b1b]">{profile.current_owner}</strong>
              </span>
            )}
          </div>

          <p className="text-sm text-[#444748]">
            <strong className="text-[#1c1b1b]">
              {formatKgWhole(profile.qty_kg_remaining)}
            </strong>{' '}
            {profile.commodity}
            {profile.qty_kg_remaining !== profile.qty_kg && (
              <> of {formatKgWhole(profile.qty_kg)} registered</>
            )}{' '}
            · {profile.origin} → {profile.destination}
          </p>
          <p className="text-sm text-[#444748]">
            Harvested {formatTimestamp(profile.harvested_at)}
            {profile.transport && <> · {title(profile.transport)}</>}
            {profile.packaging && <> · {title(profile.packaging)}</>}
          </p>

          {profile.parent_id && (
            <p className="text-sm text-[#444748]">
              Split from{' '}
              <Link
                to={`/batches/${profile.parent_id}/passport`}
                className="font-semibold text-[#0f172a] underline"
              >
                {profile.parent_id}
              </Link>
            </p>
          )}
        </div>

        {/* One QR for the batch — not one per crate, and not one per tomato. */}
        <figure className="shrink-0 text-center">
          <img
            src={qrSrc(profile.id)}
            alt={`QR code linking to the passport for batch ${profile.id}`}
            className="h-36 w-36 rounded border border-[#c4c7c8] bg-white p-1"
          />
          <figcaption className="mt-2 text-[11px] text-[#5d5f5f]">
            Scan opens this page
          </figcaption>
        </figure>
      </section>

      {/* ------------------------------------------------ lifecycle rail */}
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider">
        {LADDER.map((stage, i) => (
          <span
            key={stage}
            className={`rounded px-2 py-1 ${
              i < stageIndex
                ? 'bg-[#f1edec] text-[#5d5f5f]'
                : i === stageIndex
                  ? 'border border-[#1c1b1b] bg-[#f8fafc] text-[#0f172a]'
                  : 'text-[#c4c7c8]'
            }`}
          >
            {title(stage)}
          </span>
        ))}
        {profile.is_terminal && (
          <span className="rounded bg-[#1c1b1b] px-2 py-1 text-[#f8fafc]">
            {title(profile.lifecycle)}
          </span>
        )}
      </div>

      {/* ------------------------------------------------ current state */}
      {risk && (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Remaining life"
            value={`${risk.rul_hours.toFixed(0)} h`}
            note={
              risk.rul_at_dispatch != null
                ? `${risk.rul_at_dispatch.toFixed(0)} h leaving the farm gate`
                : undefined
            }
            urgent={risk.rul_hours < 12}
          />
          <Stat
            label="Expected loss"
            value={`${risk.loss_pct.toFixed(1)}%`}
            note={
              risk.low != null && risk.high != null
                ? `${risk.low.toFixed(1)}–${risk.high.toFixed(1)}% band`
                : 'no band — deterministic fallback'
            }
          />
          <Stat label="Mass at risk" value={formatKgWhole(risk.loss_kg)} />
          <Stat
            label="Quality"
            value={profile.state.grade ?? '—'}
            note={
              profile.state.quality_score != null
                ? `score ${profile.state.quality_score.toFixed(0)} · ${risk.confidence} confidence`
                : undefined
            }
          />
        </section>
      )}

      {/* The movement. This is the demo moment, so it stays on screen. */}
      {delta && (
        <p className="card border-[#1c1b1b] p-4 text-sm text-[#1c1b1b]">
          <strong>{delta.before.rul_hours.toFixed(0)} h</strong> →{' '}
          <strong>{delta.after.rul_hours.toFixed(0)} h</strong> remaining life · loss{' '}
          <strong>{delta.before.loss_pct.toFixed(1)}%</strong> →{' '}
          <strong>{delta.after.loss_pct.toFixed(1)}%</strong>
          {delta.before.level !== delta.after.level && (
            <>
              {' '}
              · risk {delta.before.level} → {delta.after.level}
            </>
          )}
        </p>
      )}

      {refused && (
        <p className="card border-[#ef4444] p-4 text-sm text-[#1c1b1b]">{refused}</p>
      )}

      {/* ------------------------------------------------ demo controls */}
      <section className="space-y-3">
        <h2 className="text-lg font-extrabold tracking-tight text-slate-900">
          Report an event
        </h2>
        <p className="max-w-2xl text-sm text-[#444748]">
          Each one appends to the record and re-runs the physics from the registered
          condition plus everything since. Nothing is patched, and an illegal move is
          refused rather than absorbed.
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="button-ghost"
            disabled={busy}
            onClick={fireEvent({ type: 'dispatched' })}
          >
            Dispatch
          </button>
          <button
            type="button"
            className="button-ghost"
            disabled={busy}
            onClick={fireEvent({
              type: 'delay',
              payload: { duration_hours: 6, cause: 'checkpoint queue' },
            })}
          >
            +6 h delay
          </button>
          <button
            type="button"
            className="button-ghost"
            disabled={busy}
            onClick={fireEvent({
              type: 'temperature_exposure',
              payload: { temp_c: 41, hours: 3 },
            })}
          >
            41 °C for 3 h
          </button>
          <button
            type="button"
            className="button-ghost"
            disabled={busy}
            onClick={fireEvent({ type: 'arrived' })}
          >
            Arrived
          </button>
          <button
            type="button"
            className="button-ghost"
            disabled={busy}
            onClick={fireEvent({ type: 'received' })}
          >
            Received
          </button>
          <button
            type="button"
            className="button-primary"
            disabled={busy || profile.qty_kg_remaining <= 0}
            onClick={() => {
              // Thirds of what is actually left, remainder on the last child so
              // the allocations sum exactly — the API refuses a split that does
              // not balance rather than silently rescaling it.
              const total = profile.qty_kg_remaining
              const a = Math.round(total * 0.3)
              const b = Math.round(total * 0.4)
              split.mutate([
                { qty_kg: a, destination: 'Retailer A', owner_role: 'retailer' },
                { qty_kg: b, destination: 'Retailer B', owner_role: 'retailer' },
                { qty_kg: total - a - b, destination: 'Processor C', owner_role: 'processor' },
              ])
            }}
          >
            Split 30 / 40 / 30
          </button>
        </div>
      </section>

      {/* ------------------------------------------------ children */}
      {profile.children.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-extrabold tracking-tight text-slate-900">
            Child batches
          </h2>
          <p className="max-w-2xl text-sm text-[#444748]">
            Each inherits the parent's journey and timeline, then is scored against its
            own onward leg. A child is never fresher than the batch it was cut from.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {profile.children.map((child) => (
              <Link key={child.id} to={`/batches/${child.id}/passport`} className="card p-4">
                <p className="font-semibold text-[#1c1b1b]">{child.id}</p>
                <p className="mt-1 text-sm text-[#444748]">
                  {formatKgWhole(child.qty_kg)} → {child.destination}
                </p>
                {child.rul_hours != null && (
                  <p className="mt-2 text-xs text-[#5d5f5f]">
                    {child.rul_hours.toFixed(0)} h left · {child.level}
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ------------------------------------------------ custody */}
      <section className="space-y-3">
        <h2 className="text-lg font-extrabold tracking-tight text-slate-900">Custody</h2>
        <p className="max-w-2xl text-sm text-[#444748]">
          One identity, many holders. The transporter does not create a batch — this is
          the same {profile.id} the FPO registered at the farm gate.
        </p>
        <ol className="flex flex-wrap items-center gap-2 text-sm">
          {profile.custody.map((party, i) => (
            <li key={`${party.party}-${i}`} className="flex items-center gap-2">
              {i > 0 && <span aria-hidden className="text-[#c4c7c8]">→</span>}
              <span className="rounded border border-[#c4c7c8] bg-[#fcf8f8] px-3 py-2">
                <span className="font-semibold text-[#1c1b1b]">{party.party}</span>
                {party.role && (
                  <span className="ml-2 text-xs uppercase tracking-wider text-[#5d5f5f]">
                    {title(party.role)}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ol>
      </section>

      {/* ------------------------------------------------ timeline */}
      <section className="space-y-3">
        <h2 className="text-lg font-extrabold tracking-tight text-slate-900">Timeline</h2>
        <p className="max-w-2xl text-sm text-[#444748]">
          Append-only. A correction is a new entry, never an edit — which is what makes
          this a record rather than a rendering of the current row.
        </p>
        <ol className="mt-2">
          {timeline.events.map((e) => {
            const snapshot = timeline.snapshots.find(
              (s) => s.as_of === e.occurred_at && s.reason === e.type,
            )
            const detail = describe(e)
            return (
              <li key={e.id} className="flex gap-4 border-l border-[#c4c7c8] pb-5 pl-5 last:pb-0">
                <span
                  aria-hidden
                  className="-ml-[27px] mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-[#5d5f5f] ring-4 ring-[#fcf8f8]"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="text-xs tabular-nums text-[#5d5f5f]">
                      {formatTimestamp(e.occurred_at)}
                    </span>
                    <span className="text-sm font-semibold text-[#1c1b1b]">
                      {EVENT_LABEL[e.type] ?? title(e.type)}
                    </span>
                    {e.inherited && (
                      <span className="rounded bg-[#f1edec] px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-[#5d5f5f]">
                        inherited
                      </span>
                    )}
                    {e.location && <span className="text-xs text-[#5d5f5f]">{e.location}</span>}
                  </div>
                  {detail && <p className="mt-0.5 text-sm text-[#444748]">{detail}</p>}
                  {snapshot && (
                    <p className="mt-1 text-xs text-[#5d5f5f]">
                      re-scored → {snapshot.rul_hours?.toFixed(0)} h left,{' '}
                      {snapshot.loss_pct?.toFixed(1)}% loss, {snapshot.level}
                      {snapshot.model_run_id === null && ' · deterministic fallback'}
                    </p>
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      </section>
    </div>
  )
}

function Stat({
  label,
  value,
  note,
  urgent,
}: {
  label: string
  value: string
  note?: string
  urgent?: boolean
}) {
  return (
    <div className="card p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[#5d5f5f]">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-extrabold tabular-nums ${
          urgent ? 'text-[#ef4444]' : 'text-[#1c1b1b]'
        }`}
      >
        {value}
      </p>
      {note && <p className="mt-1 text-xs text-[#5d5f5f]">{note}</p>}
    </div>
  )
}
