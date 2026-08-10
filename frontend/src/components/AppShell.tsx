import { useState, useEffect } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  Bell,
  Building2,
  Check,
  ChevronDown,
  CirclePlus,
  Eye,
  History,
  Leaf,
  LogIn,
  LogOut,
  Palette,
  Settings,
  ShieldCheck,
  User,
} from 'lucide-react'
import { NAV_GROUPS, type NavGroup } from '../config/nav'
import { SystemStatusModal } from './SystemStatusModal'

const natureBackgrounds = [
  'https://images.unsplash.com/photo-1448375240586-882707db888b?w=2160&q=80', // Soothing green forest canopy
  'https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=2160&q=80', // Organic green farm fields
  'https://images.unsplash.com/photo-1610832958506-aa56368176cf?w=2160&q=80', // Fresh green vegetables & fruits
  'https://images.unsplash.com/photo-1511497584788-876761c119ef?w=2160&q=80', // Sunlit green woodland grove
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const [isSystemStatusModalOpen, setIsSystemStatusModalOpen] = useState(false)
  const [isBellActive, setIsBellActive] = useState(false)
  const [activeOrg, setActiveOrg] = useState('Spice Garden Group (47 Kitchens)')
  const [activeTheme, setActiveTheme] = useState('dark')
  const [fontSize, setFontSize] = useState('normal')
  const [bgIndex, setBgIndex] = useState(0)

  // Faster background nature image rotation speed (rotates every 3.5 seconds)
  useEffect(() => {
    const interval = setInterval(() => {
      setBgIndex((prev) => (prev + 1) % natureBackgrounds.length)
    }, 3500)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="relative flex h-screen overflow-hidden bg-slate-100 text-slate-900 antialiased font-sans">
      {/* Soothing Nature, Forest & Fresh Produce Background Layer (Clearly Visible) */}
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
        {natureBackgrounds.map((bgUrl, idx) => (
          <div
            key={bgUrl}
            className={`absolute inset-0 bg-cover bg-center transition-all duration-1000 ease-in-out ${
              idx === bgIndex ? 'opacity-50 scale-100' : 'opacity-0 scale-105'
            }`}
            style={{ backgroundImage: `url(${bgUrl})` }}
          />
        ))}
        {/* Soft green ambient lighting overlay */}
        <div className="absolute inset-0 bg-gradient-to-tr from-emerald-950/20 via-transparent to-teal-950/10" />
      </div>

      <SystemStatusModal isOpen={isSystemStatusModalOpen} onClose={() => setIsSystemStatusModalOpen(false)} />

      {/* Left Sidebar Navigation (Transparent Glass + Rounded Rectangles) */}
      <nav className="relative z-10 hidden h-screen w-80 shrink-0 flex-col border-r-2 border-slate-300/80 bg-white/80 backdrop-blur-xl md:flex shadow-xl">
        <div className="border-b border-slate-300/80 px-6 py-7">
          <div className="mb-6 flex items-center gap-3.5">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-700 shadow-sm">
              <Leaf className="h-6 w-6 text-emerald-600" />
            </span>
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">FoodOS</h1>
              <p className="mt-0.5 text-xs font-semibold text-slate-600">Enterprise Intelligence</p>
            </div>
          </div>
          <button
            onClick={() => navigate('/batches/new')}
            className="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-900 bg-slate-900 px-4 py-3.5 text-xs font-bold uppercase tracking-wider text-white shadow-lg transition hover:bg-slate-800 hover:-translate-y-0.5 active:scale-95"
          >
            <CirclePlus className="h-4 w-4 text-emerald-400" />
            <span>Register Batch</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-6">
          <div className="flex flex-col gap-5">
            {NAV_GROUPS.map((group) => (
              <NavGroupSection key={group.id} group={group} />
            ))}
          </div>
        </div>

        <div className="border-t border-slate-300/80 px-3 py-4">
          <ul className="flex flex-col gap-1">
            <li>
              <a className="flex items-center gap-3 rounded-xl px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-700 transition hover:bg-slate-200/60 hover:text-slate-900" href="#">
                <ShieldCheck className="h-4 w-4 text-slate-500" />
                <span>Support</span>
              </a>
            </li>
            <li>
              <a className="flex items-center gap-3 rounded-xl px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-700 transition hover:bg-slate-200/60 hover:text-slate-900" href="#">
                <History className="h-4 w-4 text-slate-500" />
                <span>Archive</span>
              </a>
            </li>
          </ul>
        </div>
      </nav>

      {/* Main Content & Header (Transparent Glass + High Contrast Text) */}
      <div className="relative z-10 flex min-w-0 flex-1 flex-col bg-transparent">
        <header className="sticky top-0 z-30 flex h-20 shrink-0 items-center justify-between border-b-2 border-slate-300/80 bg-white/75 px-6 backdrop-blur-xl lg:px-12 shadow-sm">
          <div className="md:hidden">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">FoodOS</h1>
          </div>
          <div className="hidden flex-1 md:block" />
          <div className="flex items-center gap-5">
            {/* Interactive System Status Indicator */}
            <button
              onClick={() => setIsSystemStatusModalOpen(true)}
              className="flex items-center gap-2 rounded-2xl border border-slate-300 bg-white/80 px-3 py-1.5 transition hover:border-emerald-500/50 hover:bg-emerald-50 shadow-sm cursor-pointer"
            >
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-500" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700 hover:text-emerald-800">
                System Status
              </span>
            </button>

            {/* SIGN IN BUTTON RIGHT BESIDE SYSTEM STATUS */}
            <button
              onClick={() => navigate('/signin')}
              className="flex items-center gap-2 rounded-2xl border border-slate-900 bg-slate-900 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white shadow-md transition hover:bg-slate-800 hover:-translate-y-0.5 active:scale-95"
            >
              <LogIn className="h-4 w-4 text-emerald-400" />
              <span>Sign In</span>
            </button>

            <div className="h-6 w-px bg-slate-300" />

            {/* NOTIFICATIONS BELL ICON (TURNS GREEN ON PRESS) */}
            <button
              onClick={() => setIsBellActive(!isBellActive)}
              className={`p-2.5 rounded-2xl border transition-all duration-300 shadow-sm ${
                isBellActive
                  ? 'border-emerald-500 bg-emerald-100 text-emerald-600 ring-2 ring-emerald-400/40 shadow-emerald-500/20 animate-pulse'
                  : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100 hover:text-slate-900'
              }`}
              title={isBellActive ? 'Notifications Enabled (Green)' : 'Click to enable green notification status'}
              aria-label="Notifications"
            >
              <Bell className="h-5 w-5" />
            </button>

            <button className="p-2.5 rounded-2xl border border-slate-300 bg-white text-slate-700 transition hover:bg-slate-100 hover:text-slate-900 shadow-sm" aria-label="Security">
              <ShieldCheck className="h-5 w-5" />
            </button>

            {/* PROFILE AVATAR WITH HOVER POPDOWN SECTION */}
            <div
              className="relative"
              onMouseEnter={() => setIsProfileOpen(true)}
              onMouseLeave={() => setIsProfileOpen(false)}
            >
              <button
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="ml-1 flex h-10 w-10 overflow-hidden rounded-2xl border-2 border-slate-300 bg-slate-100 transition hover:border-slate-900 shadow-sm"
              >
                <img
                  alt="User Executive Profile"
                  className="h-full w-full object-cover"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuD46-9jZimZMlUEzk1lJVdgDhUSwHVR0lLT4nQHvr2sGfRJFlvKBW-rAfOh8Q0XM50mdokC6hjDj5zuKWKmwR4mJLN6CdumiuEOjZdn7-wOO8MI9xMawQosVy4oqduHK6NHZ0YRV3Gu4vO7kHPInYCHiPcW3UsB56ynE49Ff3KEAH_7nVZR7fjJ_c6ZXC6Y2vtKyD5orLaKKAi_PogRd910KJBDqHlgEz8MVg14loZVKRp_T_XhMalIKg"
                />
              </button>

              {/* Profile Hover Dropdown Card */}
              {isProfileOpen && (
                <div className="absolute right-0 top-11 z-50 w-80 rounded-3xl border border-slate-300 bg-slate-900 p-5 text-white shadow-2xl backdrop-blur-2xl animate-in fade-in duration-200">
                  {/* Section 1: Profile Status */}
                  <div className="flex items-center gap-3 border-b border-slate-800 pb-3.5">
                    <div className="relative h-11 w-11 shrink-0 overflow-hidden rounded-2xl border-2 border-emerald-500/70">
                      <img
                        alt="Profile Avatar"
                        className="h-full w-full object-cover"
                        src="https://lh3.googleusercontent.com/aida-public/AB6AXuD46-9jZimZMlUEzk1lJVdgDhUSwHVR0lLT4nQHvr2sGfRJFlvKBW-rAfOh8Q0XM50mdokC6hjDj5zuKWKmwR4mJLN6CdumiuEOjZdn7-wOO8MI9xMawQosVy4oqduHK6NHZ0YRV3Gu4vO7kHPInYCHiPcW3UsB56ynE49Ff3KEAH_7nVZR7fjJ_c6ZXC6Y2vtKyD5orLaKKAi_PogRd910KJBDqHlgEz8MVg14loZVKRp_T_XhMalIKg"
                      />
                      <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-slate-900 bg-emerald-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between">
                        <h4 className="truncate text-sm font-bold text-white">Executive Admin</h4>
                        <span className="rounded-full border border-emerald-500/30 bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-400">
                          Active
                        </span>
                      </div>
                      <p className="truncate text-xs text-slate-400">admin@foodos.ai</p>
                      <p className="mt-1 flex items-center gap-1 text-[11px] font-medium text-emerald-400">
                        <User className="h-3 w-3" /> Shift 1 • Cluster Zone B
                      </p>
                    </div>
                  </div>

                  {/* Section 2: Organisations */}
                  <div className="border-b border-slate-800 py-3">
                    <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-400">
                      <span className="flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5 text-sky-400" /> Organisations
                      </span>
                      <span className="text-[10px] text-slate-500">3 Available</span>
                    </div>
                    <div className="space-y-1.5">
                      {['Spice Garden Group (47 Kitchens)', 'Store Cluster 12 (North)', 'Central Logistics Hub B'].map((org) => (
                        <button
                          key={org}
                          onClick={() => setActiveOrg(org)}
                          className={`flex w-full items-center justify-between rounded-xl px-2.5 py-1.5 text-left text-xs transition ${
                            activeOrg === org
                              ? 'border border-slate-700 bg-slate-800 font-semibold text-emerald-400'
                              : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                          }`}
                        >
                          <span className="truncate">{org}</span>
                          {activeOrg === org && <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Section 3: Appearance */}
                  <div className="border-b border-slate-800 py-3">
                    <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-400">
                      <span className="flex items-center gap-1.5">
                        <Palette className="h-3.5 w-3.5 text-purple-400" /> Appearance
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        { id: 'dark', label: 'Dark' },
                        { id: 'light', label: 'Light' },
                        { id: 'contrast', label: 'High Contrast' },
                      ].map((theme) => (
                        <button
                          key={theme.id}
                          onClick={() => setActiveTheme(theme.id)}
                          className={`rounded-xl border py-1 text-center text-[11px] font-semibold transition ${
                            activeTheme === theme.id
                              ? 'border-emerald-500/60 bg-emerald-500/20 text-emerald-300'
                              : 'border-slate-800 bg-slate-800/50 text-slate-400 hover:text-white'
                          }`}
                        >
                          {theme.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Section 4: Accessibility */}
                  <div className="border-b border-slate-800 py-3">
                    <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-400">
                      <span className="flex items-center gap-1.5">
                        <Eye className="h-3.5 w-3.5 text-amber-400" /> Accessibility
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-300">
                      <span>Font Size Scale</span>
                      <div className="flex gap-1">
                        {['normal', 'large', 'xlarge'].map((size) => (
                          <button
                            key={size}
                            onClick={() => setFontSize(size)}
                            className={`rounded-lg border px-2 py-0.5 text-[10px] font-bold uppercase transition ${
                              fontSize === size
                                ? 'border-amber-500/40 bg-amber-500/20 text-amber-300'
                                : 'border-slate-800 text-slate-400 hover:text-white'
                            }`}
                          >
                            {size === 'normal' ? '100%' : size === 'large' ? '120%' : '140%'}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Section 5: Settings Icon & Navigation Link */}
                  <div className="flex items-center justify-between pt-3">
                    <NavLink
                      to="/settings"
                      className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-slate-500 hover:bg-slate-700 hover:text-white"
                    >
                      <Settings className="h-4 w-4 text-emerald-400" />
                      <span>Settings</span>
                    </NavLink>
                    <button
                      onClick={() => navigate('/signin')}
                      className="flex items-center gap-1.5 text-xs text-rose-400 transition hover:text-rose-300"
                    >
                      <LogOut className="h-3.5 w-3.5" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto p-4 pb-28 sm:p-6 md:pb-32 lg:p-12">{children}</main>

        <MobileTabBar />
      </div>
    </div>
  )
}

/**
 * One collapsible group per node. The kitchen group starts closed — it is the platform
 * proof, not the pitch, and it should not compete with the four batch screens for the
 * first thing a judge's eye lands on.
 */
function NavGroupSection({ group }: { group: NavGroup }) {
  const location = useLocation()
  const containsActive = group.items.some(
    (item) => location.pathname === item.to || (item.matchPrefix && location.pathname.startsWith(item.matchPrefix)),
  )
  const [open, setOpen] = useState(!group.collapsed || containsActive)

  useEffect(() => {
    if (containsActive) setOpen(true)
  }, [containsActive])

  return (
    <section>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between rounded-xl px-4 py-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500 transition hover:bg-slate-200/50 hover:text-slate-800"
      >
        <span>{group.label}</span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? '' : '-rotate-90'}`} />
      </button>

      {open ? (
        <ul className="mt-2 flex flex-col gap-1.5">
          {group.items.map((item) => {
            const Icon = item.icon

            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) => {
                    const active =
                      isActive || (item.matchPrefix ? location.pathname.startsWith(item.matchPrefix) : false)
                    return `flex items-center gap-3.5 rounded-2xl px-4 py-3 transition-all duration-200 ${
                      active
                        ? 'border border-emerald-500/40 bg-emerald-500/15 font-extrabold text-slate-900 shadow-sm'
                        : 'font-semibold text-slate-700 hover:bg-slate-200/60 hover:text-slate-900'
                    }`
                  }}
                >
                  <span className="text-emerald-700">
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-bold tracking-wide">{item.label}</span>
                    <span className="block truncate text-xs font-normal text-slate-500">{item.description}</span>
                  </span>
                </NavLink>
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}

/**
 * Mobile navigation. The FPO user is on a phone and a judge will ask — the sidebar is
 * desktop-only, so the four batch screens get a bottom tab bar under `md`.
 */
function MobileTabBar() {
  const location = useLocation()

  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 border-t-2 border-slate-300/80 bg-white/95 backdrop-blur-xl md:hidden">
      <ul className="flex items-stretch">
        {NAV_GROUPS[0].items.map((item) => {
          const Icon = item.icon
          const active =
            location.pathname === item.to || (item.matchPrefix ? location.pathname.startsWith(item.matchPrefix) : false)

          return (
            <li key={item.to} className="flex-1">
              <NavLink
                to={item.to}
                className={`flex flex-col items-center gap-1 px-1 py-2.5 text-center transition ${
                  active ? 'text-emerald-700' : 'text-slate-500'
                }`}
              >
                <Icon className="h-5 w-5" />
                <span className="text-[10px] font-bold leading-tight">{item.label.split(' ')[0]}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}