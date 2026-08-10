import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Leaf, ArrowRight, Lock, Mail } from 'lucide-react'

export function SignInScreen() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setTimeout(() => {
      setIsLoading(false)
      navigate('/today')
    }, 800)
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white flex items-center justify-center p-4 relative overflow-hidden font-sans">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-emerald-500/10 blur-[140px] rounded-full pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-[400px] h-[400px] bg-sky-500/10 blur-[120px] rounded-full pointer-events-none" />

      {/* Main Sign In Modal Container */}
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/90 p-8 shadow-2xl backdrop-blur-xl">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/20 text-emerald-400 shadow-inner mb-4">
            <Leaf className="h-7 w-7" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white">FoodOS Enterprise</h1>
          <p className="text-sm text-slate-400 mt-1">Sign in to access your Decision Intelligence Portal</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Work Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                required
                className="w-full rounded-xl border border-slate-700 bg-slate-800/80 pl-10 pr-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Password
              </label>
              <a href="#" className="text-xs text-emerald-400 hover:underline">
                Forgot password?
              </a>
            </div>
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                className="w-full rounded-xl border border-slate-700 bg-slate-800/80 pl-10 pr-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 rounded-xl border border-emerald-500/60 bg-emerald-500/20 py-3.5 font-semibold text-emerald-300 shadow-lg transition hover:bg-emerald-500/30 hover:border-emerald-400 hover:text-white disabled:opacity-50"
          >
            {isLoading ? (
              <span>Authenticating...</span>
            ) : (
              <>
                <span>Sign In to FoodOS</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        <div className="relative my-6 flex items-center justify-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-800" />
          </div>
          <span className="relative bg-slate-900 px-3 text-xs uppercase text-slate-500 font-semibold tracking-wider">
            Or SSO Sign In
          </span>
        </div>

        {/* SSO Options */}
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => navigate('/today')}
            className="flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800/60 py-2.5 text-xs font-semibold text-slate-300 transition hover:bg-slate-700 hover:text-white"
          >
            <span>Google Workspace</span>
          </button>
          <button
            onClick={() => navigate('/today')}
            className="flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800/60 py-2.5 text-xs font-semibold text-slate-300 transition hover:bg-slate-700 hover:text-white"
          >
            <span>Okta Enterprise</span>
          </button>
        </div>

        {/* Footer info */}
        <div className="mt-8 pt-6 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-1.5 text-emerald-400">
            <ShieldCheck className="h-4 w-4" />
            <span>SOC2 Type II Certified</span>
          </div>
          <button onClick={() => navigate('/today')} className="hover:text-slate-300 transition">
            Guest Mode →
          </button>
        </div>
      </div>
    </div>
  )
}
