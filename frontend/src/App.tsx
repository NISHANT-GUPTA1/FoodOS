import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ImpactScreen } from './screens/ImpactScreen'
import { LedgerScreen } from './screens/LedgerScreen'
import { PlanScreen } from './screens/PlanScreen'
import { RescueScreen } from './screens/RescueScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { TrackThreeScreen } from './screens/TrackThreeScreen'
import { TrackTwoScreen } from './screens/TrackTwoScreen'
import { TodayScreen } from './screens/TodayScreen'
import { WhyScreen } from './screens/WhyScreen'
import { BatchIntelligenceScreen } from './screens/batch/BatchIntelligenceScreen'
import { BatchPassportScreen } from './screens/batch/BatchPassportScreen'
import { CommandCenterScreen } from './screens/batch/CommandCenterScreen'
import { CreateBatchScreen } from './screens/batch/CreateBatchScreen'
import { WhatIfScreen } from './screens/batch/WhatIfScreen'
import SignInPageDemo from '@/components/ui/sign-in-demo'

/**
 * A scanned QR lands on `/batch/<code>` — the public URL the backend bakes
 * into the image — and this forwards it to the passport screen.
 *
 * `<Navigate to="/batches/:id/passport">` would not work: `to` takes a plain
 * string, not a path pattern, so `:id` would be sent through literally.
 */
function ScannedBatch() {
  const { id = '' } = useParams()
  return <Navigate to={`/batches/${id}/passport`} replace />
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<SignInPageDemo />} />
      {/* The URL printed on the crate label. Kept outside the app shell so a
          scan resolves before any nav chrome loads. */}
      <Route path="/batch/:id" element={<ScannedBatch />} />
      <Route path="/signin" element={<SignInPageDemo />} />
      {/* /login and /demo pointed at a copied template that still read
          "you agree to creating a Vercel account", carried six buttons with no
          handlers, and pulled three.js from a CDN. They now reach the real
          sign-in, which is already the root route. */}
      <Route path="/login" element={<SignInPageDemo />} />
      <Route path="/demo" element={<SignInPageDemo />} />
      <Route
        path="*"
        element={
          <AppShell>
            <Routes>
              {/* Agri batch node — the four primary screens. */}
              <Route path="/command" element={<CommandCenterScreen />} />
              <Route path="/batches/new" element={<CreateBatchScreen />} />
              <Route path="/batches/:id/simulate" element={<WhatIfScreen />} />
              <Route path="/batches/:id/passport" element={<BatchPassportScreen />} />
              <Route path="/batches/:id" element={<BatchIntelligenceScreen />} />

              {/* Kitchen node — the platform proof. Unchanged. */}
              <Route path="/today" element={<TodayScreen />} />
              <Route path="/why" element={<WhyScreen />} />
              <Route path="/plan" element={<PlanScreen />} />
              <Route path="/ledger" element={<LedgerScreen />} />
              <Route path="/rescue" element={<RescueScreen />} />
              <Route path="/impact" element={<ImpactScreen />} />
              <Route path="/settings" element={<SettingsScreen />} />
              <Route path="/track-2" element={<TrackTwoScreen />} />
              <Route path="/track-3" element={<TrackThreeScreen />} />
              <Route path="*" element={<Navigate to="/command" replace />} />
            </Routes>
          </AppShell>
        }
      />
    </Routes>
  )
}