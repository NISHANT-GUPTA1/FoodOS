import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Boxes, PackageCheck, Warehouse } from 'lucide-react'
import {
  getLots,
  receiveBatch,
  TRACK_LABEL,
  type InheritedState,
  type Lot,
} from '../../api/intakeApi'
import { EmptyState } from '../StatePanel'
import { formatHours, formatKgWhole } from '../../utils/format'
import { riskToken } from '../../lib/risk'

/**
 * Where this batch went once somebody took it into stock.
 *
 * The half of the story the agri screens could not tell. Screens 1-4 follow a
 * consignment to a destination and stop; this picks it up at the receiving gate
 * and shows the lot it became in a kitchen, store or plant — under the same
 * code, carrying the life it had left when it arrived.
 *
 * The block that matters is `inherited`. A lot that shows "46 h at dispatch,
 * 18 h on arrival" is the entire argument for the product in one line: the
 * receiving site is not starting a fresh clock, and every number it computes
 * downstream begins from what actually happened on the road.
 */
export function DownstreamLots({ code }: { code: string }) {
  const client = useQueryClient()
  const lots = useQuery({ queryKey: ['lots', code], queryFn: () => getLots(code) })

  // A batch still on the road has no lots, and the identity endpoints are
  // live-only — so a failure here means the backend is not running, which must
  // not take the rest of Screen 3 down with it.
  if (lots.isError) return null

  const rows = lots.data?.lots ?? []

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-extrabold tracking-tight text-slate-900">
          <Boxes className="h-5 w-5 text-slate-400" />
          Where this batch went
        </h2>
        {rows.length > 0 ? (
          <span className="text-[11px] font-semibold text-slate-500">
            {formatKgWhole(lots.data?.total_received_kg ?? 0)} received across{' '}
            {lots.data?.tracks.length ?? 0} node
            {(lots.data?.tracks.length ?? 0) === 1 ? '' : 's'}
          </span>
        ) : null}
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Not yet received into a node"
          description="This batch is still under the agri node. When a kitchen, store or plant takes it into stock, the lot appears here under this same code — carrying the life it has left rather than starting a fresh clock."
          action={<ReceiveAction code={code} onDone={() => client.invalidateQueries({ queryKey: ['lots', code] })} />}
        />
      ) : (
        <ul className="space-y-3">
          {rows.map((lot) => (
            <LotRow key={lot.lot_id} lot={lot} />
          ))}
        </ul>
      )}
    </section>
  )
}

function LotRow({ lot }: { lot: Lot }) {
  const inherited = lot.inherited
  const token = riskToken(inherited?.level ?? undefined)

  return (
    <li className="rounded-2xl border-2 border-slate-200 bg-white/85 p-4 shadow-sm backdrop-blur-xl">
      <div className="flex flex-wrap items-center gap-2">
        <Warehouse className="h-4 w-4 text-slate-400" />
        <span className="text-sm font-extrabold text-slate-900">{lot.site}</span>
        <span className="rounded-full border border-slate-300 bg-slate-50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">
          {TRACK_LABEL[lot.track] ?? lot.track}
        </span>
        {/* The point of the whole layer: the lot trades under the batch code. */}
        <span className="font-mono text-xs font-bold text-slate-700">{lot.lot_code}</span>
        <span className="ml-auto text-sm font-semibold text-slate-700">
          {formatKgWhole(lot.qty_kg)} {lot.product}
        </span>
      </div>

      {inherited ? <InheritedStrip inherited={inherited} rslDays={lot.rsl_days} /> : null}

      {lot.rsl_explanation ? (
        <p className="mt-3 border-t border-slate-100 pt-3 text-xs font-medium leading-5 text-slate-600">
          {lot.rsl_explanation}
        </p>
      ) : null}

      {inherited && inherited.basis !== 'model' ? (
        <p className={`mt-2 text-[11px] font-bold ${token.text}`}>
          Inherited from a fallback score — the figure stands, but no model run backs it.
        </p>
      ) : null}
    </li>
  )
}

/**
 * The carried state, as four numbers.
 *
 * `at dispatch -> on arrival` is deliberately rendered as a pair rather than a
 * single "remaining" figure. One number reads as a property of the produce;
 * the pair reads as something the journey did to it, which is the thing the
 * receiving site is being asked to act on.
 */
function InheritedStrip({
  inherited,
  rslDays,
}: {
  inherited: InheritedState
  rslDays: number | null
}) {
  return (
    <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Cell label="Life on arrival">
        <span className="flex items-baseline gap-1.5">
          {inherited.rul_at_dispatch ? (
            <>
              <span className="text-xs font-semibold text-slate-400 line-through">
                {formatHours(inherited.rul_at_dispatch)}
              </span>
              <ArrowRight className="h-3 w-3 text-slate-400" />
            </>
          ) : null}
          <span className="font-mono text-lg font-extrabold tabular-nums text-slate-900">
            {formatHours(inherited.rul_hours)}
          </span>
        </span>
        {rslDays !== null ? (
          <span className="block text-[11px] font-semibold text-slate-500">
            {rslDays.toFixed(1)} d on the shelf
          </span>
        ) : null}
      </Cell>

      <Cell label="Life already spent">
        <span className="font-mono text-lg font-extrabold tabular-nums text-slate-900">
          {Math.round(inherited.life_used * 100)}%
        </span>
        <span className="block text-[11px] font-semibold text-slate-500">
          {formatHours(inherited.age_hours)} old
        </span>
      </Cell>

      <Cell label="Accepted">
        <span className="font-mono text-lg font-extrabold tabular-nums text-slate-900">
          {formatKgWhole(inherited.qty_received_kg)}
        </span>
        <span className="block text-[11px] font-semibold text-slate-500">
          of {formatKgWhole(inherited.qty_registered_kg)} registered
        </span>
      </Cell>

      <Cell label="Custody">
        <span className="text-sm font-bold text-slate-900">
          {inherited.hops} handover{inherited.hops === 1 ? '' : 's'}
        </span>
        <span className="block truncate text-[11px] font-semibold text-slate-500">
          {inherited.custody.join(' → ')}
        </span>
      </Cell>
    </dl>
  )
}

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</dt>
      <dd className="mt-1">{children}</dd>
    </div>
  )
}

/**
 * Record the receipt. The one write on this screen that crosses nodes.
 *
 * Deliberately minimal: who is accepting it and which kind of site. Quantity
 * defaults to everything still under the identity, because a partial
 * acceptance is the exception and making it the default would invite a
 * mis-keyed number into the one ledger that has to balance.
 */
function ReceiveAction({ code, onDone }: { code: string; onDone: () => void }) {
  const [party, setParty] = useState('Azadpur Wholesale')
  const [siteType, setSiteType] = useState<'kitchen' | 'store' | 'plant'>('store')

  const receive = useMutation({
    mutationFn: () =>
      receiveBatch(code, { to_party: party, to_role: 'retailer', site_type: siteType }),
    onSuccess: onDone,
  })

  if (receive.isSuccess) {
    return (
      <p className="flex items-center gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800">
        <PackageCheck className="h-4 w-4" />
        Received into stock as {code}. Same code, new node.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={party}
          onChange={(event) => setParty(event.target.value)}
          placeholder="Who is accepting it?"
          className="w-full rounded-xl border-2 border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
        />
        <select
          value={siteType}
          onChange={(event) => setSiteType(event.target.value as typeof siteType)}
          className="rounded-xl border-2 border-slate-200 bg-white px-3 py-2 text-sm font-semibold outline-none transition focus:border-slate-400"
        >
          <option value="store">Store · retail node</option>
          <option value="kitchen">Kitchen · kitchen node</option>
          <option value="plant">Plant · production node</option>
        </select>
        <button
          type="button"
          disabled={party.trim().length < 2 || receive.isPending}
          onClick={() => receive.mutate()}
          className="shrink-0 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white transition hover:bg-slate-800 active:scale-95 disabled:opacity-40"
        >
          Receive into stock
        </button>
      </div>

      {receive.isError ? (
        <p className="text-xs font-semibold text-rose-700">
          That was refused. A batch can only be received once, and only after it has been
          dispatched and arrived.
        </p>
      ) : null}
    </div>
  )
}

/** A compact chip for list rows — "already in a node, under this code". */
export function TrackChip({ code }: { code: string }) {
  const lots = useQuery({ queryKey: ['lots', code], queryFn: () => getLots(code) })
  const tracks = lots.data?.tracks ?? []
  if (tracks.length === 0) return null

  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-800">
      <PackageCheck className="h-3 w-3" />
      In {tracks.map((t) => TRACK_LABEL[t] ?? t).join(' + ')}
    </span>
  )
}

/** Provenance for a lot that arrived on a tracked consignment. */
export function ProvenanceChip({
  batchCode,
  origin,
}: {
  batchCode: string | null
  origin?: string | null
}) {
  if (!batchCode) return null

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-[10px] font-bold text-slate-700"
      title={origin ? `Grown or aggregated at ${origin}` : undefined}
    >
      <span className="font-mono">{batchCode}</span>
      {origin ? <span className="font-sans font-semibold text-slate-500">· {origin}</span> : null}
    </span>
  )
}
