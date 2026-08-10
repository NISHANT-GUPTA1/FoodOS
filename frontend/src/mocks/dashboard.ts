import type { Horizon } from '../types'

export type KpiTone = 'prevent' | 'preserve' | 'recover'

export interface KpiCardData {
  label: string
  value: string
  delta: string
  tone: KpiTone
  note: string
}

export interface RecommendationData {
  id: string
  horizon: Horizon
  title: string
  subtitle: string
  beforeQty: number
  afterQty: number
  why: string
  saves: {
    kg: number
    inr: number
    co2e: number
  }
  confidence: number
  expiresIn: string
  batchId?: string
  commodity?: string
  origin?: string
  destination?: string
  rulHours?: number
  lossRiskPercent?: number
}

export interface AttributionRow {
  label: string
  value: number
  detail: string
}

export interface ActionPlanCandidate {
  id: string
  name: string
  lossPercent: number
  massLostKg: number
  logisticsCostInr: number
  grossRevenueInr: number
  netRealizationInr: number
  isRecommended: boolean
  description: string
}

export interface PlanRow {
  dish: string
  oldQty: number
  profitQty: number
  planetQty: number
  unitSaving: number
}

export interface LedgerRow {
  batch: string
  sku: string
  qtyKg: number
  rslDays: number
  riskPercent: number
  valueAtRisk: number
  action: string
  tone: KpiTone
}

export interface RescueRow {
  channel: string
  recovery: string
  amount: string
  reason: string
  eligible: boolean
}

export interface ImpactRow {
  day: string
  actual: number
  forecast: number
  baseline: number
  heldOut: boolean
}

export interface TodayDashboardData {
  hero: string
  kpis: KpiCardData[]
  recommendations: RecommendationData[]
  actionMatrix: ActionPlanCandidate[]
  batchProfile: {
    id: string
    commodity: string
    quantityKg: number
    origin: string
    destination: string
    qualityScore: number
    maturity: string
    mechanicalDamage: string
    fieldHeatHours: number
    expectedLossPercent: number
    expectedLossKg: number
    rulHours: number
    riskLevel: 'HIGH' | 'MODERATE' | 'LOW'
  }
}

export interface WhyDashboardData {
  attribution: AttributionRow[]
  contributors: Array<{ label: string; value: number; note: string }>
  callout: string
  nabconsBaseline: {
    annualLossInr: string
    fruitsVegLossRange: string
    tomatoLossPercent: string
    guavaLossPercent: string
  }
}

export interface PlanDashboardData {
  lambda: number
  rows: Array<PlanRow & { recommendedQty: number; delta: number; saving: number }>
  totals: {
    oldQty: number
    recommendedQty: number
    saving: number
  }
}

export interface LedgerDashboardData {
  batches: LedgerRow[]
}

export interface RescueDashboardData {
  rows: RescueRow[]
}

export interface ImpactDashboardData {
  rows: ImpactRow[]
  accuracy: {
    mape: string
    rmse: string
    acceptance: string
  }
}

export const navItems: Array<{ to: string; label: string; description: string; tone: Horizon }> = [
  { to: '/today', label: 'Today', description: 'Command Center & Batch Profile', tone: 'PREVENT' },
  { to: '/why', label: 'Why', description: 'Arrhenius Decay & NABCONS Attribution', tone: 'PRESERVE' },
  { to: '/plan', label: 'Plan', description: 'What-If Scenario Simulator', tone: 'PREVENT' },
  { to: '/ledger', label: 'Ledger', description: 'Batch RUL & Risk Tracking', tone: 'PRESERVE' },
  { to: '/rescue', label: 'Rescue', description: 'Cascading Rescue & B2B Secondary', tone: 'RECOVER' },
  { to: '/impact', label: 'Impact', description: 'Backtest & Accuracy Models', tone: 'RECOVER' },
  { to: '/settings', label: 'Settings', description: 'Tokens & Demo Knobs', tone: 'PREVENT' },
]

export const actionMatrixData: ActionPlanCandidate[] = [
  {
    id: 'plan-0',
    name: 'Plan 0: Current Baseline (Delhi Open Truck)',
    lossPercent: 8.4,
    massLostKg: 840,
    logisticsCostInr: 32000,
    grossRevenueInr: 146560,
    netRealizationInr: 114560,
    isRecommended: false,
    description: 'Baseline open truck transport without departure shift. High thermal risk.',
  },
  {
    id: 'plan-1',
    name: 'Plan 1: Earlier Departure (-6 Hours)',
    lossPercent: 6.1,
    massLostKg: 610,
    logisticsCostInr: 32000,
    grossRevenueInr: 150240,
    netRealizationInr: 118240,
    isRecommended: false,
    description: 'Bypasses midday peak heat transit by departing at 04:00 AM.',
  },
  {
    id: 'plan-2',
    name: 'Plan 2: Covered Truck Upgrade',
    lossPercent: 5.8,
    massLostKg: 580,
    logisticsCostInr: 36000,
    grossRevenueInr: 150720,
    netRealizationInr: 114720,
    isRecommended: false,
    description: 'Tarpaulin insulated vehicle upgrade reduces solar irradiance exposure.',
  },
  {
    id: 'plan-3',
    name: 'Plan 3: Reroute Entire Batch to Jaipur',
    lossPercent: 4.2,
    massLostKg: 420,
    logisticsCostInr: 24000,
    grossRevenueInr: 143700,
    netRealizationInr: 119700,
    isRecommended: false,
    description: 'Shorter 7-hour transit route to Jaipur APMC mandi.',
  },
  {
    id: 'plan-4',
    name: 'Plan 4: Split Batch (6T Delhi / 4T Jaipur) + Early Departure',
    lossPercent: 3.9,
    massLostKg: 390,
    logisticsCostInr: 31500,
    grossRevenueInr: 153760,
    netRealizationInr: 122260,
    isRecommended: true,
    description: 'BEST ACTION: Maximizes net price realization while reducing total physical loss by 450 kg.',
  },
]

export const todayDashboard: TodayDashboardData = {
  hero: 'Batch #T1024 • 10,000 kg Tomatoes | Kolar Collection Hub → Delhi & Jaipur APMC Mandis',
  kpis: [
    { label: 'kg at risk', value: '840 kg', delta: '8.4% baseline loss', tone: 'recover', note: 'Batch #T1024 high thermal exposure at 34°C.' },
    { label: '₹ at risk', value: '₹1,53,760', delta: 'Potential loss of ₹32,000', tone: 'preserve', note: 'Value preserved under Plan 4 multi-mandi split.' },
    { label: '% preventable', value: '53.5%', delta: 'Loss drops to 3.9% under Plan 4', tone: 'prevent', note: 'Preventable physical loss with 6h early departure.' },
  ],
  batchProfile: {
    id: 'Batch #T1024',
    commodity: 'Tomato (Hybrid Red)',
    quantityKg: 10000,
    origin: 'Kolar Collection Hub',
    destination: 'Delhi APMC Mandi',
    qualityScore: 72,
    maturity: 'High (Turning Pink / Light Red)',
    mechanicalDamage: 'Moderate (Surface Abrasion ≤ 3%)',
    fieldHeatHours: 4.2,
    expectedLossPercent: 8.4,
    expectedLossKg: 840,
    rulHours: 31,
    riskLevel: 'HIGH',
  },
  actionMatrix: actionMatrixData,
  recommendations: [
    {
      id: 'rec-1',
      horizon: 'PREVENT',
      title: 'Split Batch (6T Delhi / 4T Jaipur) + Early Departure (-6h)',
      subtitle: 'Multi-Agent Optimizer Plan 4: Reduces expected loss from 8.4% to 3.9% and saves 450 kg of edible tomatoes.',
      beforeQty: 10000,
      afterQty: 9610,
      why: 'Multi-agent optimization maximizes net price realization (₹1,22,260) by balancing RUL (31h) against transit thermal heat.',
      saves: { kg: 450, inr: 7700, co2e: 765 },
      confidence: 0.94,
      expiresIn: '42 min',
      batchId: 'Batch #T1024',
      commodity: 'Tomato',
      origin: 'Kolar Hub',
      destination: 'Delhi & Jaipur APMC',
      rulHours: 31,
      lossRiskPercent: 3.9,
    },
    {
      id: 'rec-2',
      horizon: 'PRESERVE',
      title: 'Tarpaulin Thermal Insulation & Route Bypass',
      subtitle: 'Move 4,000 kg Grade B+ tomatoes to Jaipur APMC before dock heat consumes another day of RUL.',
      beforeQty: 4000,
      afterQty: 3832,
      why: 'Jaipur mandi velocity yields ₹14.8/kg with 4.4 days remaining life vs 3.1 days in open transit.',
      saves: { kg: 168, inr: 2480, co2e: 285 },
      confidence: 0.91,
      expiresIn: '28 min',
      batchId: 'Batch #T1024-B',
      commodity: 'Tomato',
      origin: 'Kolar Hub',
      destination: 'Jaipur APMC',
      rulHours: 44,
      lossRiskPercent: 4.2,
    },
    {
      id: 'rec-3',
      horizon: 'RECOVER',
      title: 'Route 390 kg Grade C Surplus to Secondary Food Processor',
      subtitle: 'B2B Salvage Auction for puree & paste lines at ₹8.5/kg before RUL safety gate closes.',
      beforeQty: 390,
      afterQty: 390,
      why: 'RSL is below 12 hours, but high Brix count makes batch optimal for industrial puree lines.',
      saves: { kg: 390, inr: 3315, co2e: 520 },
      confidence: 0.88,
      expiresIn: '15 min',
      batchId: 'Batch #T1024-C',
      commodity: 'Tomato Puree Grade',
      origin: 'Kolar Hub',
      destination: 'Kolar Agro Processing Unit',
      rulHours: 12,
      lossRiskPercent: 0.0,
    },
  ],
}

export const whyDashboard: WhyDashboardData = {
  nabconsBaseline: {
    annualLossInr: '₹1.53 Lakh Crore ($18.4 Billion USD)',
    fruitsVegLossRange: '4.58% – 15.05%',
    tomatoLossPercent: '11.62%',
    guavaLossPercent: '15.05%',
  },
  attribution: [
    { label: 'Accumulated Field Heat', value: 38, detail: '4.2 hours exposure at >30°C post-harvest accelerates ethylene respiration rates by 3.2x.' },
    { label: 'Open Transit Exposure', value: 29, detail: '14-hour open truck transit in ambient 34–38°C heat depletes batch RUL by 19 hours.' },
    { label: 'Mechanical Abrasion', value: 18, detail: 'Rough unpaved rural road vibration causes surface micro-punctures (3% severity).' },
    { label: 'Sub-Optimal Mandi Choice', value: 15, detail: 'Over-concentrating 100% volume in Delhi APMC risks dock dwell time and panic discounting.' },
  ],
  contributors: [
    { label: 'Field Heat Excursion', value: 38, note: 'Primary driver of rapid softening in turning tomatoes.' },
    { label: 'Transit Thermal Risk', value: 29, note: 'Mitigated by Plan 4 earlier 04:00 AM departure.' },
    { label: 'Road Vibration Damage', value: 18, note: 'Reduced by using ventilated plastic crates instead of gunny bags.' },
  ],
  callout: 'Arrhenius kinetic model: k = A · exp(-Ea / RT). Biophysical loss predictions combine field telemetry, computer vision maturity scoring, and e-NAM mandi prices.',
}

export const planRows: PlanRow[] = [
  { dish: 'Tomato (Batch #T1024)', oldQty: 10000, profitQty: 9610, planetQty: 9390, unitSaving: 15 },
  { dish: 'Guava (Batch #G4412)', oldQty: 5000, profitQty: 4720, planetQty: 4500, unitSaving: 22 },
  { dish: 'Potato (Batch #P8801)', oldQty: 15000, profitQty: 14550, planetQty: 14200, unitSaving: 8 },
  { dish: 'Cauliflower (Batch #C3091)', oldQty: 3500, profitQty: 3290, planetQty: 3100, unitSaving: 18 },
]

export const ledgerBatches: LedgerRow[] = [
  { batch: 'T1024', sku: 'Tomato (Hybrid Red)', qtyKg: 10000, rslDays: 1.3, riskPercent: 84, valueAtRisk: 146560, action: 'Split 6T Delhi / 4T Jaipur (Plan 4)', tone: 'prevent' },
  { batch: 'G4412', sku: 'Guava (Pink Flesh)', qtyKg: 5000, rslDays: 2.1, riskPercent: 42, valueAtRisk: 75000, action: 'Ship to Cold Storage Hub B', tone: 'preserve' },
  { batch: 'P8801', sku: 'Potato (Jyoti)', qtyKg: 15000, rslDays: 8.5, riskPercent: 12, valueAtRisk: 180000, action: 'Standard Mandi Clearance', tone: 'prevent' },
  { batch: 'PN2288', sku: 'Paneer (Fresh)', qtyKg: 600, rslDays: 0.5, riskPercent: 68, valueAtRisk: 165000, action: 'Cascading B2B Kitchen Auction', tone: 'recover' },
  { batch: 'CB8031', sku: 'Cauliflower', qtyKg: 3500, rslDays: 1.8, riskPercent: 48, valueAtRisk: 42000, action: 'Mark down & local processing', tone: 'preserve' },
]

export const rescueRows: RescueRow[] = [
  { channel: 'Jaipur Secondary Mandi', recovery: '₹59,200', amount: '4,000 kg', reason: 'Highest fresh sale price realization for Grade B+ tomatoes.', eligible: true },
  { channel: 'Kolar Agro Processing Unit', recovery: '₹3,315', amount: '390 kg', reason: 'High Brix count batch ideal for tomato puree & paste lines.', eligible: true },
  { channel: 'B2B Cloud Kitchen Network', recovery: '₹14,200', amount: '1,200 kg', reason: '24-hour culinary usability verified for curry bases.', eligible: true },
  { channel: 'NGO Food Rescue Network', recovery: '₹0 cash', amount: '300 kg', reason: 'Tax benefit & zero waste exit for near-expiry surplus.', eligible: true },
  { channel: 'Animal Feed / Compost', recovery: '₹350', amount: 'Last resort', reason: 'Excluded while higher salvage value channels remain open.', eligible: false },
]

export const impactRows: ImpactRow[] = [
  { day: 'Day 1', actual: 8.4, forecast: 8.2, baseline: 11.6, heldOut: false },
  { day: 'Day 2', actual: 7.9, forecast: 7.8, baseline: 11.6, heldOut: false },
  { day: 'Day 3', actual: 6.5, forecast: 6.4, baseline: 11.6, heldOut: false },
  { day: 'Day 4', actual: 5.8, forecast: 5.9, baseline: 11.6, heldOut: false },
  { day: 'Day 5', actual: 4.9, forecast: 5.0, baseline: 11.6, heldOut: false },
  { day: 'Day 6', actual: 4.3, forecast: 4.2, baseline: 11.6, heldOut: false },
  { day: 'Day 7', actual: 3.9, forecast: 3.9, baseline: 11.6, heldOut: false },
  { day: 'Day 8', actual: 3.8, forecast: 3.7, baseline: 11.6, heldOut: false },
  { day: 'Day 9', actual: 3.9, forecast: 3.8, baseline: 11.6, heldOut: false },
  { day: 'Day 10', actual: 3.7, forecast: 3.8, baseline: 11.6, heldOut: false },
  { day: 'Day 11', actual: 3.9, forecast: 4.0, baseline: 11.6, heldOut: true },
  { day: 'Day 12', actual: 3.8, forecast: 3.9, baseline: 11.6, heldOut: true },
  { day: 'Day 13', actual: 3.9, forecast: 3.8, baseline: 11.6, heldOut: true },
  { day: 'Day 14', actual: 3.9, forecast: 3.9, baseline: 11.6, heldOut: true },
]

export function buildPlanDashboard(lambda: number): PlanDashboardData {
  const rows = planRows.map((row) => {
    const recommendedQty = Math.round(row.profitQty + (row.planetQty - row.profitQty) * lambda)
    const delta = recommendedQty - row.oldQty
    const saving = Math.round(row.unitSaving * (row.oldQty - recommendedQty) * 0.72)

    return {
      ...row,
      recommendedQty,
      delta,
      saving,
    }
  })

  return {
    lambda,
    rows,
    totals: {
      oldQty: rows.reduce((total, row) => total + row.oldQty, 0),
      recommendedQty: rows.reduce((total, row) => total + row.recommendedQty, 0),
      saving: rows.reduce((total, row) => total + row.saving, 0),
    },
  }
}

export function getImpactDashboard(): ImpactDashboardData {
  return {
    rows: impactRows,
    accuracy: {
      mape: '3.9%',
      rmse: '0.4 kg',
      acceptance: '94%',
    },
  }
}