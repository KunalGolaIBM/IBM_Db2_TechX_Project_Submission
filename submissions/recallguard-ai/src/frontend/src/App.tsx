import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "@/layouts/AppLayout";
import { DemoProvider } from "@/hooks/useDemo";
import { LoadingState } from "@/components/ui";
import DashboardPage from "@/pages/DashboardPage";

const IncidentsPage = lazy(() => import("@/pages/IncidentsPage"));
const IncidentDetailPage = lazy(() => import("@/pages/IncidentDetailPage"));
const ExplorerPage = lazy(() => import("@/pages/ExplorerPage"));
const InvestigationPage = lazy(() => import("@/pages/InvestigationPage"));
const RecallsPage = lazy(() => import("@/pages/RecallsPage"));
const RecallDetailPage = lazy(() => import("@/pages/RecallDetailPage"));
const EvidencePage = lazy(() => import("@/pages/EvidencePage"));
const MonitoringPage = lazy(() => import("@/pages/MonitoringPage"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));

export function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, refetchOnWindowFocus: false, retry: 1 } } });
}

export function AppRoutes() {
  return (
    <Suspense fallback={<LoadingState rows={5} />}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="incidents" element={<IncidentsPage />} />
          <Route path="incidents/:id" element={<IncidentDetailPage />} />
          <Route path="explorer" element={<ExplorerPage />} />
          <Route path="investigations" element={<InvestigationPage />} />
          <Route path="investigations/:id" element={<InvestigationPage />} />
          <Route path="recalls" element={<RecallsPage />} />
          <Route path="recalls/:id" element={<RecallDetailPage />} />
          <Route path="evidence" element={<EvidencePage />} />
          <Route path="monitoring" element={<MonitoringPage />} />
          <Route path="monitoring/:id" element={<MonitoringPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<p className="p-8 text-slate-400">Page not found.</p>} />
        </Route>
      </Routes>
    </Suspense>
  );
}

const client = makeQueryClient();

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <DemoProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </DemoProvider>
    </QueryClientProvider>
  );
}
