/**
 * Mock payloads for Contract 2, shaped byte-for-byte like the endpoints B is building.
 *
 * These stand in for `contracts/mock/*.json`. When that folder lands they are replaced
 * wholesale — no screen imports this file directly, only `api/batchApi.ts` does, so the
 * swap is one file wide.
 *
 * The plan matrix and the simulator both come out of `batchEngine.score()`. Nothing
 * here is a hand-typed rupee figure.
 */

import type {
  BatchListResponse,
  BatchListRow,
  BatchProfile,
  CandidatePlan,
  HealthResponse,
  MarketsResponse,
  PlansResponse,
  QuestionnaireResponse,
  SimulateRequest,
} from '../api/batchContract'
import type { RiskLevel } from '../lib/risk'
import { BASELINE_QTY_KG, MANDIS, W_PRESERVE, rank, toPlan, type CandidateSpec } from './batchEngine'

export const DEMO_BATCH_ID = 'T1024'

/* ---------------------------------------------------------------- *
 * Candidate action space for T1024
 * ---------------------------------------------------------------- */

const D = (qty: number) => ({ mandi: 'delhi_apmc', qty_kg: qty })
const J = (qty: number) => ({ mandi: 'jaipur_apmc', qty_kg: qty })
const K = (qty: number) => ({ mandi: 'kolar_local', qty_kg: qty })

const CANDIDATES: CandidateSpec[] = [
  {
    id: 0,
    label: 'Do nothing — 10 T Delhi APMC, open truck, scheduled departure',
    request: { departure_shift_hours: 0, transport: 'open_truck', destinations: [D(10_000)] },
    is_baseline: true,
    horizon: 'PREVENT',
    note: 'The lane as booked. Every other row is measured against this one.',
  },
  {
    id: 1,
    label: 'Depart 6 h earlier — 10 T Delhi APMC',
    request: { departure_shift_hours: -6, transport: 'open_truck', destinations: [D(10_000)] },
    horizon: 'PREVENT',
    note: 'Moves the load out of the 12:00–16:00 thermal peak. No extra spend.',
  },
  {
    id: 2,
    label: 'Upgrade to tarpaulin — 10 T Delhi APMC, scheduled departure',
    request: { departure_shift_hours: 0, transport: 'tarpaulin', destinations: [D(10_000)] },
    horizon: 'PREVENT',
    note: 'Cuts solar load, but the extra ₹1.42/km eats the saving on a 2,150 km lane.',
  },
  {
    id: 3,
    label: 'Reroute whole batch to Jaipur APMC',
    request: { departure_shift_hours: 0, transport: 'open_truck', destinations: [J(10_000)] },
    horizon: 'PRESERVE',
    note: '6.5 h shorter transit at ₹15.90/kg, but 10 T lands on a 180 T/day mandi.',
  },
  {
    id: 4,
    label: 'Split 6 T Delhi / 4 T Jaipur + depart 6 h earlier',
    request: { departure_shift_hours: -6, transport: 'open_truck', destinations: [D(6_000), J(4_000)] },
    horizon: 'PRESERVE',
    note: 'Thermal relief and arrival-price diversification in one action.',
  },
  {
    id: 5,
    label: 'Reefer upgrade + depart 6 h earlier — 10 T Delhi APMC',
    request: { departure_shift_hours: -6, transport: 'reefer', destinations: [D(10_000)] },
    feasible: false,
    exclusion_reason:
      'No reefer capacity inside the 6 h dispatch window — nearest available unit is 19 h out.',
    horizon: 'PRESERVE',
    note: 'Scored and kept on screen: it is the best physical outcome and the worst economic one.',
  },
  {
    id: 6,
    label: 'Divert 10 T to Kolar agro-processing (puree line)',
    request: { departure_shift_hours: 0, transport: 'open_truck', destinations: [K(10_000)] },
    diversion_cost_per_kg: 0.4,
    feasible: false,
    exclusion_reason:
      'Rescue tier gated: 31 h RUL keeps fresh-market channels open. RECOVER unlocks below 12 h.',
    horizon: 'RECOVER',
    note: 'The rescue waterfall will not open a salvage channel while a fresh one still clears.',
  },
]

const T1024_PLANS: CandidatePlan[] = rank(CANDIDATES, BASELINE_QTY_KG)
const T1024_BASELINE = T1024_PLANS.find((p) => p.is_baseline) as CandidatePlan
const T1024_BEST = T1024_PLANS.find((p) => p.is_best) as CandidatePlan

/* ---------------------------------------------------------------- *
 * 5 · GET /api/batches/{id}
 * ---------------------------------------------------------------- */

export const T1024_PROFILE: BatchProfile = {
  id: DEMO_BATCH_ID,
  commodity: 'tomato',
  qty_kg: BASELINE_QTY_KG,
  origin: 'Kolar Collection Hub',
  destination: 'Delhi APMC',
  harvested_at: '2026-08-10T06:00:00',
  transport: 'open_truck',
  packaging: 'ventilated_plastic_crate',
  state: {
    quality_score: 72,
    grade: 'B+',
    maturity: 'high',
    damage_factor: 'moderate',
    field_heat_hours_over_30c: 4.2,
  },
  risk: {
    loss_pct: T1024_BASELINE.loss_pct,
    loss_kg: T1024_BASELINE.loss_kg,
    low: 6.7,
    high: 10.9,
    rul_hours: 31,
    level: 'HIGH',
    confidence: 'HIGH',
  },
  drivers: [
    {
      name: 'field_heat_hours',
      contribution: 0.31,
      text: '4.2 h above 30 °C between cutting and loading. Field heat sets the respiration rate the whole journey runs at.',
    },
    {
      name: 'transit_temperature',
      contribution: 0.26,
      text: 'Route snapshot peaks at 38 °C in the Nagpur–Jhansi stretch, inside the scheduled departure window.',
    },
    {
      name: 'open_transport',
      contribution: 0.18,
      text: 'Open truck adds direct solar load; no thermal retention from the vehicle body.',
    },
    {
      name: 'road_vibration',
      contribution: 0.14,
      text: 'Mixed road quality over 2,150 km causes surface micro-punctures that open decay sites.',
    },
    {
      name: 'maturity_stage',
      contribution: 0.11,
      text: 'Turning-to-light-red maturity leaves less transit headroom than a mature-green cut would.',
    },
  ],
  best_plan_id: T1024_BEST.id,
  recommendation: {
    id: `plan-${T1024_BEST.id}`,
    horizon: 'PRESERVE',
    title: T1024_BEST.label,
    subtitle: `Cuts expected loss from ${T1024_BASELINE.loss_pct}% to ${T1024_BEST.loss_pct}% and keeps ${
      T1024_BASELINE.loss_kg - T1024_BEST.loss_kg
    } kg of tomatoes in the food system.`,
    beforeQty: BASELINE_QTY_KG,
    afterQty: Math.round(BASELINE_QTY_KG - T1024_BEST.loss_kg),
    why: `Departing 6 h earlier clears the midday thermal peak, and moving 4 T to Jaipur trades ₹0.10/kg of price for 6.5 h of transit. Net realisation rises to ₹${T1024_BEST.net_value.toLocaleString('en-IN')}.`,
    saves: {
      kg: T1024_BASELINE.loss_kg - T1024_BEST.loss_kg,
      inr: T1024_BEST.delta_vs_baseline,
      co2e: Math.round((T1024_BASELINE.loss_kg - T1024_BEST.loss_kg) * 1.7),
    },
    confidence: 0.94,
    expiresIn: '42 min',
    batchId: DEMO_BATCH_ID,
    commodity: 'Tomato',
    origin: 'Kolar Collection Hub',
    destination: 'Delhi & Jaipur APMC',
    rulHours: 31,
    lossRiskPercent: T1024_BEST.loss_pct,
  },
  model_run_id: 'loss-lgbm-2026081006-a41',
  source: 'snapshot',
}

/* ---------------------------------------------------------------- *
 * 4 · GET /api/batches — 3 High Risk · 7 Stable · 2 Need Attention
 * ---------------------------------------------------------------- */

function row(
  id: string,
  qty: number,
  origin: string,
  destination: string,
  rul: number,
  loss: number,
  level: RiskLevel,
  status: BatchListRow['status'],
  bestAction: string,
  planId: number,
  delta: number,
): BatchListRow {
  return {
    id,
    commodity: 'tomato',
    qty_kg: qty,
    origin,
    destination,
    rul_hours: rul,
    loss_pct: loss,
    loss_kg: Math.round((qty * loss) / 100),
    level,
    status,
    best_action: bestAction,
    best_plan_id: planId,
    delta_vs_baseline: delta,
  }
}

const BATCH_ROWS: BatchListRow[] = [
  // 3 High Risk
  row(DEMO_BATCH_ID, 10_000, 'Kolar Collection Hub', 'Delhi APMC', 31, T1024_BASELINE.loss_pct, 'HIGH', 'assessed', T1024_BEST.label, T1024_BEST.id, T1024_BEST.delta_vs_baseline),
  row('T1031', 7_500, 'Chintamani FPO', 'Delhi APMC', 22, 11.2, 'HIGH', 'assessed', 'Depart 8 h earlier + tarpaulin cover', 2, 9_140),
  row('T1019', 4_200, 'Srinivaspur Yard', 'Jaipur APMC', 18, 9.8, 'HIGH', 'in_transit', 'Reroute 4.2 T to Bengaluru APMC — 5.5 h transit', 3, 4_620),
  // 2 Need Attention
  row('T1027', 6_000, 'Malur Collection Point', 'Delhi APMC', 44, 6.4, 'MEDIUM', 'assessed', 'Split 3 T Delhi / 3 T Jaipur', 4, 3_180),
  row('T1022', 9_000, 'Kolar Collection Hub', 'Jaipur APMC', 51, 5.9, 'MEDIUM', 'registered', 'Depart 4 h earlier — no extra spend', 1, 2_410),
  // 7 Stable
  row('T1035', 5_500, 'Bangarpet FPO', 'Bengaluru APMC', 66, 2.1, 'LOW', 'assessed', 'Hold current plan', 0, 0),
  row('T1036', 3_800, 'Mulbagal Yard', 'Bengaluru APMC', 71, 1.8, 'LOW', 'in_transit', 'Hold current plan', 0, 0),
  row('T1030', 12_000, 'Kolar Collection Hub', 'Bengaluru APMC', 62, 2.4, 'LOW', 'assessed', 'Hold current plan', 0, 0),
  row('T1028', 4_400, 'Srinivaspur Yard', 'Kolar Local Mandi', 69, 1.2, 'LOW', 'delivered', 'Cleared at ₹9.50/kg', 0, 0),
  row('T1025', 8_200, 'Chintamani FPO', 'Bengaluru APMC', 58, 3.0, 'LOW', 'in_transit', 'Hold current plan', 0, 0),
  row('T1021', 2_600, 'Malur Collection Point', 'Kolar Local Mandi', 73, 1.1, 'LOW', 'delivered', 'Cleared at ₹9.50/kg', 0, 0),
  row('T1018', 6_800, 'Bangarpet FPO', 'Jaipur APMC', 55, 3.4, 'LOW', 'in_transit', 'Hold current plan', 0, 0),
]

export const BATCH_LIST: BatchListResponse = {
  batches: BATCH_ROWS,
  counts: {
    HIGH: BATCH_ROWS.filter((b) => b.level === 'HIGH').length,
    MEDIUM: BATCH_ROWS.filter((b) => b.level === 'MEDIUM').length,
    LOW: BATCH_ROWS.filter((b) => b.level === 'LOW').length,
  },
  source: 'snapshot',
  as_of: '2026-08-10T09:40:00',
}

/* ---------------------------------------------------------------- *
 * 6 · GET /api/batches/{id}/plans
 * ---------------------------------------------------------------- */

export const T1024_PLANS_RESPONSE: PlansResponse = {
  batch_id: DEMO_BATCH_ID,
  baseline_plan_id: T1024_BASELINE.id,
  best_plan_id: T1024_BEST.id,
  plans: T1024_PLANS,
  w_preserve: W_PRESERVE,
  model_run_id: 'loss-lgbm-2026081006-a41',
}

/* ---------------------------------------------------------------- *
 * 7 · POST /api/batches/{id}/simulate — same score(), different inputs
 * ---------------------------------------------------------------- */

export function simulateMock(request: SimulateRequest, qtyKg = BASELINE_QTY_KG): CandidatePlan {
  const legs = request.destinations.filter((d) => d.qty_kg > 0)
  const label = legs
    .map((d) => `${(d.qty_kg / 1000).toFixed(1)} T ${MANDIS[d.mandi]?.name ?? d.mandi}`)
    .join(' / ')
  const shift = request.departure_shift_hours
  const shiftLabel =
    shift === 0 ? 'scheduled departure' : shift < 0 ? `depart ${Math.abs(shift)} h earlier` : `depart ${shift} h later`

  const plan = toPlan(
    {
      id: 999,
      label: `${label || 'no allocation'} · ${shiftLabel}`,
      request,
      feasible: legs.length > 0,
      exclusion_reason: legs.length === 0 ? 'Allocate at least one destination before simulating.' : null,
    },
    qtyKg,
    T1024_BASELINE.net_value,
  )

  return plan
}

/* ---------------------------------------------------------------- *
 * 1 · GET /api/questionnaire?commodity=tomato
 *
 * D owns `content/questionnaire/tomato.yaml`. This is that tree serialised. The
 * wizard renders whatever arrives here — no question is written in TSX.
 * ---------------------------------------------------------------- */

export const TOMATO_QUESTIONNAIRE: QuestionnaireResponse = {
  commodity: 'tomato',
  version: 'tomato@0.3.0',
  target_seconds: 30,
  source: 'snapshot',
  steps: [
    {
      id: 'commodity',
      title: 'What are you registering?',
      subtitle: 'One commodity per batch. Tomato is the calibrated pilot lane.',
      questions: [
        {
          id: 'q_commodity',
          prompt: 'Commodity',
          kind: 'single',
          feature_key: 'commodity',
          required: true,
          default: 'tomato',
          options: [{ value: 'tomato', label: 'Tomato', hint: 'Hybrid red · calibrated against NABCONS baselines' }],
        },
      ],
    },
    {
      id: 'consignment',
      title: 'How much, and where is it going?',
      subtitle: 'Volume and lane set the physics. Everything after this refines it.',
      questions: [
        {
          id: 'q_qty',
          prompt: 'Quantity',
          kind: 'number',
          feature_key: 'qty_kg',
          unit: 'kg',
          min: 100,
          max: 40_000,
          step: 100,
          default: 10_000,
          required: true,
        },
        {
          id: 'q_origin',
          prompt: 'Collection point',
          kind: 'single',
          feature_key: 'origin',
          required: true,
          default: 'Kolar Collection Hub',
          options: [
            { value: 'Kolar Collection Hub', label: 'Kolar Collection Hub' },
            { value: 'Chintamani FPO', label: 'Chintamani FPO' },
            { value: 'Srinivaspur Yard', label: 'Srinivaspur Yard' },
            { value: 'Malur Collection Point', label: 'Malur Collection Point' },
            { value: 'Bangarpet FPO', label: 'Bangarpet FPO' },
          ],
        },
        {
          id: 'q_destination',
          prompt: 'Intended destination',
          kind: 'single',
          feature_key: 'destination',
          help: 'A starting assumption. The optimiser is free to move it.',
          required: true,
          default: 'delhi_apmc',
          options: [
            { value: 'delhi_apmc', label: 'Delhi APMC · Azadpur', hint: '2,150 km · ~36.5 h' },
            { value: 'jaipur_apmc', label: 'Jaipur APMC · Muhana', hint: '1,980 km · ~30 h' },
            { value: 'bengaluru_apmc', label: 'Bengaluru APMC · Binny Mill', hint: '280 km · ~5.5 h' },
            { value: 'kolar_local', label: 'Kolar Local Mandi', hint: '25 km · ~1.5 h' },
          ],
        },
      ],
    },
    {
      id: 'condition',
      title: 'Condition at the collection point',
      subtitle: 'Five questions. This is the layer the loss model leans on hardest.',
      questions: [
        {
          id: 'q_harvest_window',
          prompt: 'When was it cut?',
          kind: 'single',
          feature_key: 'harvest_window',
          required: true,
          options: [
            { value: 'dawn', label: 'Before 8 am', hint: 'Lowest field heat' },
            { value: 'morning', label: '8 am – 11 am' },
            { value: 'midday', label: '11 am – 3 pm', hint: 'Peak field heat' },
            { value: 'evening', label: 'After 3 pm' },
          ],
        },
        {
          id: 'q_sun_exposure',
          prompt: 'How long did it sit uncovered in the sun after cutting?',
          kind: 'number',
          feature_key: 'sun_exposure_hours',
          unit: 'hours',
          min: 0,
          max: 12,
          step: 0.5,
          default: 4,
          // Branch: a midday cut opens the sun-exposure follow-up.
          show_if: { question: 'q_harvest_window', in: ['midday', 'evening'] },
        },
        {
          id: 'q_hours_since_harvest',
          prompt: 'Hours since cutting',
          kind: 'number',
          feature_key: 'hours_since_harvest',
          unit: 'hours',
          min: 0,
          max: 72,
          step: 1,
          default: 6,
          required: true,
        },
        {
          id: 'q_maturity',
          prompt: 'Maturity at cut',
          kind: 'single',
          feature_key: 'maturity_stage',
          required: true,
          options: [
            { value: 'mature_green', label: 'Mature green', hint: 'Most transit headroom' },
            { value: 'breaker', label: 'Breaker' },
            { value: 'turning', label: 'Turning / light red' },
            { value: 'red_ripe', label: 'Red ripe', hint: 'Least transit headroom' },
          ],
        },
        {
          id: 'q_damage',
          prompt: 'Visible damage across the lot',
          kind: 'single',
          feature_key: 'damage_factor',
          required: true,
          options: [
            { value: 'clean', label: 'Clean', hint: 'Under 1% affected' },
            { value: 'light', label: 'Light', hint: '1–3% surface abrasion' },
            { value: 'moderate', label: 'Moderate', hint: '3–7%, some splitting' },
            { value: 'heavy', label: 'Heavy', hint: 'Over 7%' },
          ],
        },
      ],
    },
    {
      id: 'photos',
      title: 'Three to five photos',
      subtitle: 'Shot across the lot, not the best crate. Skippable — the batch still scores.',
      questions: [
        {
          id: 'q_photos',
          prompt: 'Lot photos',
          kind: 'photos',
          feature_key: 'photo_bundle',
          min: 3,
          max: 5,
          help: 'Vision reads maturity, damage share and uniformity as probabilistic features — never as a verdict.',
        },
      ],
    },
    {
      id: 'logistics',
      title: 'How is it moving?',
      subtitle: 'The last layer. These two answers are also the first two levers the optimiser pulls.',
      questions: [
        {
          id: 'q_transport',
          prompt: 'Transport booked',
          kind: 'single',
          feature_key: 'transport',
          required: true,
          default: 'open_truck',
          options: [
            { value: 'open_truck', label: 'Open truck', hint: '₹14.88/km' },
            { value: 'tarpaulin', label: 'Tarpaulin covered', hint: '₹16.30/km' },
            { value: 'reefer', label: 'Reefer', hint: '₹24.50/km · limited availability' },
          ],
        },
        {
          id: 'q_packaging',
          prompt: 'Packaging',
          kind: 'single',
          feature_key: 'packaging',
          required: true,
          default: 'ventilated_plastic_crate',
          // Branch: a reefer closes the packaging thermal questions.
          show_if: { question: 'q_transport', not_in: ['reefer'] },
          options: [
            { value: 'ventilated_plastic_crate', label: 'Ventilated plastic crate' },
            { value: 'wooden_crate', label: 'Wooden crate' },
            { value: 'corrugated_box', label: 'Corrugated box' },
            { value: 'gunny_bag', label: 'Gunny bag', hint: 'Highest crush loss' },
          ],
        },
        {
          id: 'q_depart_at',
          prompt: 'Scheduled departure',
          kind: 'time',
          feature_key: 'depart_at',
          default: '10:00',
          required: true,
        },
      ],
    },
  ],
}

/* ---------------------------------------------------------------- *
 * 10 · GET /api/markets      11 · GET /api/health
 * ---------------------------------------------------------------- */

export const MARKETS: MarketsResponse = {
  commodity: 'tomato',
  near: 'Kolar Collection Hub',
  as_of: '2026-08-10T06:15:00',
  source: 'snapshot',
  markets: Object.values(MANDIS).map((m) => ({
    mandi: m.key,
    name: m.name,
    distance_km: m.distance_km,
    transit_hours: m.transit_hours,
    price_per_kg: m.price_per_kg,
    daily_absorption_kg: m.daily_absorption_kg,
    trend: m.trend,
  })),
}

export const HEALTH: HealthResponse = {
  status: 'ok',
  version: 'mock',
  model_run_id: 'loss-lgbm-2026081006-a41',
  source: 'snapshot',
}
