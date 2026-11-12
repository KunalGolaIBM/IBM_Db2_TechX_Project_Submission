import { Loader2 } from 'lucide-react';
import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Shell } from '@/components/Shell';
import { Button } from '@/components/ui';
import { AuthProvider, useAuth } from '@/lib/auth';
import type { Role } from '@/lib/api';
import Login from '@/pages/Login';
import Overview from '@/pages/Overview';

const Scan = lazy(() => import('@/pages/Scan'));
const Assessments = lazy(() => import('@/pages/Assessments'));
const AssessmentDetail = lazy(() => import('@/pages/AssessmentDetail'));
const Compare = lazy(() => import('@/pages/Compare'));
const Policies = lazy(() => import('@/pages/Policies'));
const Admin = lazy(() => import('@/pages/Admin'));

function Loading() {
  return <div className="grid h-64 place-items-center text-muted"><Loader2 className="size-5 animate-spin" /></div>;
}

function Guard({ role, children }: { role: Role; children: ReactNode }) {
  const { can } = useAuth();
  return can(role) ? <>{children}</> : <Navigate to="/" replace />;
}

function NotFound() {
  return (
    <div className="py-24 text-center">
      <div className="mono text-sm text-brand-400">404</div>
      <h1 className="mt-2 text-2xl font-semibold">This page doesn't exist</h1>
      <Link to="/"><Button className="mt-6">Back to overview</Button></Link>
    </div>
  );
}

function Routed() {
  const { me, checking } = useAuth();
  if (checking) return <div className="grid h-screen place-items-center"><Loader2 className="size-6 animate-spin text-brand-400" /></div>;
  if (!me) return <Login />;
  return (
    <Shell>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/scan" element={<Guard role="operator"><Scan /></Guard>} />
          <Route path="/assessments" element={<Assessments />} />
          <Route path="/assessments/:id" element={<AssessmentDetail />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/policies" element={<Policies />} />
          <Route path="/admin" element={<Guard role="admin"><Admin /></Guard>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </Shell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routed />
        <Toaster theme="dark" position="bottom-right" toastOptions={{ style: { background: '#0a1020', border: '1px solid rgba(255,255,255,0.1)' } }} />
      </AuthProvider>
    </BrowserRouter>
  );
}
