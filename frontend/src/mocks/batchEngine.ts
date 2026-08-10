/**
 * The mock objective function.
 *
 * ONE `score()`. `/api/batches/{id}/plans` and `/api/batches/{id}/simulate` both call
 * it, exactly as Contract 2 requires of the backend — "the simulator and the optimiser
 * must call the same score(), or the simulator will disagree with the recommendation
 * on stage." If the frontend mock had two, the demo would disagree with itself before
 * B ever shipped.
 *
 * Every constant below is a PLACEHOLDER standing in for D's `content/*.yaml` and A's
 * loss model, and is calibrated to the two numbers the H30 gate locks:
 *
 *   baseline (10,000 kg -> Delhi, open truck, no departure shift) = 8.4 % loss
 *   best plan (6 T Delhi / 4 T Jaipur, depart 6 h earlier)        = 3.9 % loss
 *
 * When B's endpoints land, this file stops being read. Nothing imports it except
 * `mocks/batch.ts`.
 */

import type { CandidatePlan, SimulateRequest, TransportMode } from '../api/batchContract'

/* ---------------------------------------------------------------- *
 * Constants — placeholders for D's content/*.yaml
 * ---------------------------------------------------------------- */

export interface MandiSpec {
  key: string
  name: string
  distance_km: number
  transit_hours: number
  price_per_kg: number
  daily_absorption_kg: number
  trend: 'up' | 'down' | 'flat'
}

/** Stand-in for `content/mandis.yaml` + `external/agmarknet.py` prices (per kg, never per quintal). */
export const MANDIS: Record<string, MandiSpec> = {
  delhi_apmc: {
    key: 'delhi_apmc',
    name: 'Delhi APMC · Azadpur',
    distance_km: 2150,
    transit_hours: 36.5,
    price_per_kg: 16.0,
    daily_absorption_kg: 420_000,
    trend: 'flat',
  },
  jaipur_apmc: {
    key: 'jaipur_apmc',
    name: 'Jaipur APMC · Muhana',
    distance_km: 1980,
    transit_hours: 30.0,
    price_per_kg: 15.9,
    daily_absorption_kg: 180_000,
    trend: 'up',
  },
  bengaluru_apmc: {
    key: 'bengaluru_apmc',
    name: 'Bengaluru APMC · Binny Mill',
    distance_km: 280,
    transit_hours: 5.5,
    // Short transit, but the nearest market is the one every Kolar FPO already ships
    // to — the price reflects that saturation, not the quality.
    price_per_kg: 11.2,
    daily_absorption_kg: 260_000,
    trend: 'down',
  },
  kolar_local: {
    key: 'kolar_local',
    name: 'Kolar Local Mandi',
    distance_km: 25,
    transit_hours: 1.5,
    price_per_kg: 9.5,
    daily_absorption_kg: 40_000,
    trend: 'flat',
  },
}

export const MANDI_KEYS = Object.keys(MANDIS)

/** Stand-in for `content/transport_modes.yaml`. */
export const TRANSPORT: Record<TransportMode, { label: string; cooling_factor: number; cost_per_km: number; available: boolean; unavailable_reason?: string }> = {
  open_truck: { label: 'Open truck', cooling_factor: 1.0, cost_per_km: 14.88, available: true },
  tarpaulin: { label: 'Tarpaulin covered', cooling_factor: 0.88, cost_per_km: 16.3, available: true },
  reefer: {
    label: 'Reefer (refrigerated)',
    cooling_factor: 0.55,
    cost_per_km: 24.5,
    available: false,
    unavailable_reason:
      'No reefer capacity inside the 6 h dispatch window — nearest available unit is 19 h out (transport_modes.availability_hours).',
  },
}

/** Baseline loss for the reference lane (Kolar -> Delhi, open truck, no shift). */
const BASELINE_LOSS_PCT = 8.4
const REFERENCE_TRANSIT_HOURS = 36.5

/** How loss scales with transit hours. Sub-linear: the first hours cost the most. */
const TRANSIT_EXPONENT = 0.85

/**
 * Departure shift, saturating. Most of the benefit of leaving early is in the first
 * six hours because that is what moves the load out of the midday thermal peak;
 * twelve hours earlier is not twice as good.
 */
const SHIFT_SATURATION_HOURS = 6
const SHIFT_AMPLITUDE = 0.622

/** Splitting across mandis cuts dock dwell and panic discounting at a single arrival. */
const SPLIT_FACTOR = 0.94
const SPLIT_COORDINATION_COST = 500

/** Baseline RUL at the H30 calibration, in hours. */
export const BASELINE_RUL_HOURS = 31

/** λ — the mass-preservation weight, ₹ per kg of food lost. Ranks plans; not in net_value. */
export const W_PRESERVE = 8

export const BASELINE_QTY_KG = 10_000

function departureFactor(shiftHours: number): number {
  return 1 + SHIFT_AMPLITUDE * Math.tanh(shiftHours / SHIFT_SATURATION_HOURS)
}

function transitFactor(transitHours: number): number {
  return Math.pow(transitHours / REFERENCE_TRANSIT_HOURS, TRANSIT_EXPONENT)
}

function round(value: number, dp = 0): number {
  const f = Math.pow(10, dp)
  return Math.round(value * f) / f
}

export interface ScoreInput extends SimulateRequest {
  qty_kg: number
  /** Rescue diversion, ₹/kg handling cost. Zero for every fresh-market plan. */
  diversion_cost_per_kg?: number
}

export interface ScoreResult {
  loss_pct: number
  loss_kg: number
  surviving_kg: number
  gross_revenue: number
  logistics_cost: number
  loss_cost: number
  diversion_cost: number
  mass_penalty: number
  net_value: number
  ranking_value: number
  expected_price_per_kg: number
  rul_hours: number
  /** Per-destination breakdown, so a split is explainable leg by leg. */
  legs: Array<{ mandi: string; name: string; qty_kg: number; loss_pct: number; surviving_kg: number; price_per_kg: number; revenue: number }>
}

/**
 * V(a) = Σ_legs [ surviving_kg · price ] − C_logistics − C_diversion
 * ranked by V(a) − λ · L_mass.
 */
export function score(input: ScoreInput): ScoreResult {
  const destinations = input.destinations.filter((d) => d.qty_kg > 0)
  const totalQty = destinations.reduce((sum, d) => sum + d.qty_kg, 0) || input.qty_kg

  const shift = departureFactor(input.departure_shift_hours)
  const cooling = TRANSPORT[input.transport]?.cooling_factor ?? 1
  const split = destinations.length > 1 ? SPLIT_FACTOR : 1
  const diversionPerKg = input.diversion_cost_per_kg ?? 0

  let surviving = 0
  let gross = 0
  let logistics = destinations.length > 1 ? SPLIT_COORDINATION_COST * (destinations.length - 1) : 0

  const legs: ScoreResult['legs'] = destinations.map((leg) => {
    const mandi = MANDIS[leg.mandi] ?? MANDIS.delhi_apmc
    const lossPct = Math.min(
      26,
      Math.max(0.4, BASELINE_LOSS_PCT * transitFactor(mandi.transit_hours) * shift * cooling * split),
    )
    const survivingKg = leg.qty_kg * (1 - lossPct / 100)
    const revenue = survivingKg * mandi.price_per_kg

    surviving += survivingKg
    gross += revenue
    logistics += mandi.distance_km * (TRANSPORT[input.transport]?.cost_per_km ?? 14.88) * (leg.qty_kg / BASELINE_QTY_KG)

    return {
      mandi: mandi.key,
      name: mandi.name,
      qty_kg: leg.qty_kg,
      loss_pct: round(lossPct, 2),
      surviving_kg: round(survivingKg, 1),
      price_per_kg: mandi.price_per_kg,
      revenue: round(revenue),
    }
  })

  const lossKg = totalQty - surviving
  const lossPct = (lossKg / totalQty) * 100
  const expectedPrice = surviving > 0 ? gross / surviving : 0
  const lossCost = lossKg * expectedPrice
  const diversionCost = diversionPerKg * totalQty
  const massPenalty = W_PRESERVE * lossKg
  const netValue = gross - logistics - diversionCost

  // RUL responds to the same thermal factors that drive loss, but damped: remaining
  // life is mostly a property of the batch's field history, and only partly of how
  // it is moved. Departing six hours earlier buys hours, not days.
  const RUL_ELASTICITY = 0.35
  const thermalRelief = 1 / (shift * cooling)
  const rul = Math.min(72, Math.max(16, BASELINE_RUL_HOURS * (1 + RUL_ELASTICITY * (thermalRelief - 1))))

  return {
    loss_pct: round(lossPct, 1),
    loss_kg: Math.round(lossKg),
    surviving_kg: round(surviving, 1),
    gross_revenue: Math.round(gross),
    logistics_cost: Math.round(logistics),
    loss_cost: Math.round(lossCost),
    diversion_cost: Math.round(diversionCost),
    mass_penalty: Math.round(massPenalty),
    net_value: Math.round(netValue),
    ranking_value: Math.round(netValue - massPenalty),
    expected_price_per_kg: round(expectedPrice, 2),
    rul_hours: round(rul, 1),
    legs,
  }
}

export interface CandidateSpec {
  id: number
  label: string
  request: SimulateRequest
  is_baseline?: boolean
  feasible?: boolean
  exclusion_reason?: string | null
  diversion_cost_per_kg?: number
  horizon?: CandidatePlan['horizon']
  note?: string
}

/** Turn a scored candidate into the frozen `plans[]` row shape. */
export function toPlan(spec: CandidateSpec, qtyKg: number, baselineNetValue: number | null): CandidatePlan {
  const result = score({ ...spec.request, qty_kg: qtyKg, diversion_cost_per_kg: spec.diversion_cost_per_kg })

  return {
    id: spec.id,
    label: spec.label,
    loss_pct: result.loss_pct,
    loss_kg: result.loss_kg,
    logistics_cost: result.logistics_cost,
    gross_revenue: result.gross_revenue,
    net_value: result.net_value,
    delta_vs_baseline: baselineNetValue === null ? 0 : result.net_value - baselineNetValue,
    is_baseline: spec.is_baseline ?? false,
    is_best: false,
    feasible: spec.feasible ?? true,
    exclusion_reason: spec.exclusion_reason ?? null,
    rul_hours: result.rul_hours,
    horizon: spec.horizon,
    note: spec.note,
    terms: {
      expected_price_per_kg: result.expected_price_per_kg,
      surviving_kg: result.surviving_kg,
      gross_revenue: result.gross_revenue,
      logistics_cost: result.logistics_cost,
      loss_cost: result.loss_cost,
      diversion_cost: result.diversion_cost,
      mass_penalty: result.mass_penalty,
      w_preserve: W_PRESERVE,
      ranking_value: result.ranking_value,
    },
  }
}

/**
 * Rank a candidate set. Infeasible plans are scored and RETURNED — never hidden —
 * but they cannot win.
 */
export function rank(specs: CandidateSpec[], qtyKg: number): CandidatePlan[] {
  const baselineSpec = specs.find((s) => s.is_baseline)
  const baselineNet = baselineSpec ? toPlan(baselineSpec, qtyKg, null).net_value : null

  const plans = specs.map((spec) => toPlan(spec, qtyKg, baselineNet))

  let best: CandidatePlan | undefined
  for (const plan of plans) {
    if (!plan.feasible) continue
    if (!best || plan.terms.ranking_value > best.terms.ranking_value) best = plan
  }
  if (best) best.is_best = true

  return plans
}
