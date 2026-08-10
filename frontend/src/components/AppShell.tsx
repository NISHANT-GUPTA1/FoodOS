import { NavLink } from 'react-router-dom'
import { Bell, ChartNoAxesCombined, CirclePlus, Clock3, History, Leaf, List, PackageSearch, ShieldCheck, TimerReset, Wand2 } from 'lucide-react'
import { navItems } from '../mocks/dashboard'

const icons = [Clock3, ChartNoAxesCombined, TimerReset, List, PackageSearch, ShieldCheck, Wand2]

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#fcf8f8] text-[#1c1b1b] antialiased">
      <nav className="hidden h-screen w-80 shrink-0 flex-col border-r-2 border-[#c4c7c8] bg-[#ffffff] md:flex">
        <div className="border-b border-[#c4c7c8] px-6 py-8">
          <div className="mb-6 flex items-center gap-4">
            <span className="flex h-10 w-10 items-center justify-center rounded bg-[#e5e2e1] text-[#1c1b1b]">
              <Leaf className="h-5 w-5" />
            </span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tighter text-[#1c1b1b]">FoodOS</h1>
              <p className="mt-1 text-sm text-[#444748]">Enterprise Intelligence</p>
            </div>
          </div>
          <button className="flex w-full items-center justify-center gap-2 rounded border border-[#1c1b1b] bg-[#f8fafc] px-4 py-3 font-semibold text-[#0f172a] transition hover:-translate-x-1 hover:-translate-y-1 hover:shadow-[4px_4px_0px_0px_#0ea5e9]">
            <CirclePlus className="h-4 w-4" />
            New Analysis
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-0 py-6">
          <ul className="flex flex-col gap-2">
            {navItems.map((item, index) => {
              const Icon = icons[index] ?? Clock3

              return (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      `flex items-center gap-4 border-l-4 px-6 py-4 transition-all duration-150 ${
                        isActive
                          ? 'border-[#c6c6c7] bg-[#e2e2e2] text-[#1a1c1c]'
                          : 'border-transparent text-[#444748] hover:bg-[#ebe7e7] hover:text-[#1c1b1b]'
                      }`
                    }
                  >
                    <span className="text-[#5d5f5f]">
                      <Icon className="h-5 w-5" />
                    </span>
                    <span className="flex-1">
                      <span className="block text-sm font-bold uppercase tracking-wide">{item.label}</span>
                      <span className="block text-xs text-[#646464]">{item.description}</span>
                    </span>
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </div>

        <div className="border-t border-[#c4c7c8] px-2 py-4">
          <ul className="flex flex-col gap-1">
            <li>
              <a className="flex items-center gap-3 rounded border-l-4 border-transparent px-4 py-3 text-[#444748] transition-all duration-150 hover:bg-[#ebe7e7] hover:text-[#1c1b1b]" href="#">
                <ShieldCheck className="h-4 w-4" />
                <span className="text-sm uppercase tracking-wide">Support</span>
              </a>
            </li>
            <li>
              <a className="flex items-center gap-3 rounded border-l-4 border-transparent px-4 py-3 text-[#444748] transition-all duration-150 hover:bg-[#ebe7e7] hover:text-[#1c1b1b]" href="#">
                <History className="h-4 w-4" />
                <span className="text-sm uppercase tracking-wide">Archive</span>
              </a>
            </li>
          </ul>
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col bg-[#fcf8f8]">
        <header className="sticky top-0 z-30 flex h-20 shrink-0 items-center justify-between border-b-2 border-[#c4c7c8] bg-[#fcf8f8]/80 px-6 backdrop-blur-md lg:px-12">
          <div className="md:hidden">
            <h1 className="text-2xl font-semibold tracking-tighter text-[#1c1b1b]">FoodOS</h1>
          </div>
          <div className="hidden flex-1 md:block" />
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
              <span className="text-sm uppercase tracking-[0.14em] text-[#444748]">System Status</span>
            </div>
            <div className="h-6 w-px bg-[#c4c7c8]" />
            <button className="text-[#444748] transition-colors duration-200 hover:text-[#5d5f5f]">
              <Bell className="h-5 w-5" />
            </button>
            <button className="text-[#444748] transition-colors duration-200 hover:text-[#5d5f5f]">
              <ShieldCheck className="h-5 w-5" />
            </button>
            <button className="ml-2 h-10 w-10 overflow-hidden rounded-full border border-[#c4c7c8] bg-[#e5e2e1]">
              <img alt="User Executive Profile" className="h-full w-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuD46-9jZimZMlUEzk1lJVdgDhUSwHVR0lLT4nQHvr2sGfRJFlvKBW-rAfOh8Q0XM50mdokC6hjDj5zuKWKmwR4mJLN6CdumiuEOjZdn7-wOO8MI9xMawQosVy4oqduHK6NHZ0YRV3Gu4vO7kHPInYCHiPcW3UsB56ynE49Ff3KEAH_7nVZR7fjJ_c6ZXC6Y2vtKyD5orLaKKAi_PogRd910KJBDqHlgEz8MVg14loZVKRp_T_XhMalIKg" />
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto p-6 pb-32 lg:p-12">{children}</main>
      </div>
    </div>
  )
}