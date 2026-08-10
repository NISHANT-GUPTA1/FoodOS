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
}

export interface AttributionRow {
  label: string
  value: number
  detail: string
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
}

export interface WhyDashboardData {
  attribution: AttributionRow[]
  contributors: Array<{ label: string; value: number; note: string }>
  callout: string
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
  { to: '/today', label: 'Today', description: 'Ranked recommendations', tone: 'PREVENT' },
  { to: '/why', label: 'Why', description: 'Attribution and causes', tone: 'PRESERVE' },
  { to: '/plan', label: 'Plan', description: 'Lambda-driven prep table', tone: 'PREVENT' },
  { to: '/ledger', label: 'Ledger', description: 'Batch life and risk', tone: 'PRESERVE' },
  { to: '/rescue', label: 'Rescue', description: 'Channel ranking', tone: 'RECOVER' },
  { to: '/impact', label: 'Impact', description: 'Backtest and accuracy', tone: 'RECOVER' },
  { to: '/settings', label: 'Settings', description: 'Tokens and demo knobs', tone: 'PREVENT' },
]

export const todayDashboard: TodayDashboardData = {
  hero: '47 kitchens, 12 stores, 1 cluster forecast that replaces guesswork.',
  kpis: [
    { label: 'kg at risk', value: '1,248', delta: '+14% week over week', tone: 'recover', note: 'Stock with the shortest remaining life.' },
    { label: '₹ at risk', value: '₹94,800', delta: '18 batches within 6 hours', tone: 'preserve', note: 'Value that can still be saved or rerouted.' },
    { label: '% preventable', value: '63%', delta: 'Based on the current forecast band', tone: 'prevent', note: 'Loss that disappears when the plan is followed.' },
  ],
  recommendations: [
    {
      id: 'rec-1',
      horizon: 'PREVENT',
      title: 'Cut biryani prep at Spice Garden',
      subtitle: 'The weekday peak clears at 63 portions, not 80.',
      beforeQty: 80,
      afterQty: 63,
      why: 'Forecast confidence is tight, and the stockout penalty is already captured in the objective.',
      saves: { kg: 17, inr: 1500, co2e: 29 },
      confidence: 0.86,
      expiresIn: '84 min',
    },
    {
      id: 'rec-2',
      horizon: 'PRESERVE',
      title: 'Move the tomato crate to Store 12',
      subtitle: 'High velocity store, 2 km away, before the dock heat consumes another day of life.',
      beforeQty: 20,
      afterQty: 20,
      why: 'The same crate has 4.4 days of remaining life here and 3.1 days in the warehouse.',
      saves: { kg: 8, inr: 940, co2e: 14 },
      confidence: 0.91,
      expiresIn: '38 min',
    },
    {
      id: 'rec-3',
      horizon: 'RECOVER',
      title: 'Route leftover paneer to a nearby kitchen',
      subtitle: 'B2B transfer still beats donation and compost when the safety gate is open.',
      beforeQty: 6,
      afterQty: 6,
      why: 'RSL is below 12 hours, but transit plus handling is still safe for a close buyer.',
      saves: { kg: 6, inr: 1650, co2e: 11 },
      confidence: 0.78,
      expiresIn: '22 min',
    },
  ],
}

export const whyDashboard: WhyDashboardData = {
  attribution: [
    { label: 'Over-prep', value: 42, detail: 'Friday demand spikes push the kitchen past the optimal percentile.' },
    { label: 'Dock heat', value: 27, detail: 'Four hours on the receiving dock removes more life than the label admits.' },
    { label: 'Trim loss', value: 16, detail: 'Yield is lower than the standard on cauliflower and leafy greens.' },
    { label: 'FEFO miss', value: 9, detail: 'The nearest crate is not always the crate with the most value left.' },
    { label: 'Spoilage lag', value: 6, detail: 'Old stock stays visible long after it should have been recovered.' },
  ],
  contributors: [
    { label: 'Biryani over-prep', value: 42, note: 'The main preventable driver in the cluster.' },
    { label: 'Tomato dock excursion', value: 27, note: 'A preserve problem that becomes a recover problem later.' },
    { label: 'Cauliflower trim', value: 16, note: 'Edible florets leaving as peel and stem.' },
  ],
  callout: 'One forecast band, one ledger, one action engine. The cause changes by horizon, but the decision spine stays the same.',
}

export const planRows: PlanRow[] = [
  { dish: 'Biryani', oldQty: 80, profitQty: 68, planetQty: 58, unitSaving: 118 },
  { dish: 'Tomato curry', oldQty: 52, profitQty: 46, planetQty: 40, unitSaving: 92 },
  { dish: 'Paneer wrap', oldQty: 34, profitQty: 30, planetQty: 26, unitSaving: 74 },
  { dish: 'Cauliflower special', oldQty: 29, profitQty: 24, planetQty: 20, unitSaving: 81 },
]

export const ledgerBatches: LedgerRow[] = [
  { batch: 'TM-4471', sku: 'Tomato', qtyKg: 20, rslDays: 4.4, riskPercent: 31, valueAtRisk: 640, action: 'Route to Store 12', tone: 'preserve' },
  { batch: 'PN-2288', sku: 'Paneer', qtyKg: 6, rslDays: 0.8, riskPercent: 64, valueAtRisk: 1650, action: 'Transfer to nearby kitchen', tone: 'recover' },
  { batch: 'CB-8031', sku: 'Cauliflower', qtyKg: 14, rslDays: 2.1, riskPercent: 48, valueAtRisk: 910, action: 'Mark down and rotate', tone: 'prevent' },
  { batch: 'CH-1190', sku: 'Chicken', qtyKg: 18, rslDays: 1.4, riskPercent: 56, valueAtRisk: 1420, action: 'Prep in next service', tone: 'preserve' },
  { batch: 'SP-5012', sku: 'Spinach', qtyKg: 9, rslDays: 0.6, riskPercent: 72, valueAtRisk: 530, action: 'Deep markdown', tone: 'recover' },
]

export const rescueRows: RescueRow[] = [
  { channel: 'Nearby kitchen', recovery: '₹1,650', amount: '400 m', reason: 'Highest salvage value with the transit gate still open.', eligible: true },
  { channel: 'Deep markdown', recovery: '₹1,120', amount: 'Today only', reason: 'Short dwell remains, but the item can still sell on-site.', eligible: true },
  { channel: 'Donation', recovery: '₹0 cash', amount: 'NGO pickup', reason: 'Eligibility stays open because the item is not spoiled.', eligible: true },
  { channel: 'Processing', recovery: '₹420', amount: 'Batching window', reason: 'Quality is above the threshold for puree or pickle.', eligible: true },
  { channel: 'Animal feed', recovery: '₹90', amount: 'Rejected now', reason: 'Excluded because the crate is already past the safety gate.', eligible: false },
  { channel: 'Compost', recovery: '₹0', amount: 'Last resort', reason: 'Always available, but never the best value exit.', eligible: false },
]

export const impactRows: ImpactRow[] = [
  { day: 'Day 1', actual: 48, forecast: 46, baseline: 55, heldOut: false },
  { day: 'Day 2', actual: 49, forecast: 50, baseline: 55, heldOut: false },
  { day: 'Day 3', actual: 50, forecast: 49, baseline: 56, heldOut: false },
  { day: 'Day 4', actual: 53, forecast: 52, baseline: 58, heldOut: false },
  { day: 'Day 5', actual: 54, forecast: 55, baseline: 59, heldOut: false },
  { day: 'Day 6', actual: 56, forecast: 57, baseline: 61, heldOut: false },
  { day: 'Day 7', actual: 58, forecast: 59, baseline: 62, heldOut: false },
  { day: 'Day 8', actual: 60, forecast: 61, baseline: 64, heldOut: false },
  { day: 'Day 9', actual: 57, forecast: 58, baseline: 63, heldOut: false },
  { day: 'Day 10', actual: 59, forecast: 60, baseline: 65, heldOut: false },
  { day: 'Day 11', actual: 61, forecast: 60, baseline: 66, heldOut: true },
  { day: 'Day 12', actual: 63, forecast: 62, baseline: 67, heldOut: true },
  { day: 'Day 13', actual: 62, forecast: 63, baseline: 68, heldOut: true },
  { day: 'Day 14', actual: 64, forecast: 65, baseline: 70, heldOut: true },
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
      mape: '11.8%',
      rmse: '7.2 kg',
      acceptance: '78%',
    },
  }
}