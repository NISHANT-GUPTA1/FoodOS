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
import DemoOne from '@/components/ui/demo'
import GradientDemo from '@/components/ui/gradient-demo'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<DemoOne />} />
      <Route path="/demo" element={<DemoOne />} />
      <Route path="/gradient-menu" element={<GradientDemo />} />
      <Route
        path="*"
        element={
          <AppShell>
            <Routes>
              <Route path="/" element={<Navigate to="/today" replace />} />
              <Route path="/today" element={<TodayScreen />} />
              <Route path="/why" element={<WhyScreen />} />
              <Route path="/plan" element={<PlanScreen />} />
              <Route path="/ledger" element={<LedgerScreen />} />
              <Route path="/rescue" element={<RescueScreen />} />
              <Route path="/impact" element={<ImpactScreen />} />
              <Route path="/settings" element={<SettingsScreen />} />
              <Route path="/track-2" element={<TrackTwoScreen />} />
              <Route path="/track-3" element={<TrackThreeScreen />} />
              <Route path="*" element={<Navigate to="/today" replace />} />
            </Routes>
          </AppShell>
        }
      />
    </Routes>
  )
}