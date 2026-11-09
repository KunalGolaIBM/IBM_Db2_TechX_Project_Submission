import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './auth/RequireAuth'
import { AppShell } from './components/AppShell'
import { ComplaintsView } from './views/ComplaintsView'
import { InvestigationDetailView } from './views/InvestigationDetailView'
import { InvestigationsView } from './views/InvestigationsView'
import { LoadingBlock } from './components/ui'
import { LoginView } from './views/LoginView'
import { NotFoundView } from './views/NotFoundView'
import { OverviewView } from './views/OverviewView'
import { ReviewView } from './views/ReviewView'
import { TransparencyView } from './views/TransparencyView'

// Leaflet is the largest dependency and only the map needs it, so the map view is its own chunk.
const GeoView = lazy(() => import('./views/GeoView').then((m) => ({ default: m.GeoView })))

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginView />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<OverviewView />} />
        <Route
          path="map"
          element={
            <Suspense fallback={<LoadingBlock label="Loading the map" className="min-h-96" />}>
              <GeoView />
            </Suspense>
          }
        />
        <Route path="complaints" element={<ComplaintsView />} />
        <Route path="investigations" element={<InvestigationsView />} />
        <Route path="investigations/:id" element={<InvestigationDetailView />} />
        <Route path="review" element={<ReviewView />} />
        <Route path="transparency" element={<TransparencyView />} />
        <Route path="overview" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundView />} />
      </Route>
    </Routes>
  )
}
