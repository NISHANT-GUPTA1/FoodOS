import { SectionHeader } from '../components/SectionHeader'

export function TrackThreeScreen() {
  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Track 3"
        title="Expansion stub screen"
        description="Placeholder for the third track. Keep it lightweight so the production demo path remains focused on the core chain."
      />

      <div className="panel p-5">
        <div className="text-xs uppercase tracking-[0.28em] text-slate-400">Future lane</div>
        <div className="mt-3 text-2xl font-semibold text-white">Cluster expansion and partner onboarding</div>
        <p className="mt-2 text-sm text-slate-300">This route is reserved for a later story without forcing a redesign of the navigation or shell.</p>
      </div>
    </div>
  )
}