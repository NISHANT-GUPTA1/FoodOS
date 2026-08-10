/**
 * The receiving gate — where a tracked batch becomes stock in a track.
 *
 * Additive to `batchApi.ts` (Contract 2b's four screens) and to
 * `passportApi.ts` (identity inside the agri node). This client owns the one
 * step neither covers: taking the crate into a kitchen, store or plant while
 * the code survives the crossing.
 *
 * No mock path, for the same reason `passportApi.ts` has none. The claim these
 * endpoints make is that the provenance is real; a mocked chain of custody
 * would be worse than an empty one, because it would demo perfectly and mean
 * nothing.
 */

import { fetchJson, postJson } from './http'
import type { PartyRole } from './passportApi'

export type TrackName = 'kitchen' | 'retail' | 'production'

/**
 * What a lot arrived carrying. Every field is a fact about the produce at the
 * moment of receipt, not a prediction about its future in the receiving site.
 */
export interface InheritedState {
  code: string
  commodity: string
  origin: string
  destination: string
  harvested_at: string
  received_at: string
  /** Registered at the farm gate, versus what the receiver actually accepted. */
  qty_registered_kg: number
  qty_received_kg: number
  upstream_loss_pct: number
  /** Life left **now**, after the elapsed journey. Not life at dispatch. */
  rul_hours: number
  /** What it had leaving the farm gate, so a screen can show "46 h -> 18 h". */
  rul_at_dispatch: number | null
  age_hours: number
  /** 0-1. Share of total usable life already spent before it got here. */
  life_used: number
  quality_score: number | null
  grade: string | null
  level: 'LOW' | 'MEDIUM' | 'HIGH' | null
  confidence: 'LOW' | 'MEDIUM' | 'HIGH' | null
  /** How many times it changed hands before this gate. */
  hops: number
  custody: string[]
  /** "model" | "fallback" — render it. An inherited number from a degraded
   *  score must not arrive looking like a modelled one. */
  basis: string
  model_run_id: string | null
}

export interface Lot {
  lot_id: number
  /** The consignment's own code. No new identifier is minted at the gate. */
  lot_code: string
  batch_code: string | null
  site_id: number
  site: string
  track: TrackName | string
  product_id: number
  product: string
  qty_kg: number
  uom: string
  /** Written from the inherited RUL, never from a shelf-life table. */
  rsl_days: number | null
  life_used: number | null
  intake_grade: number
  printed_expiry: string | null
  rsl_explanation: string | null
  inherited: InheritedState | null
}

export interface Receipt {
  batch_id: string
  /** Contract 2b's four-value spelling. */
  status: string
  lifecycle: string
  accepted_kg: number
  /** Rejected at the gate. Booked as waste against the batch, never dropped. */
  rejected_kg: number
  custody: string[]
  lot: Lot
}

export interface LotsResponse {
  batch_id: string
  /** A split legitimately lands one code in more than one track. */
  tracks: string[]
  total_received_kg: number
  lots: Lot[]
}

export interface ReceiveRequest {
  to_party: string
  to_role?: PartyRole
  site_id?: number
  site_type?: 'kitchen' | 'store' | 'warehouse' | 'plant'
  storage_zone_id?: number
  product_sku?: string
  /** Less than what was shipped is a partial acceptance. */
  qty_kg?: number
  occurred_at?: string
  note?: string
}

export const getLots = (id: string) =>
  fetchJson<LotsResponse>(`/api/batches/${id}/lots`)

export const receiveBatch = (id: string, body: ReceiveRequest) =>
  postJson<Receipt>(`/api/batches/${id}/receive`, body)

/** The track a site belongs to, for a label. Mirrors `intake.SITE_TYPE_TRACK`. */
export const TRACK_LABEL: Record<string, string> = {
  kitchen: 'Kitchen node',
  retail: 'Retail node',
  production: 'Production node',
}
