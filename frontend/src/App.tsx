import { Navigate, Route, Routes } from 'react-router-dom'
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
import { CommandCenterScreen } from './screens/batch/CommandCenterScreen'
import { CreateBatchScreen } from './screens/batch/CreateBatchScreen'
import { WhatIfScreen } from './screens/batch/WhatIfScreen'
import SignInPageDemo from '@/components/ui/sign-in-demo'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<SignInPageDemo />} />
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