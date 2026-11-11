import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';

// Pages
import { LandingPage } from './pages/LandingPage';
import { AuthPage } from './pages/AuthPage';
import { ResidentDashboard } from './pages/ResidentDashboard';
import { ReportIncidentPage } from './pages/ReportIncidentPage';
import { IncidentDetailPage } from './pages/IncidentDetailPage';
import { TrustedContactsPage } from './pages/TrustedContactsPage';
import { ChildSafetyPage } from './pages/ChildSafetyPage';
import { ElderCarePage } from './pages/ElderCarePage';
import { ResponderDashboard } from './pages/ResponderDashboard';
import { CommunitySafetyDashboard } from './pages/CommunitySafetyDashboard';
import { AdminDashboard } from './pages/AdminDashboard';

// Route Guard
const ProtectedRoute: React.FC<{ children: React.ReactNode; allowedRoles?: string[] }> = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center text-sm text-slate-500">
        Verifying authorization...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/auth?mode=login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

export const AppContent: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/auth" element={<AuthPage />} />

          {/* Resident & Common Routes */}
          <Route path="/dashboard" element={<ProtectedRoute><ResidentDashboard /></ProtectedRoute>} />
          <Route path="/sos" element={<ProtectedRoute><ResidentDashboard /></ProtectedRoute>} />
          <Route path="/report-incident" element={<ProtectedRoute><ReportIncidentPage /></ProtectedRoute>} />
          <Route path="/incidents/:id" element={<ProtectedRoute><IncidentDetailPage /></ProtectedRoute>} />
          <Route path="/contacts" element={<ProtectedRoute><TrustedContactsPage /></ProtectedRoute>} />
          <Route path="/child-safety" element={<ProtectedRoute><ChildSafetyPage /></ProtectedRoute>} />
          <Route path="/elder-care" element={<ProtectedRoute><ElderCarePage /></ProtectedRoute>} />

          {/* Responder Route */}
          <Route path="/responder" element={<ProtectedRoute allowedRoles={['responder', 'admin']}><ResponderDashboard /></ProtectedRoute>} />

          {/* Community Hazards & Map */}
          <Route path="/community" element={<CommunitySafetyDashboard />} />

          {/* Admin Route */}
          <Route path="/admin" element={<ProtectedRoute allowedRoles={['admin']}><AdminDashboard /></ProtectedRoute>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}
