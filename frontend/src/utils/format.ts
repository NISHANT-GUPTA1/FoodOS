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