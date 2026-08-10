import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Camera, Check, ImageOff, Loader2, X } from 'lucide-react'
import { createBatch, getQuestionnaire, uploadPhotos } from '../../api/batchApi'
import type {
  CreateBatchRequest,
  PackagingType,
  Question,
  QuestionnaireStep,
  TransportMode,
} from '../../api/batchContract'
import { SectionHeader } from '../../components/SectionHeader'
import { ErrorState, LoadingState } from '../../components/StatePanel'
import { SourceNote } from '../../components/batch/SourceNote'
import { formatKgWhole } from '../../utils/format'

type AnswerValue = string | number
type Answers = Record<string, AnswerValue>

/**
 * Screen 2 — Create Batch.
 *
 * Driven ENTIRELY by `GET /api/questionnaire`. Not one question, option, branch rule
 * or feature key is written in this file — the tree is D's `content/questionnaire/
 * tomato.yaml`, served as data. Adding a second commodity must never require a
 * frontend release.
 *
 * Budget: under 30 seconds on a phone-width viewport. That is why every question is
 * a tap target, defaults are pre-filled, and photos are skippable.
 */
export function CreateBatchScreen() {
  const navigate = useNavigate()
  const [stepIndex, setStepIndex] = useState(0)
  const [answers, setAnswers] = useState<Answers>({})
  const [photos, setPhotos] = useState<File[]>([])
  const startedAt = useRef<number>(Date.now())

  const questionnaire = useQuery({
    queryKey: ['questionnaire', 'tomato'],
    queryFn: () => getQuestionnaire('tomato'),
  })

  // Seed defaults from the tree the moment it lands, so the wizard starts pre-filled.
  useEffect(() => {
    if (!questionnaire.data) return
    const defaults: Answers = {}
    questionnaire.data.steps.forEach((step) =>
      step.questions.forEach((q) => {
        if (q.default !== undefined) defaults[q.id] = q.default
      }),
    )
    setAnswers((prev) => ({ ...defaults, ...prev }))
  }, [questionnaire.data])

  const submit = useMutation({
    mutationFn: async () => {
      const body = buildRequest(questionnaire.data?.steps ?? [], answers)
      const created = await createBatch(body)
      if (photos.length > 0) await uploadPhotos(created.id, photos)
      return created
    },
    onSuccess: (created) => navigate(`/batches/${created.id}`),
  })

  const steps = questionnaire.data?.steps ?? []
  const step: QuestionnaireStep | undefined = steps[stepIndex]

  const visibleQuestions = useMemo(
    () => (step ? step.questions.filter((q) => isVisible(q, answers)) : []),
    [step, answers],
  )

  const blocking = visibleQuestions.filter((q) => q.required && isBlank(answers[q.id]))
  const canAdvance = blocking.length === 0
  const isLast = stepIndex === steps.length - 1

  if (questionnaire.isLoading) {
    return <LoadingState title="Loading the assessment tree" description="Fetching the adaptive questionnaire for tomato." />
  }

  if (questionnaire.isError || steps.length === 0) {
    return (
      <ErrorState
        title="Assessment tree unavailable"
        description="The questionnaire endpoint did not answer, and this wizard is deliberately unable to invent questions of its own. Retry once the content service is back."
        action={
          <button type="button" className="button-primary" onClick={() => questionnaire.refetch()}>
            Retry
          </button>
        }
      />
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionHeader
        eyebrow="Screen 2 · Create Batch"
        title="Register a consignment"
        description={`${steps.length} steps, about ${questionnaire.data?.target_seconds ?? 30} seconds. Every answer feeds one feature vector — nothing is asked twice.`}
      />

      <ol className="flex flex-wrap items-center gap-2">
        {steps.map((s, index) => (
          <li key={s.id} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => index < stepIndex && setStepIndex(index)}
              disabled={index > stepIndex}
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider transition ${
                index === stepIndex
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : index < stepIndex
                    ? 'border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                    : 'border-slate-200 bg-white/70 text-slate-400'
              }`}
            >
              {index < stepIndex ? <Check className="h-3 w-3" /> : <span className="font-mono">{index + 1}</span>}
              <span className="hidden sm:inline">{s.title.split(' ').slice(0, 3).join(' ')}</span>
            </button>
            {index < steps.length - 1 ? <span className="h-px w-3 bg-slate-300" /> : null}
          </li>
        ))}
      </ol>

      <section className="rounded-3xl border-2 border-slate-300 bg-white/90 p-6 shadow-xl backdrop-blur-xl sm:p-8">
        <h2 className="text-2xl font-extrabold tracking-tight text-slate-900">{step?.title}</h2>
        <p className="mt-1.5 text-sm font-medium leading-relaxed text-slate-600">{step?.subtitle}</p>

        <div className="mt-7 space-y-7">
          {visibleQuestions.map((question) => (
            <QuestionField
              key={question.id}
              question={question}
              value={answers[question.id]}
              onChange={(value) => setAnswers((prev) => ({ ...prev, [question.id]: value }))}
              photos={photos}
              onPhotos={setPhotos}
            />
          ))}
        </div>

        {submit.isError ? (
          <p className="mt-6 rounded-2xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-800">
            The batch could not be registered. Nothing was saved — your answers are still here, press Register again.
          </p>
        ) : null}

        <footer className="mt-8 flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            onClick={() => (stepIndex === 0 ? navigate('/command') : setStepIndex((i) => i - 1))}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold uppercase text-slate-700 transition hover:bg-slate-100 active:scale-95"
          >
            <ArrowLeft className="h-4 w-4" />
            {stepIndex === 0 ? 'Cancel' : 'Back'}
          </button>

          <div className="flex items-center gap-3">
            {!canAdvance ? (
              <span className="text-[11px] font-semibold text-slate-500">
                {blocking.length} answer{blocking.length > 1 ? 's' : ''} still needed
              </span>
            ) : null}

            {isLast ? (
              <button
                type="button"
                disabled={!canAdvance || submit.isPending}
                onClick={() => submit.mutate()}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-bold uppercase text-white shadow-md transition hover:bg-emerald-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {submit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                {submit.isPending ? 'Scoring batch' : 'Register & score'}
              </button>
            ) : (
              <button
                type="button"
                disabled={!canAdvance}
                onClick={() => setStepIndex((i) => i + 1)}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-bold uppercase text-white shadow-md transition hover:bg-slate-800 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Continue
                <ArrowRight className="h-4 w-4 text-emerald-400" />
              </button>
            )}
          </div>
        </footer>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <SourceNote source={questionnaire.data?.source} label="Questionnaire" />
        <span className="font-mono text-[10px] text-slate-400">
          tree {questionnaire.data?.version} · {Math.round((Date.now() - startedAt.current) / 1000)}s elapsed
        </span>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- *
 * Branch evaluation — the rules travel with the data
 * ---------------------------------------------------------------- */

function isVisible(question: Question, answers: Answers): boolean {
  const rule = question.show_if
  if (!rule) return true
  const answer = String(answers[rule.question] ?? '')
  if (rule.in && !rule.in.includes(answer)) return false
  if (rule.not_in && rule.not_in.includes(answer)) return false
  return true
}

function isBlank(value: AnswerValue | undefined) {
  return value === undefined || value === '' || value === null
}

function buildRequest(steps: QuestionnaireStep[], answers: Answers): CreateBatchRequest {
  const byFeature: Record<string, AnswerValue> = {}
  steps.forEach((step) =>
    step.questions.forEach((q) => {
      if (isVisible(q, answers) && !isBlank(answers[q.id])) byFeature[q.feature_key] = answers[q.id]
    }),
  )

  return {
    commodity: String(byFeature.commodity ?? 'tomato'),
    qty_kg: Number(byFeature.qty_kg ?? 0),
    origin: String(byFeature.origin ?? ''),
    destination: String(byFeature.destination ?? ''),
    transport: (byFeature.transport ?? 'open_truck') as TransportMode,
    packaging: (byFeature.packaging ?? 'ventilated_plastic_crate') as PackagingType,
    depart_at: byFeature.depart_at ? String(byFeature.depart_at) : undefined,
    answers: byFeature,
  }
}

/* ---------------------------------------------------------------- *
 * Field renderers — one per `kind`, nothing per question
 * ---------------------------------------------------------------- */

interface QuestionFieldProps {
  question: Question
  value: AnswerValue | undefined
  onChange: (value: AnswerValue) => void
  photos: File[]
  onPhotos: (files: File[]) => void
}

function QuestionField({ question, value, onChange, photos, onPhotos }: QuestionFieldProps) {
  return (
    <fieldset>
      <legend className="text-sm font-bold text-slate-900">
        {question.prompt}
        {question.required ? <span className="ml-1 text-rose-600">*</span> : null}
      </legend>
      {question.help ? <p className="mt-1 text-xs leading-relaxed text-slate-500">{question.help}</p> : null}

      <div className="mt-3">
        {question.kind === 'single' ? (
          <div className="grid gap-2 sm:grid-cols-2">
            {(question.options ?? []).map((option) => {
              const active = String(value ?? '') === option.value
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onChange(option.value)}
                  className={`rounded-2xl border-2 px-4 py-3 text-left transition active:scale-[0.98] ${
                    active
                      ? 'border-emerald-500 bg-emerald-50 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <span className={`block text-sm font-bold ${active ? 'text-emerald-900' : 'text-slate-800'}`}>
                    {option.label}
                  </span>
                  {option.hint ? <span className="mt-0.5 block text-[11px] text-slate-500">{option.hint}</span> : null}
                </button>
              )
            })}
          </div>
        ) : null}

        {question.kind === 'number' ? (
          <div className="flex items-center gap-3">
            <input
              type="number"
              inputMode="decimal"
              min={question.min}
              max={question.max}
              step={question.step ?? 1}
              value={value === undefined ? '' : Number(value)}
              onChange={(event) => onChange(event.target.value === '' ? '' : Number(event.target.value))}
              className="w-full max-w-[16rem] rounded-2xl border-2 border-slate-200 bg-white px-4 py-3 font-mono text-lg font-bold tabular-nums text-slate-900 outline-none transition focus:border-emerald-500"
            />
            {question.unit ? <span className="text-sm font-bold text-slate-500">{question.unit}</span> : null}
            {question.feature_key === 'qty_kg' && Number(value) > 0 ? (
              <span className="text-xs font-semibold text-slate-500">{formatKgWhole(Number(value))}</span>
            ) : null}
          </div>
        ) : null}

        {question.kind === 'time' ? (
          <input
            type="time"
            value={String(value ?? '')}
            onChange={(event) => onChange(event.target.value)}
            className="rounded-2xl border-2 border-slate-200 bg-white px-4 py-3 font-mono text-lg font-bold text-slate-900 outline-none transition focus:border-emerald-500"
          />
        ) : null}

        {question.kind === 'text' ? (
          <input
            type="text"
            placeholder={question.placeholder}
            value={String(value ?? '')}
            onChange={(event) => onChange(event.target.value)}
            className="w-full rounded-2xl border-2 border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-900 outline-none transition focus:border-emerald-500"
          />
        ) : null}

        {question.kind === 'photos' ? (
          <PhotoField question={question} photos={photos} onPhotos={onPhotos} />
        ) : null}
      </div>
    </fieldset>
  )
}

function PhotoField({ question, photos, onPhotos }: { question: Question; photos: File[]; onPhotos: (files: File[]) => void }) {
  const [previews, setPreviews] = useState<string[]>([])
  const max = question.max ?? 5
  const min = question.min ?? 3

  useEffect(() => {
    const urls = photos.map((file) => URL.createObjectURL(file))
    setPreviews(urls)
    return () => urls.forEach((url) => URL.revokeObjectURL(url))
  }, [photos])

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
        {previews.map((url, index) => (
          <div key={url} className="group relative aspect-square overflow-hidden rounded-2xl border-2 border-slate-200">
            <img src={url} alt={`Lot photo ${index + 1}`} className="h-full w-full object-cover" />
            <button
              type="button"
              onClick={() => onPhotos(photos.filter((_, i) => i !== index))}
              className="absolute right-1 top-1 rounded-full bg-slate-900/80 p-1 text-white opacity-0 transition group-hover:opacity-100"
              aria-label={`Remove photo ${index + 1}`}
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}

        {photos.length < max ? (
          <label className="flex aspect-square cursor-pointer flex-col items-center justify-center gap-1.5 rounded-2xl border-2 border-dashed border-slate-300 bg-white text-slate-500 transition hover:border-emerald-500 hover:text-emerald-700">
            <Camera className="h-6 w-6" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Add</span>
            <input
              type="file"
              accept="image/*"
              multiple
              capture="environment"
              className="hidden"
              onChange={(event) => {
                const picked = Array.from(event.target.files ?? [])
                onPhotos([...photos, ...picked].slice(0, max))
                event.target.value = ''
              }}
            />
          </label>
        ) : null}
      </div>

      <p className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        {photos.length === 0 ? <ImageOff className="h-3.5 w-3.5" /> : <Camera className="h-3.5 w-3.5" />}
        {photos.length === 0
          ? 'No photos. The batch still scores — vision degrades to the rule-based fallback and confidence drops.'
          : `${photos.length} of ${min}–${max} photos attached.`}
      </p>
    </div>
  )
}
