export const inrFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 0,
})

export const compactNumberFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 1,
})

export const percentFormatter = new Intl.NumberFormat('en-US', {
  style: 'percent',
  maximumFractionDigits: 0,
})

export function formatInr(value: number) {
  return `₹${inrFormatter.format(value)}`
}

export function formatKg(value: number) {
  return `${compactNumberFormatter.format(value)} kg`
}

export function formatCo2e(value: number) {
  return `${compactNumberFormatter.format(value)} kg CO₂e`
}

export function formatPercent(value: number) {
  return percentFormatter.format(value)
}

/* -------- agri batch surface -------- */

/**
 * Indian grouping: ₹1,22,260 — never ₹122,260. Must agree with
 * `agents/facts.py::format_indian` on the backend (D verifies this at H19-24).
 */
export function formatIndianInr(value: number) {
  return `₹${inrFormatter.format(Math.round(value))}`
}

/** Signed, for a delta-vs-baseline that must never read as an absolute. */
export function formatInrDelta(value: number) {
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}₹${inrFormatter.format(Math.abs(Math.round(value)))}`
}

/** Whole kilograms with Indian grouping — 10,000 kg. */
export function formatKgWhole(value: number) {
  return `${inrFormatter.format(Math.round(value))} kg`
}

/** Tonnes, for allocations. 6000 -> "6 T". */
export function formatTonnes(kg: number) {
  const t = kg / 1000
  return `${Number.isInteger(t) ? t : t.toFixed(1)} T`
}

/** One decimal, because the calibration gate is stated to one decimal (8.4 / 3.9). */
export function formatLossPct(value: number) {
  return `${value.toFixed(1)}%`
}

/** RUL is always hours. Never days — the blueprint is explicit about this. */
export function formatHours(value: number) {
  return `${Math.round(value)} h`
}

/** A live countdown: 30h 12m. */
export function formatCountdown(msRemaining: number) {
  if (msRemaining <= 0) return 'expired'
  const totalMinutes = Math.floor(msRemaining / 60_000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  const seconds = Math.floor((msRemaining % 60_000) / 1000)
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, '0')}m`
  return `${minutes}m ${String(seconds).padStart(2, '0')}s`
}

const timeFormatter = new Intl.DateTimeFormat('en-IN', {
  hour: '2-digit',
  minute: '2-digit',
  day: '2-digit',
  month: 'short',
})

export function formatTimestamp(iso: string) {
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? iso : timeFormatter.format(parsed)
}