import { useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Leaf,
  Sparkles,
  Upload,
  X,
} from 'lucide-react'

interface CreateBatchModalProps {
  isOpen: boolean
  onClose: () => void
  onBatchCreated?: (batchData: any) => void
}

export function CreateBatchModal({ isOpen, onClose, onBatchCreated }: CreateBatchModalProps) {
  const [step, setStep] = useState(1)
  const [commodity, setCommodity] = useState('Tomato (Hybrid Red)')
  const [quantity, setQuantity] = useState(10000)
  const [harvestTime, setHarvestTime] = useState('Pre-dawn (06:00 AM)')
  const [sunlightExposure, setSunlightExposure] = useState('2–5 Hours')
  const [packaging, setPackaging] = useState('Ventilated Plastic Crates')
  const [transportType, setTransportType] = useState('Open Truck')
  const [uploadedPhotos] = useState<string[]>([
    'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=300&q=80',
    'https://images.unsplash.com/photo-1546470427-e26264be0b11?w=300&q=80',
    'https://images.unsplash.com/photo-1582284540020-8acbe03f4924?w=300&q=80',
  ])
  const [origin, setOrigin] = useState('Kolar Collection Hub (Karnataka)')
  const [destination, setDestination] = useState('Delhi APMC Mandi')
  const [isGenerating, setIsGenerating] = useState(false)

  if (!isOpen) return null

  const handleNextStep = () => {
    if (step < 5) {
      setStep(step + 1)
    } else {
      // Finalize batch creation
      setIsGenerating(true)
      setTimeout(() => {
        setIsGenerating(false)
        onBatchCreated?.({
          id: `Batch #T${Math.floor(1000 + Math.random() * 9000)}`,
          commodity,
          quantity,
          harvestTime,
          packaging,
          transportType,
          origin,
          destination,
        })
        onClose()
        setStep(1)
      }, 1200)
    }
  }

  const handlePrevStep = () => {
    if (step > 1) setStep(step - 1)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl rounded-3xl border-2 border-slate-300 bg-white/95 text-slate-900 shadow-2xl backdrop-blur-2xl overflow-hidden font-sans">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-900 px-8 py-5 text-white">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
              <Leaf className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-xl font-extrabold tracking-tight text-white flex items-center gap-2">
                Conversational Batch Intake Wizard
                <span className="rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-bold uppercase border border-emerald-500/30 px-2 py-0.5">
                  5-Step AI Fusion
                </span>
              </h2>
              <p className="text-xs text-slate-400">Step {step} of 5 — FoodOS Biological Intelligence Profile</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Step Progress Bar */}
        <div className="grid grid-cols-5 border-b border-slate-200 bg-slate-100 text-center text-xs font-bold">
          {[
            '1. Commodity',
            '2. Harvest Meta',
            '3. Handling',
            '4. Vision CV',
            '5. Telemetry',
          ].map((label, idx) => {
            const current = idx + 1
            return (
              <div
                key={label}
                className={`py-2.5 transition-colors ${
                  step === current
                    ? 'bg-emerald-600 text-white font-extrabold shadow-inner'
                    : step > current
                    ? 'bg-emerald-100 text-emerald-900'
                    : 'text-slate-500'
                }`}
              >
                {label}
              </div>
            )
          })}
        </div>

        {/* Modal Body Steps */}
        <div className="p-8 min-h-[360px]">
          {step === 1 && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div>
                <h3 className="text-xl font-bold text-slate-900">Step 1: Select Produce Commodity & Batch Size</h3>
                <p className="text-xs text-slate-600 mt-1">Loads Arrhenius kinetic decay curves and baseline biological parameters.</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {[
                  { name: 'Tomato (Hybrid Red)', note: 'NABCONS Baseline: 11.62% loss', icon: '🍅' },
                  { name: 'Guava (Pink Flesh)', note: 'NABCONS Baseline: 15.05% loss', icon: '🍐' },
                  { name: 'Potato (Jyoti)', note: 'NABCONS Baseline: 4.58% loss', icon: '🥔' },
                  { name: 'Cauliflower (Special)', note: 'NABCONS Baseline: 9.20% loss', icon: '🥦' },
                ].map((item) => (
                  <button
                    key={item.name}
                    onClick={() => setCommodity(item.name)}
                    className={`flex items-center gap-3 rounded-2xl border-2 p-4 text-left transition ${
                      commodity === item.name
                        ? 'border-emerald-600 bg-emerald-50 text-emerald-900 font-bold shadow-sm'
                        : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-800'
                    }`}
                  >
                    <span className="text-3xl">{item.icon}</span>
                    <div>
                      <div className="text-sm font-extrabold">{item.name}</div>
                      <div className="text-[11px] text-slate-500">{item.note}</div>
                    </div>
                  </button>
                ))}
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
                  Batch Quantity (Kilograms)
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min={1000}
                    max={25000}
                    step={500}
                    value={quantity}
                    onChange={(e) => setQuantity(Number(e.target.value))}
                    className="flex-1 accent-emerald-600"
                  />
                  <span className="rounded-xl border border-slate-300 bg-slate-100 px-4 py-2 text-lg font-extrabold text-slate-900">
                    {quantity.toLocaleString()} kg ({quantity / 1000} Tonnes)
                  </span>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div>
                <h3 className="text-xl font-bold text-slate-900">Step 2: Harvest Metadata & Thermal Context</h3>
                <p className="text-xs text-slate-600 mt-1">Human context captures post-harvest field heat and sun exposure.</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
                    Harvest Window & Time of Day
                  </label>
                  <div className="grid grid-cols-3 gap-3">
                    {['Pre-dawn (06:00 AM)', 'Midday Peak Heat (12:00 PM)', 'Late Afternoon (05:00 PM)'].map((t) => (
                      <button
                        key={t}
                        onClick={() => setHarvestTime(t)}
                        className={`rounded-xl border-2 p-3 text-xs font-bold transition ${
                          harvestTime === t
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-900'
                            : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
                    Direct Sunlight Exposure Post-Harvest
                  </label>
                  <div className="grid grid-cols-3 gap-3">
                    {['< 2 Hours', '2–5 Hours', '> 5 Hours (High Excursion)'].map((exp) => (
                      <button
                        key={exp}
                        onClick={() => setSunlightExposure(exp)}
                        className={`rounded-xl border-2 p-3 text-xs font-bold transition ${
                          sunlightExposure === exp
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-900'
                            : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        {exp}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div>
                <h3 className="text-xl font-bold text-slate-900">Step 3: Handling, Packaging & Transit Truck Specs</h3>
                <p className="text-xs text-slate-600 mt-1">Evaluates mechanical vibration penalty and thermal insulation factors.</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">Packaging Type</label>
                  <div className="grid grid-cols-3 gap-3">
                    {['Ventilated Plastic Crates', 'Wooden Crates', 'Gunny Bags (High Damage)'].map((p) => (
                      <button
                        key={p}
                        onClick={() => setPackaging(p)}
                        className={`rounded-xl border-2 p-3 text-xs font-bold transition ${
                          packaging === p
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-900'
                            : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">Transport Mode</label>
                  <div className="grid grid-cols-3 gap-3">
                    {['Open Truck', 'Tarpaulin Covered', 'Refrigerated Cold Truck'].map((tr) => (
                      <button
                        key={tr}
                        onClick={() => setTransportType(tr)}
                        className={`rounded-xl border-2 p-3 text-xs font-bold transition ${
                          transportType === tr
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-900'
                            : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        {tr}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div>
                <h3 className="text-xl font-bold text-slate-900">Step 4: Representative Computer Vision Analysis</h3>
                <p className="text-xs text-slate-600 mt-1">Upload 3–5 batch photos. Vision models extract maturity index & damage %.</p>
              </div>

              <div className="flex items-center gap-4">
                {uploadedPhotos.map((photo, i) => (
                  <div key={i} className="relative h-28 w-28 overflow-hidden rounded-2xl border-2 border-slate-300 shadow-md">
                    <img src={photo} alt="Produce batch sample" className="h-full w-full object-cover" />
                    <span className="absolute bottom-1 right-1 rounded-md bg-slate-900/80 px-1.5 py-0.5 text-[10px] font-bold text-emerald-400">
                      Sample #{i + 1}
                    </span>
                  </div>
                ))}

                <button className="flex h-28 w-28 flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-400 bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition">
                  <Upload className="h-6 w-6 text-emerald-600" />
                  <span className="mt-1 text-[11px] font-bold">Add Photo</span>
                </button>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-emerald-50/80 p-4 text-xs text-slate-800">
                <div className="font-bold text-emerald-900 flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-emerald-600" /> Automated Vision Diagnostic Output:
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 font-semibold">
                  <div>• Maturity Index: Turning Pink (72/100)</div>
                  <div>• Mechanical Abrasion: ≤ 3%</div>
                  <div>• Size Uniformity: High (Grade B+)</div>
                </div>
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div>
                <h3 className="text-xl font-bold text-slate-900">Step 5: Origin Hub & Destination Mandi Route Selection</h3>
                <p className="text-xs text-slate-600 mt-1">Ingests AGMARKNET modal prices & OpenAgri route weather forecasts.</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">Origin Collection Hub</label>
                  <select
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 bg-white p-3 text-xs font-bold text-slate-900 focus:ring-2 focus:ring-emerald-500"
                  >
                    <option>Kolar Collection Hub (Karnataka)</option>
                    <option>Nasik Agricultural Hub (Maharashtra)</option>
                    <option>Chittoor FPO Cluster (Andhra Pradesh)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">Primary Target Mandi</label>
                  <select
                    value={destination}
                    onChange={(e) => setDestination(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 bg-white p-3 text-xs font-bold text-slate-900 focus:ring-2 focus:ring-emerald-500"
                  >
                    <option>Delhi APMC Mandi (Azadpur)</option>
                    <option>Jaipur APMC Mandi</option>
                    <option>Bengaluru APMC Mandi (Yeshwanthpur)</option>
                  </select>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-300 bg-slate-100 p-4 text-xs font-medium text-slate-800">
                <div className="flex items-center justify-between font-bold text-slate-900">
                  <span>Batch Blueprint Ready: Batch #T1024</span>
                  <span className="text-emerald-700">4-Agent Optimization Enabled</span>
                </div>
                <p className="mt-1 text-slate-600">
                  {quantity} kg {commodity} from {origin} to {destination}. Weather pipeline ready.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-8 py-5">
          <button
            onClick={handlePrevStep}
            disabled={step === 1}
            className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold uppercase text-slate-700 hover:bg-slate-100 disabled:opacity-40 transition"
          >
            <ChevronLeft className="h-4 w-4" /> Back
          </button>

          <button
            onClick={handleNextStep}
            disabled={isGenerating}
            className="flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-2.5 text-xs font-bold uppercase text-white shadow-md hover:bg-emerald-700 active:scale-95 transition"
          >
            {isGenerating ? (
              <span>Running Multi-Agent Fusion...</span>
            ) : (
              <>
                <span>{step === 5 ? 'Generate Batch #T1024' : 'Next Step'}</span>
                <ChevronRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
