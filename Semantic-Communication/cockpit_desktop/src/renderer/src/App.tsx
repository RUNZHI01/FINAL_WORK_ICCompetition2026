import { HashRouter, Route, Routes } from 'react-router-dom'
import { MissionShell } from './layouts/MissionShell'
import { DashboardPageMinimal } from './pages/DashboardPageMinimal'
import { ControlConsolePage } from './pages/ControlConsolePage'
import { ErrorBoundary } from './components/ErrorBoundary'

export default function App() {
  return (
    <ErrorBoundary>
      <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<MissionShell />}>
            <Route index element={<DashboardPageMinimal />} />
            <Route path="console" element={<ControlConsolePage />} />
          </Route>
        </Routes>
      </HashRouter>
    </ErrorBoundary>
  )
}
