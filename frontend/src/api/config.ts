export type ApiMode = 'mock' | 'live'

export function getApiMode(): ApiMode {
  const mode = import.meta.env.VITE_FOODS_API_MODE

  return mode === 'live' ? 'live' : 'mock'
}

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_FOODS_API_BASE_URL ?? ''
}