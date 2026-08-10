/**
 * The batch identity surface — timeline, custody, events, splitting, FEFO.
 *
 * Additive to `batchApi.ts`, which owns Contract 2b's four screens. These
 * endpoints are live on the backend from the start, so unlike the Contract 2b
 * client there is no mock path here: a passport with invented history would be
 * worse than no passport, because the whole claim is that the history is real.
 */

import { fetchJson, postJson } from './http'

export type Lifecycle =
  | 'created'
  | 'assessed'
  | 'ready_for_dispatch'
  | 'in_transit'
  | 'arrived'
  | 'received'
  | 'in_inventory'
  | 'sold'
  | 'processed'
  | 'donated'
  | 'diverted'
  | 'wasted'

export type PartyRole =
  | 'farmer'
  | 'fpo'
  | 'transporter'
  | 'wholesaler'
  | 'retailer'
  | 'processor'
  | 'donation_partner'

export interface BatchRisk {
  loss_pct: number
  loss_kg: number
  low: number | null
  high: number | null
  rul_hours: number
  level: 'LOW' | 'MEDIUM' | 'HIGH'
  confidence: 'LOW' | 'MEDIUM' | 'HIGH'
  rul_at_dispatch: number | null
}

export interface BatchStateBlock {
  quality_score: number | null
  grade: string | null
  maturity: string | null
  damage_factor: string | null
  field_heat_hours_over_30c: number | null
}

export interface Party {
  party: string
  role: PartyRole | null
  since: string
  location: string | null
  qty_kg: number | null
}

export interface BatchEvent {
  id: number
  type: string
  /** When it happened in the world. */
  occurred_at: string
  /** When FoodOS was told. Later than `occurred_at` whenever a delay is
   *  reported from inside the delay. */
  recorded_at: string
  location: string | null
  actor: string | null
  actor_role: PartyRole | null
  qty_kg: number | null
  payload: Record<string, unknown>
  from_status: Lifecycle | null
  to_status: Lifecycle | null
  /** Copied from the parent at a split — history this holder inherited. */
  inherited: boolean
}

export interface BatchSnapshot {
  sequence: number
  as_of: string
  reason: string
  status: Lifecycle
  location: string | null
  qty_kg: number
  quality_score: number | null
  loss_pct: number | null
  loss_kg: number | null
  low: number | null
  high: number | null
  rul_hours: number | null
  level: 'LOW' | 'MEDIUM' | 'HIGH' | null
  confidence: 'LOW' | 'MEDIUM' | 'HIGH' | null
  /** Null means the deterministic fallback scored this row, not A's model. */
  model_run_id: string | null
  inputs: Record<string, unknown>
}

export interface BatchChild {
  id: string
  qty_kg: number
  destination: string
  status: string
  lifecycle: Lifecycle
  rul_hours: number | null
  level: string | null
}

export interface BatchProfile {
  id: string
  commodity: string
  qty_kg: number
  qty_kg_remaining: number
  origin: string
  destination: string
  harvested_at: string
  transport: string | null
  packaging: string | null
  state: BatchStateBlock
  risk: BatchRisk | null
  drivers: Array<Record<string, unknown>>
  best_plan_id: number | null
  status: string
  lifecycle: Lifecycle
  is_terminal: boolean
  current_owner: string | null
  current_owner_role: PartyRole | null
  current_location: string | null
  parent_id: string | null
  children: BatchChild[]
  custody: Party[]
  passport_url: string
  qr_url: string
}

export interface Timeline {
  batch_id: string
  events: BatchEvent[]
  snapshots: BatchSnapshot[]
  custody: Party[]
}

export interface EventOutcome {
  batch_id: string
  event: BatchEvent
  previous: BatchRisk | null
  current: BatchRisk | null
  lifecycle: Lifecycle
  status: string
  rescored: boolean
  snapshot: BatchSnapshot | null
}

export interface Passport {
  id: string
  commodity: string
  qty_kg: number
  origin: string
  destination: string
  harvested_at: string
  status: string
  lifecycle: Lifecycle
  state: BatchStateBlock
  risk: BatchRisk | null
  recommended_action: string
  handle_within_hours: number | null
  custody: Party[]
  events: BatchEvent[]
  qr_url: string
}

export interface FefoRow {
  rank: number
  id: string
  commodity: string
  qty_kg: number
  rul_hours: number | null
  expires_at: string | null
  level: string | null
  beats_fifo: boolean
}

export const getBatchProfile = (id: string) =>
  fetchJson<BatchProfile>(`/api/batches/${id}`)

export const getTimeline = (id: string) =>
  fetchJson<Timeline>(`/api/batches/${id}/timeline`)

export const getPassport = (id: string) =>
  fetchJson<Passport>(`/api/batches/${id}/passport`)

export const getFefo = (owner?: string) =>
  fetchJson<{ as_of: string; rows: FefoRow[]; disagreements: number }>(
    `/api/inventory/fefo${owner ? `?owner=${encodeURIComponent(owner)}` : ''}`,
  )

export interface ReportEvent {
  type: string
  occurred_at?: string
  location?: string
  actor?: string
  actor_role?: PartyRole
  qty_kg?: number
  payload?: Record<string, unknown>
}

export const reportEvent = (id: string, body: ReportEvent) =>
  postJson<EventOutcome>(`/api/batches/${id}/events`, body)

export const handOver = (
  id: string,
  body: { to_party: string; to_role: PartyRole; qty_kg?: number; location?: string },
) => postJson<unknown>(`/api/batches/${id}/handoff`, body)

export const splitBatch = (
  id: string,
  allocations: Array<{ qty_kg: number; destination: string; owner_role?: PartyRole }>,
) => postJson<{ parent_id: string; children: BatchProfile[] }>(
  `/api/batches/${id}/split`,
  { allocations },
)

/** The QR is served as SVG straight from the API — no client-side encoding. */
export const qrSrc = (id: string, scale = 6) =>
  `${import.meta.env.VITE_FOODS_API_BASE_URL ?? ''}/api/batches/${id}/qr.svg?scale=${scale}`
