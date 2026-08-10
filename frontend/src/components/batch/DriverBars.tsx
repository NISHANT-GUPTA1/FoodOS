import type { LossDriver } from '../../api/batchContract'

interface DriverBarsProps {
  drivers: LossDriver[]
  modelRunId?: string
}

const DRIVER_LABELS: Record<string, string> = {
  field_heat_hours: 'Accumulated field heat',
  transit_temperature: 'Transit temperature',
  open_transport: 'Open transport',
  road_vibration: 'Road vibration',
  maturity_stage: 'Maturity at cut',
  damage_factor: 'Mechanical damage',
  packaging: 'Packaging',
}

function label(name: string) {
  return DRIVER_LABELS[name] ?? name.replace(/_/g, ' ')
}

/**
 * Primary loss drivers as ranked bars.
 *
 * These are model output — SHAP or gain from A's trained model — not a hardcoded list.
 * The `model_run_id` is printed so every bar traces back to a run.
 */
export function DriverBars({ drivers, modelRunId }: DriverBarsProps) {
  const sorted = [...drivers].sort((a, b) => b.contribution - a.contribution)
  const max = sorted[0]?.contribution ?? 1

  return (
    <div className="rounded-2xl border border-slate-200 bg-white/80 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Primary loss drivers</p>
        {modelRunId ? (
          <span className="font-mono text-[10px] text-slate-400">run {modelRunId}</span>
        ) : null}
      </div>

      <ol className="mt-4 space-y-4">
        {sorted.map((driver, index) => (
          <li key={driver.name}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm font-bold capitalize text-slate-900">
                <span className="mr-2 font-mono text-xs text-slate-400">{index + 1}</span>
                {label(driver.name)}
              </span>
              <span className="font-mono text-sm font-bold tabular-nums text-slate-700">
                {Math.round(driver.contribution * 100)}%
              </span>
            </div>
            <div className="mt-1.5 h-2 w-full rounded-full bg-slate-200/80">
              <div
                className="h-2 rounded-full bg-slate-800"
                style={{ width: `${(driver.contribution / max) * 100}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{driver.text}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}
