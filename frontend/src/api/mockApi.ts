import {
  buildPlanDashboard,
  getImpactDashboard,
  ledgerBatches,
  rescueRows,
  todayDashboard,
  whyDashboard,
} from '../mocks/dashboard'
import { getApiMode } from './config'
import { apiPaths, type ApiResponse, type ImpactResponse, type LedgerResponse, type PlanRequest, type PlanResponse, type RescueResponse, type TodayResponse, type WhyResponse } from './contract'
import { fetchJson } from './http'

const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

export async function fetchTodayDashboard() {
  if (getApiMode() === 'live') {
    const response = await fetchJson<ApiResponse<TodayResponse>>(apiPaths.today)
    return response.data
  }

  await delay(140)
  return todayDashboard
}

export async function fetchWhyDashboard() {
  if (getApiMode() === 'live') {
    const response = await fetchJson<ApiResponse<WhyResponse>>(apiPaths.why)
    return response.data
  }

  await delay(140)
  return whyDashboard
}

export async function fetchPlanDashboard(request: PlanRequest): Promise<PlanResponse> {
  const { lambda } = request

  if (getApiMode() === 'live') {
    const response = await fetchJson<ApiResponse<PlanResponse>>(`${apiPaths.plan}?lambda=${lambda.toFixed(2)}`)
    return response.data
  }

  await delay(160)
  return buildPlanDashboard(lambda)
}

export async function fetchLedgerDashboard() {
  if (getApiMode() === 'live') {
    const response = await fetchJson<ApiResponse<LedgerResponse>>(apiPaths.ledger)
    return response.data
  }

  await delay(120)
  return { batches: ledgerBatches }
}

export async function fetchRescueDashboard() {
  if (getApiMode() === 'live') {
    const response = await fetchJson<ApiResponse<RescueResponse>>(apiPaths.rescue)
    return response.data
  }

  await delay(120)
  return { rows: rescueRows }
}

export async function fetchImpactDashboard() {
  if (getApiMode() === 'live') {
    const response = await fetchJson<ApiResponse<ImpactResponse>>(apiPaths.impact)
    return response.data
  }

  await delay(150)
  return getImpactDashboard()
}