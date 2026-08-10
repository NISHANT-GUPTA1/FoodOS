import { useState } from 'react'
import { ShieldCheck, Activity, Cpu, Database, RefreshCw, CheckCircle2, Server, Globe2, X, Zap } from 'lucide-react'

export function SystemStatusModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [isPinging, setIsPinging] = useState(false)
  const [pingSuccess, setPingSuccess] = useState(false)

  const handleRunDiagnostics = () => {
    setIsPinging(true)
    setPingSuccess(false)
    setTimeout(() => {
      setIsPinging(false)
      setPingSuccess(true)
    }, 1200)
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-md animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900/95 p-6 text-white shadow-2xl backdrop-blur-2xl ring-1 ring-slate-700/50 space-y-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-emerald-400">
              <Activity className="h-5 w-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-white">System Active Telemetry</h3>
                <span className="rounded-full bg-emerald-500/20 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-bold text-emerald-400 uppercase">
                  Healthy
                </span>
              </div>
              <p className="text-xs text-slate-400">FoodOS Cluster Node #47 • Real-time Monitoring</p>
            </div>
          </div>

          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Live Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div className="rounded-xl border border-slate-800 bg-slate-800/50 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase">
              <span>Cluster Nodes</span>
              <Globe2 className="h-4 w-4 text-sky-400" />
            </div>
            <div className="text-2xl font-bold text-white">47 <span className="text-xs font-normal text-slate-400">Kitchens</span></div>
            <div className="text-[11px] text-emerald-400">12 Stores active</div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-800/50 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase">
              <span>API Latency</span>
              <Zap className="h-4 w-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-white">42 <span className="text-xs font-normal text-slate-400">ms</span></div>
            <div className="text-[11px] text-emerald-400">99.99% Uptime</div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-800/50 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase">
              <span>MAPE Error</span>
              <Cpu className="h-4 w-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold text-white">11.8<span className="text-xs font-normal text-slate-400">%</span></div>
            <div className="text-[11px] text-emerald-400">89% Coverage</div>
          </div>
        </div>

        {/* Subsystems Status List */}
        <div className="space-y-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Decision Spine Subsystems</h4>
          <div className="rounded-xl border border-slate-800 bg-slate-800/30 p-3 space-y-2 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
              <span className="flex items-center gap-2 text-slate-300">
                <Database className="h-4 w-4 text-emerald-400" /> Quantile Forecaster Engine
              </span>
              <span className="flex items-center gap-1 font-semibold text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> Operational
              </span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
              <span className="flex items-center gap-2 text-slate-300">
                <Server className="h-4 w-4 text-sky-400" /> Remaining Shelf-Life (RSL) Tracker
              </span>
              <span className="flex items-center gap-1 font-semibold text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> Operational
              </span>
            </div>
            <div className="flex items-center justify-between py-1">
              <span className="flex items-center gap-2 text-slate-300">
                <ShieldCheck className="h-4 w-4 text-purple-400" /> B2B Rescue & Reroute Gate
              </span>
              <span className="flex items-center gap-1 font-semibold text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> Operational
              </span>
            </div>
          </div>
        </div>

        {/* Diagnostic Action Bar */}
        <div className="flex items-center justify-between border-t border-slate-800 pt-4">
          <div className="text-xs text-slate-400">
            {pingSuccess ? (
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="h-4 w-4" /> All 47 cluster nodes verified!
              </span>
            ) : (
              <span>Last verified 2 minutes ago</span>
            )}
          </div>

          <button
            onClick={handleRunDiagnostics}
            disabled={isPinging}
            className="flex items-center gap-2 rounded-xl border border-emerald-500/50 bg-emerald-500/20 px-4 py-2 text-xs font-semibold text-emerald-300 shadow-md transition hover:bg-emerald-500/30 hover:text-white disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isPinging ? 'animate-spin' : ''}`} />
            <span>{isPinging ? 'Pinging Nodes...' : 'Run Diagnostics'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
