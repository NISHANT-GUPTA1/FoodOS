/**
 * Contract 2 · B -> C — the agri batch surface.
 *
 * Transcribed from `FoodOS-Team-Split-v2.md` §2, Contract 2. Additive to the frozen
 * eleven kitchen endpoints, which keep working byte for byte.
 *
 * Field names are snake_case because they come off the wire from FastAPI unchanged.
 * Do not camelCase them here — that would put a translation layer between the contract
 * and the screen, and the contract is the thing that is frozen.
 */

import type { ConfidenceLevel, RiskLevel } from '../lib/risk'
import type { RecommendationData } from '../mocks/dashboard'

export type TransportMode = 'open_truck' | 'tarpaulin' | 'reefer'
export type PackagingType =
  | 'ventilated_plastic_crate'
  | 'gunny_bag'
  | 'wooden_crate'
  | 'corrugated_box'
export type SourceStamp = 'snapshot' | 'live'

/* ------------------------------------------------------------------ *
 * 4 · GET /api/batches?status=&risk=   — Screen 1, Command Center
 * ------------------------------------------------------------------ */

export interface BatchListRow {
  id: string
  commodity: string
  qty_kg: number
  origin: string
  destination: string
  rul_hours: number
  loss_pct: number
  loss_kg: number
  level: RiskLevel
  status: BatchStatus
  /** One line. The action, not a summary of the batch. */
  best_action: string
  best_plan_id: number
  delta_vs_baseline: number
}

export type BatchStatus = 'registered' | 'assessed' | 'in_transit' | 'delivered'

export interface BatchListResponse {
  batches: BatchListRow[]
  counts: Record<RiskLevel, number>
  source: SourceStamp
  as_of: string
}

/* ------------------------------------------------------------------ *
 * 5 · GET /api/batches/{id}   — Screen 3 hero. Shape frozen in §2.
 * ------------------------------------------------------------------ */

export interface BatchState {
  quality_score: number
  grade: string
  maturity: string
  damage_factor: string
  field_heat_hours_over_30c: number
}

export interface BatchRisk {
  loss_pct: number
  loss_kg: number
  low: number
  high: number
  rul_hours: number
  level: RiskLevel
  confidence: ConfidenceLevel
}

export interface LossDriver {
  name: string
  /** 0-1, sums to 1 across the array. */
  contribution: number
  text: string
}

export interface BatchProfile {
  id: string
  commodity: string
  qty_kg: number
  origin: string
  destination: string
  harvested_at: string
  transport: TransportMode
  packaging: PackagingType
  state: BatchState
  risk: BatchRisk
  drivers: LossDriver[]
  best_plan_id: number
  /** The frozen recommendation card shape, unchanged. */
  recommendation: RecommendationData
  model_run_id?: string
  source?: SourceStamp
}

/* ------------------------------------------------------------------ *
 * 6 · GET /api/batches/{id}/plans   — the Action Evaluation Matrix
 * ------------------------------------------------------------------ */

/** Every term of V(a), so no number on screen is unattributable. */
export interface PlanTerms {
  expected_price_per_kg: number
  surviving_kg: number
  gross_revenue: number
  logistics_cost: number
  loss_cost: number
  diversion_cost: number
  mass_penalty: number
  w_preserve: number
  ranking_value: number
}

export interface CandidatePlan {
  id: number
  label: string
  loss_pct: number
  loss_kg: number
  logistics_cost: number
  gross_revenue: number
  net_value: number
  delta_vs_baseline: number
  is_baseline: boolean
  is_best: boolean
  feasible: boolean
  exclusion_reason: string | null
  terms: PlanTerms
  /** Present on simulate responses; absent on stored candidates. */
  rul_hours?: number
  horizon?: 'PREVENT' | 'PRESERVE' | 'RECOVER'
  note?: string
}

export interface PlansResponse {
  batch_id: string
  baseline_plan_id: number
  best_plan_id: number
  plans: CandidatePlan[]
  w_preserve: number
  model_run_id?: string
}

/* ------------------------------------------------------------------ *
 * 7 · POST /api/batches/{id}/simulate   — Screen 4, What-If
 * ------------------------------------------------------------------ */

export interface SplitAllocation {
  mandi: string
  qty_kg: number
}

export interface SimulateRequest {
  departure_shift_hours: number
  transport: TransportMode
  destinations: SplitAllocation[]
}

/** Returns the same plan object — same `score()`, or the stage disagrees with itself. */
export type SimulateResponse = CandidatePlan

/* ------------------------------------------------------------------ *
 * 1 · GET /api/questionnaire?commodity=tomato   — Screen 2
 *
 * The adaptive tree is DATA from D. Never hardcode a question in TSX or adding a
 * second commodity becomes a frontend release.
 * ------------------------------------------------------------------ */

export type QuestionKind = 'single' | 'number' | 'photos' | 'time' | 'text'

export interface QuestionOption {
  value: string
  label: string
  hint?: string
}

/** Branch condition: show this question only when `question` answered inside `in`. */
export interface ShowIf {
  question: string
  in?: string[]
  not_in?: string[]
}

export interface Question {
  id: string
  prompt: string
  help?: string
  kind: QuestionKind
  /** The key this answer writes into A's `fuse()`. */
  feature_key: string
  options?: QuestionOption[]
  unit?: string
  min?: number
  max?: number
  step?: number
  placeholder?: string
  default?: string | number
  required?: boolean
  show_if?: ShowIf
}

export interface QuestionnaireStep {
  id: string
  title: string
  subtitle: string
  questions: Question[]
}

export interface QuestionnaireResponse {
  commodity: string
  version: string
  /** Seconds the tree is expected to take. Screen 2 budget is 30. */
  target_seconds: number
  steps: QuestionnaireStep[]
  source: SourceStamp
}

/* ------------------------------------------------------------------ *
 * 2 · POST /api/batches      3 · POST /api/batches/{id}/photos
 * ------------------------------------------------------------------ */

export interface CreateBatchRequest {
  commodity: string
  qty_kg: number
  origin: string
  destination: string
  transport: TransportMode
  packaging: PackagingType
  depart_at?: string
  /** Every answered `feature_key` -> value. */
  answers: Record<string, string | number>
}

export interface CreateBatchResponse {
  id: string
  status: BatchStatus
  photos_expected: number
}

export interface PhotoUploadResponse {
  batch_id: string
  accepted: number
  /** A batch with zero photos still scores — CV degrades, it does not gate. */
  vision_confidence: ConfidenceLevel
}

/* ------------------------------------------------------------------ *
 * 8/9 · accept / override
 * ------------------------------------------------------------------ */

export interface PlanOutcomeResponse {
  plan_id: number
  outcome: 'accepted' | 'overridden'
  recorded_at: string
  reason?: string
}

/* ------------------------------------------------------------------ *
 * 10 · GET /api/markets?commodity=&near=
 * ------------------------------------------------------------------ */

export interface MarketRow {
  mandi: string
  name: string
  distance_km: number
  transit_hours: number
  price_per_kg: number
  daily_absorption_kg: number
  trend: 'up' | 'down' | 'flat'
}

export interface MarketsResponse {
  commodity: string
  near: string
  as_of: string
  /** Never hidden. The UI shows a quiet staleness note when this is "snapshot". */
  source: SourceStamp
  markets: MarketRow[]
}

/* ------------------------------------------------------------------ *
 * 11 · GET /api/health
 * ------------------------------------------------------------------ */

export interface HealthResponse {
  status: 'ok' | 'degraded'
  version: string
  model_run_id: string | null
  source: SourceStamp
}

/* ------------------------------------------------------------------ */

export const batchPaths = {
  questionnaire: '/api/questionnaire',
  batches: '/api/batches',
  batch: (id: string) => `/api/batches/${id}`,
  photos: (id: string) => `/api/batches/${id}/photos`,
  plans: (id: string) => `/api/batches/${id}/plans`,
  simulate: (id: string) => `/api/batches/${id}/simulate`,
  accept: (planId: number) => `/api/plans/${planId}/accept`,
  override: (planId: number) => `/api/plans/${planId}/override`,
  markets: '/api/markets',
  health: '/api/health',
} as const
