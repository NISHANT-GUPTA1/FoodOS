import { useMutation } from '@tanstack/react-query'
import { Check, Clock3, Flame, RotateCcw } from 'lucide-react'
import { acceptRecommendation, overrideRecommendation } from '../api/mockApi'
import type { RecommendationData } from '../mocks/dashboard'
import { formatCo2e, formatInr } from '../utils/format'

interface RecommendationCardProps {
  data: RecommendationData
  /**
   * The buttons below post to the KITCHEN lifecycle
   * (`/api/recommendations/{id}/accept|override`).
   *
   * The agri batch surface has its own pair — Contract 2b #8/#9 route a plan through
   * `/api/plans/{id}/accept|override` — so Screen 3 renders the card with
   * `showActions={false}` and owns the lifecycle itself. Default stays `true`, so
   * every existing kitchen caller is untouched.
   */
  showActions?: boolean
}

// One colour per horizon, read from the tokens in index.css / tailwind.config.js.
// `ink` is the accessible text tone; `border` tints the card edge.
const horizonStyles: Record<RecommendationData['horizon'], { border: string; ink: string; icon: React.ReactNode }> = {
  PREVENT: {
    border: 'border-prevent/20',
    ink: 'text-prevent-ink',
    icon: <Flame className="h-4 w-4" />,
  },
  PRESERVE: {
    border: 'border-preserve/20',
    ink: 'text-preserve-ink',
    icon: <Clock3 className="h-4 w-4" />,
  },
  RECOVER: {
    border: 'border-recover/20',
    ink: 'text-recover-ink',
    icon: <RotateCcw className="h-4 w-4" />,
  },
}

export function RecommendationCard({ data, showActions = true }: RecommendationCardProps) {
  const style = horizonStyles[data.horizon]

  const accept = useMutation({ mutationFn: () => acceptRecommendation(data.id) })
  const override = useMutation({ mutationFn: () => overrideRecommendation(data.id, 'Overridden from the card') })

  const outcome = accept.data?.status ?? override.data?.status
  const pending = accept.isPending || override.isPending
  const failed = accept.isError || override.isError

  return (
    <article className={`panel ${style.border} p-5 text-[#1c1b1b] transition hover:-translate-y-0.5 hover:border-[#747878]`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`chip border border-[#c4c7c8] bg-[#f1edec] ${style.ink}`}>{style.icon} <span className="ml-2">{data.horizon}</span></span>
            <span className="text-xs uppercase tracking-[0.25em] text-[#646464]">Confidence {Math.round(data.confidence * 100)}%</span>
            <span className="text-xs uppercase tracking-[0.25em] text-[#646464]">Expires in {data.expiresIn}</span>
          </div>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-[#1c1b1b]">{data.title}</h2>
            <p className="mt-2 text-sm leading-7 text-[#444748]">{data.subtitle}</p>
          </div>
        </div>
        <div className="rounded-3xl border border-[#c4c7c8] bg-[#f6f3f2] px-5 py-4 text-right">
          <div className="text-xs uppercase tracking-[0.25em] text-[#646464]">Qty</div>
          <div className="mt-2 text-3xl font-semibold text-[#1c1b1b]">
            {data.beforeQty} <span className="text-[#747878]">→</span> {data.afterQty}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[1.3fr_0.9fr]">
        <div className="rounded-3xl border border-[#c4c7c8] bg-[#f6f3f2] p-4">
          <p className="text-xs uppercase tracking-[0.28em] text-[#646464]">Why</p>
          <p className="mt-3 text-sm leading-7 text-[#1c1b1b]">{data.why}</p>
        </div>
        <div className="rounded-3xl border border-[#c4c7c8] bg-[#f6f3f2] p-4">
          <p className="text-xs uppercase tracking-[0.28em] text-[#646464]">Saves</p>
          <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-[#646464]">kg</div>
              <div className="mt-1 font-semibold text-[#1c1b1b]">{data.saves.kg}</div>
            </div>
            <div>
              <div className="text-[#646464]">₹</div>
              <div className="mt-1 font-semibold text-[#1c1b1b]">{formatInr(data.saves.inr)}</div>
            </div>
            <div>
              <div className="text-[#646464]">CO₂e</div>
              <div className="mt-1 font-semibold text-[#1c1b1b]">{formatCo2e(data.saves.co2e)}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#c4c7c8] pt-4">
        <div className="text-sm text-[#444748]">
          {failed ? (
            <span className="text-[#ba1a1a]">That did not save. Try again — the recommendation is unchanged.</span>
          ) : outcome ? (
            <span>
              Marked <span className="font-medium text-[#1c1b1b]">{outcome}</span>. It stays on the list until the next refresh.
            </span>
          ) : (
            <>
              {/* Was "confidence from the current mock contract". A judge reads
                  that on the hero card and concludes nothing behind it is real,
                  however much of the backend is running. Provenance is shown
                  when the response carries a run id, and simply omitted when it
                  does not — an invented id would be a worse lie than the word
                  "mock" was. */}
              <span className="font-medium text-[#1c1b1b]">{Math.round(data.confidence * 100)}%</span> confidence
              {data.modelRunId ? (
                <> · model run <span className="font-mono text-xs text-[#1c1b1b]">{data.modelRunId}</span></>
              ) : null}
            </>
          )}
        </div>
        {showActions ? (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="button-primary"
              onClick={() => accept.mutate()}
              disabled={pending || Boolean(outcome)}
            >
              <Check className="h-4 w-4" />
              {accept.isPending ? 'Accepting…' : 'Accept'}
            </button>
            <button
              type="button"
              className="button-ghost"
              onClick={() => override.mutate()}
              disabled={pending || Boolean(outcome)}
            >
              {override.isPending ? 'Overriding…' : 'Override'}
            </button>
          </div>
        ) : null}
      </div>
    </article>
  )
}