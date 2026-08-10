import { SectionHeader } from '../components/SectionHeader'

const settings = [
  { label: 'PREVENT token', value: '#4ade80', note: 'Forecast and prep surfaces' },
  { label: 'PRESERVE token', value: '#f59e0b', note: 'Shelf life and markdown surfaces' },
  { label: 'RECOVER token', value: '#fb7185', note: 'Recovery and rescue surfaces' },
]

export function SettingsScreen() {
  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Settings"
        title="Design tokens and demo knobs"
        description="This page is intentionally spare for now. It gives the shell a home for colours, theme values, and later contract flags."
      />

      <div className="grid gap-4 md:grid-cols-3">
        {settings.map((setting) => (
          <div key={setting.label} className="panel p-5">
            <div className="text-xs uppercase tracking-[0.28em] text-[#646464]">{setting.label}</div>
            <div className="mt-3 text-2xl font-semibold text-[#1c1b1b]">{setting.value}</div>
            <p className="mt-2 text-sm text-[#444748]">{setting.note}</p>
          </div>
        ))}
      </div>
    </div>
  )
}