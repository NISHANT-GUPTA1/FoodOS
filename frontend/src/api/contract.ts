import type { ActionPlanCandidate } from '../mocks/dashboard'

export interface ApiResponse<T> {
  data: T
}

export interface LambdaQueryParams {
  lambda: number
}

export interface PlanRequest {
  lambda: number
}

export interface PlanRow {
  dish: string
  oldQty: number
  recommendedQty: number
  delta: number
  saving: number
}

export interface PlanResponse {
  lambda: number
  rows: PlanRow[]
  totals: {
    oldQty: number
    recommendedQty: number
    saving: number
  }
}

export interface KpiCardData {
  label: string
  value: string
  delta: string
  tone: 'prevent' | 'preserve' | 'recover'
  note: string
}

export interface RecommendationData {
  id: string
  horizon: 'PREVENT' | 'PRESERVE' | 'RECOVER'
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

export interface BatchProfileData {
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

export interface TodayResponse {
  hero: string
  kpis: KpiCardData[]
  recommendations: RecommendationData[]
  actionMatrix?: ActionPlanCandidate[]
  batchProfile?: BatchProfileData
}

export interface AttributionRow {
  label: string
  value: number
  detail: string
}

export interface WhyResponse {
  attribution: AttributionRow[]
  contributors: Array<{ label: string; value: number; note: string }>
  callout: string
  nabconsBaseline?: {
    annualLossInr: string
    fruitsVegLossRange: string
    tomatoLossPercent: string
    guavaLossPercent: string
  }
}

export interface LedgerRow {
  batch: string
  sku: string
  qtyKg: number
  rslDays: number
  riskPercent: number
  valueAtRisk: number
  action: string
  tone: 'prevent' | 'preserve' | 'recover'
}

export interface LedgerResponse {
  batches: LedgerRow[]
}

export interface RescueRow {
  channel: string
  recovery: string
  amount: string
  reason: string
  eligible: boolean
}

export interface RescueResponse {
  rows: RescueRow[]
}

export interface ImpactRow {
  day: string
  actual: number
  forecast: number
  baseline: number
  heldOut: boolean
}

export interface ImpactResponse {
  rows: ImpactRow[]
  accuracy: {
    mape: string
    rmse: string
    acceptance: string
  }
}

export interface OutcomeResponse {
  id: string
  status: 'accepted' | 'overridden' | 'pending'
}

export const apiPaths = {
  today: '/api/today',
  why: '/api/attribution',
  plan: '/api/plan',
  ledger: '/api/ledger',
  rescue: '/api/rescue',
  impact: '/api/impact',
  accept: (id: string) => `/api/recommendations/${id}/accept`,
  override: (id: string) => `/api/recommendations/${id}/override`,
} as const