import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { Spinner } from './components/ui/Feedback'

const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const Compare = lazy(() => import('./pages/Compare').then((m) => ({ default: m.Compare })))
const RunExperiment = lazy(() => import('./pages/RunExperiment').then((m) => ({ default: m.RunExperiment })))
const SingleRun = lazy(() => import('./pages/SingleRun').then((m) => ({ default: m.SingleRun })))
const Explore = lazy(() => import('./pages/Explore').then((m) => ({ default: m.Explore })))

export default function App() {
  return (
    <AppShell>
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/run" element={<RunExperiment />} />
          <Route path="/single-run" element={<SingleRun />} />
          <Route path="/explore" element={<Explore />} />
        </Routes>
      </Suspense>
    </AppShell>
  )
}
