import {
  ChartNoAxesCombined,
  ClipboardList,
  Clock3,
  LayoutDashboard,
  List,
  PackageSearch,
  QrCode,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  TimerReset,
  Wand2,
  type LucideIcon,
} from 'lucide-react'

export interface NavEntry {
  to: string
  label: string
  description: string
  icon: LucideIcon
  /** Highlight the parent when a child route is active (`/batches/T1024`). */
  matchPrefix?: string
}

export interface NavGroup {
  id: string
  label: string
  /** Collapsed groups render closed. The kitchen node is proof, not the pitch. */
  collapsed?: boolean
  items: NavEntry[]
}

/**
 * Nav restructure — Team Split v2 §5, H0-3.
 *
 * The four batch screens are primary. The seven existing kitchen screens collapse into
 * one "Kitchen node" group: they are the platform proof ("same engine, a different
 * node"), shown for about twenty seconds, and nobody rebuilds them.
 */
export const BATCH_NAV: NavGroup = {
  id: 'agri',
  label: 'Agri batch node',
  items: [
    {
      to: '/command',
      label: 'Command Center',
      description: 'Every live consignment, worst first',
      icon: LayoutDashboard,
    },
    {
      to: '/batches/new',
      label: 'Create Batch',
      description: 'Adaptive assessment in 30 seconds',
      icon: ClipboardList,
    },
    {
      to: '/batches/T1024',
      label: 'Batch Intelligence',
      description: 'RUL, loss band, drivers, plan matrix',
      icon: PackageSearch,
      matchPrefix: '/batches/',
    },
    {
      to: '/batches/T1024/simulate',
      label: 'What-If',
      description: 'Move a lever, watch the loss move',
      icon: SlidersHorizontal,
    },
    {
      to: '/batches/TOM-KLR-00001/passport',
      label: 'Batch Passport',
      description: 'Identity, custody chain and full event history',
      icon: QrCode,
    },
  ],
}

export const KITCHEN_NAV: NavGroup = {
  id: 'kitchen',
  label: 'Kitchen node',
  collapsed: true,
  items: [
    { to: '/today', label: 'Today', description: 'Service-day recommendations', icon: Clock3 },
    { to: '/why', label: 'Why', description: 'Attribution & NABCONS baseline', icon: ChartNoAxesCombined },
    { to: '/plan', label: 'Plan', description: 'Prep plan at a given λ', icon: TimerReset },
    { to: '/ledger', label: 'Ledger', description: 'Batch RSL & value at risk', icon: List },
    { to: '/rescue', label: 'Rescue', description: 'Cascading channel waterfall', icon: ShieldCheck },
    { to: '/impact', label: 'Impact', description: 'Backtest & forecast accuracy', icon: Wand2 },
    { to: '/settings', label: 'Settings', description: 'Tokens & demo knobs', icon: Settings },
  ],
}

export const NAV_GROUPS: NavGroup[] = [BATCH_NAV, KITCHEN_NAV]
