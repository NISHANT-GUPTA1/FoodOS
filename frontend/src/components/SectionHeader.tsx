interface SectionHeaderProps {
  eyebrow: string
  title: string
  description: string
  action?: React.ReactNode
}

export function SectionHeader({ eyebrow, title, description, action }: SectionHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl space-y-3">
        <span className="chip border border-[#c4c7c8] bg-[#f1edec] text-[#444748]">{eyebrow}</span>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-[#1c1b1b] md:text-5xl">{title}</h1>
          <p className="max-w-2xl text-sm leading-7 text-[#444748] md:text-base">{description}</p>
        </div>
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  )
}