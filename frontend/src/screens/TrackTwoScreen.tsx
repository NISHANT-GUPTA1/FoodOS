import { SectionHeader } from '../components/SectionHeader'

export function TrackTwoScreen() {
  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Track 2"
        title="Ops stub screen"
        description="Placeholder for the second track. It uses the same shell and card language so the demo stays coherent while the main chain is built out."
      />

      <div className="grid gap-4 md:grid-cols-2">
        <div className="panel p-5">
          <div className="text-xs uppercase tracking-[0.28em] text-slate-400">Use case</div>
          <div className="mt-3 text-2xl font-semibold text-white">Retail ops and store execution</div>
          <p className="mt-2 text-sm text-slate-300">This slot stays ready for a second demo lane without changing the design system.</p>
        </div>
        <div className="panel p-5">
          <div className="text-xs uppercase tracking-[0.28em] text-slate-400">Status</div>
          <div className="mt-3 text-2xl font-semibold text-white">Stub</div>
          <p className="mt-2 text-sm text-slate-300">No separate engine yet. Same shell, separate route.</p>
        </div>
      </div>
    </div>
  )
}