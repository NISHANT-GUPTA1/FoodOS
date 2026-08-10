/**
 * Contract 2 client — all eleven agri endpoints.
 *
 * Mock-first by design. Team Split v2 §5 hard rule: "you never wait for the backend.
 * Mocks until H26. If B is late, you are still finished."
 *
 * H26–31 asks for the swap to happen ONE ENDPOINT AT A TIME as B ships. That is what
 * `LIVE_ENDPOINTS` is for: flip a single key (or set VITE_FOODOS_LIVE_ENDPOINTS) and
 * exactly that call goes to :8000 while the rest keep serving mocks. No screen changes.
 */

import { getApiMode } from './config'
import { fetchJson, postForm, postJson } from './http'
import {
  type BatchListRow,
  batchPaths,
  type BatchListResponse,
  type BatchProfile,
  type CreateBatchRequest,
  type CreateBatchResponse,
  type HealthResponse,
  type MarketsResponse,
  type PhotoUploadResponse,
  type PlanOutcomeResponse,
  type PlansResponse,
  type QuestionnaireResponse,
  type SimulateRequest,
  type SimulateResponse,
} from './batchContract'
import {
  BATCH_LIST,
  HEALTH,
  MARKETS,
  T1024_PLANS_RESPONSE,
  T1024_PROFILE,
  TOMATO_QUESTIONNAIRE,
  simulateMock,
} from '../mocks/batch'
import type { RiskLevel } from '../lib/risk'

export type EndpointKey =
  | 'questionnaire'
  | 'createBatch'
  | 'photos'
  | 'batches'
  | 'batch'
  | 'plans'
  | 'simulate'
  | 'accept'
  | 'override'
  | 'markets'
  | 'health'

/** Flip to true as B confirms each endpoint is real. */
const LIVE_ENDPOINTS: Record<EndpointKey, boolean> = {
  questionnaire: false,
  createBatch: false,
  photos: false,
  batches: false,
  batch: false,
  plans: false,
  simulate: false,
  accept: false,
  override: false,
  markets: false,
  health: false,
}

const envOverrides = (import.meta.env.VITE_FOODOS_LIVE_ENDPOINTS ?? '')
  .split(',')
  .map((k: string) => k.trim())
  .filter(Boolean)

function isLive(key: EndpointKey): boolean {
  if (getApiMode() !== 'live') return false
  if (envOverrides.includes('all')) return true
  if (envOverrides.length > 0) return envOverrides.includes(key)
  return LIVE_ENDPOINTS[key]
}

/** Mock latency, so loading states get exercised in development instead of at H32. */
const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

/* ---------------------------------------------------------------- */

export async function getQuestionnaire(commodity = 'tomato'): Promise<QuestionnaireResponse> {
  if (isLive('questionnaire')) {
    return fetchJson<QuestionnaireResponse>(`${batchPaths.questionnaire}?commodity=${encodeURIComponent(commodity)}`)
  }
  await delay(120)
  return TOMATO_QUESTIONNAIRE
}

/**
 * Batches registered through the wizard during this session.
 *
 * Mock mode used to answer `createBatch` with a hardcoded `T1042` that was in
 * no list, so finishing the wizard navigated straight to "No batch T1042" —
 * the demo's own happy path dead-ended on its last step. A created batch has to
 * be retrievable afterwards, so it is kept here and consulted by `listBatches`
 * and `getBatch` alongside the fixtures.
 *
 * Session-scoped on purpose: a reload clears it, which matches a mock backend
 * with no database behind it. Live mode never touches this.
 */
const CREATED: BatchListRow[] = []

export async function createBatch(body: CreateBatchRequest): Promise<CreateBatchResponse> {
  if (isLive('createBatch')) {
    return postJson<CreateBatchResponse>(batchPaths.batches, body)
  }
  await delay(260)

  const id = `T${1024 + BATCH_LIST.batches.length + CREATED.length + 1}`
  const reference = BATCH_LIST.batches[0]

  CREATED.push({
    ...reference,
    id,
    commodity: body.commodity,
    qty_kg: body.qty_kg,
    origin: body.origin,
    destination: body.destination,
    status: 'assessed',
  })

  return { id, status: 'assessed', photos_expected: 3 }
}

export async function uploadPhotos(batchId: string, files: File[]): Promise<PhotoUploadResponse> {
  if (isLive('photos')) {
    const form = new FormData()
    files.forEach((file) => form.append('photos', file))
    return postForm<PhotoUploadResponse>(batchPaths.photos(batchId), form)
  }
  await delay(200 + files.length * 60)
  return {
    batch_id: batchId,
    accepted: files.length,
    // Zero photos is not an error. CV degrades to the rule-based fallback.
    vision_confidence: files.length >= 3 ? 'MEDIUM' : files.length > 0 ? 'LOW' : 'LOW',
  }
}

export interface BatchListFilters {
  status?: string
  risk?: RiskLevel | ''
}

export async function getBatches(filters: BatchListFilters = {}): Promise<BatchListResponse> {
  if (isLive('batches')) {
    const params = new URLSearchParams()
    if (filters.status) params.set('status', filters.status)
    if (filters.risk) params.set('risk', filters.risk)
    const query = params.toString()
    return fetchJson<BatchListResponse>(`${batchPaths.batches}${query ? `?${query}` : ''}`)
  }

  await delay(140)
  const batches = [...BATCH_LIST.batches, ...CREATED].filter(
    (b) => (!filters.status || b.status === filters.status) && (!filters.risk || b.level === filters.risk),
  )
  return { ...BATCH_LIST, batches }
}

/** Thrown when an id is not in the set, so the screen can say so rather than
 *  render a different batch under the requested id. */
export class BatchNotFoundError extends Error {
  constructor(public readonly id: string) {
    super(`No batch ${id}`)
    this.name = 'BatchNotFoundError'
  }
}

export async function getBatch(id: string): Promise<BatchProfile> {
  if (isLive('batch')) {
    return fetchJson<BatchProfile>(batchPaths.batch(id))
  }
  await delay(160)
  // An id that is not in the set is NOT T1024. Returning T1024 for anything
  // unknown put a different batch on screen from the one in the URL — type
  // /batches/T1042 and the header still read T1024. A judge changing the URL,
  // or a wrong click mid-demo, would have caught that. A "batch not found" is a
  // thousand times better than a confident wrong number.
  const row = [...BATCH_LIST.batches, ...CREATED].find((b) => b.id === id)
  if (!row) throw new BatchNotFoundError(id)
  if (id === T1024_PROFILE.id) return T1024_PROFILE
  return {
    ...T1024_PROFILE,
    id: row.id,
    qty_kg: row.qty_kg,
    origin: row.origin,
    destination: row.destination,
    risk: { ...T1024_PROFILE.risk, loss_pct: row.loss_pct, loss_kg: row.loss_kg, rul_hours: row.rul_hours, level: row.level },
  }
}

export async function getPlans(id: string): Promise<PlansResponse> {
  if (isLive('plans')) {
    return fetchJson<PlansResponse>(batchPaths.plans(id))
  }
  await delay(180)
  return { ...T1024_PLANS_RESPONSE, batch_id: id }
}

export async function simulate(id: string, body: SimulateRequest): Promise<SimulateResponse> {
  if (isLive('simulate')) {
    return postJson<SimulateResponse>(batchPaths.simulate(id), body)
  }
  // Deliberately short: Screen 4 is the judge-interaction moment and must feel instant.
  await delay(90)
  return simulateMock(body)
}

export async function acceptPlan(planId: number): Promise<PlanOutcomeResponse> {
  if (isLive('accept')) {
    return postJson<PlanOutcomeResponse>(batchPaths.accept(planId), {})
  }
  await delay(180)
  return { plan_id: planId, outcome: 'accepted', recorded_at: new Date().toISOString() }
}

export async function overridePlan(planId: number, reason: string): Promise<PlanOutcomeResponse> {
  if (isLive('override')) {
    return postJson<PlanOutcomeResponse>(batchPaths.override(planId), { reason })
  }
  await delay(180)
  return { plan_id: planId, outcome: 'overridden', recorded_at: new Date().toISOString(), reason }
}

export async function getMarkets(commodity = 'tomato', near = 'Kolar Collection Hub'): Promise<MarketsResponse> {
  if (isLive('markets')) {
    return fetchJson<MarketsResponse>(
      `${batchPaths.markets}?commodity=${encodeURIComponent(commodity)}&near=${encodeURIComponent(near)}`,
    )
  }
  await delay(130)
  return { ...MARKETS, commodity, near }
}

export async function getHealth(): Promise<HealthResponse> {
  if (isLive('health')) {
    return fetchJson<HealthResponse>(batchPaths.health)
  }
  await delay(60)
  return HEALTH
}
