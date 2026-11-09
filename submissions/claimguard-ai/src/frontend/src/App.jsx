import React, { useState, useEffect } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import SubmitClaim from './pages/SubmitClaim';
import ClaimsManagement from './pages/ClaimsManagement';
import ClaimDetails from './pages/ClaimDetails';
import FraudDetection from './pages/FraudDetection';
import AIReports from './pages/AIReports';
import PolicyManagement from './pages/PolicyManagement';
import AuditLogs from './pages/AuditLogs';
import Settings from './pages/Settings';
import { apiClient } from './api/client';

export default function App() {
  const [dbHealth, setDbHealth] = useState(null);
  const location = useLocation();
  const isLoginPage = location.pathname === '/login';

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await apiClient.getHealth();
        setDbHealth(res.data?.database);
      } catch (err) {
        console.warn('Could not retrieve database health status:', err);
      }
    }
    checkHealth();
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-[#F4F4F4] text-[#161616]">
      <Navbar dbHealth={dbHealth} />

      <div className="flex flex-1 overflow-hidden">
        {!isLoginPage && <Sidebar />}

        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Routes>
            <Route path="/" element={<Dashboard dbHealth={dbHealth} />} />
            <Route path="/login" element={<Login />} />
            <Route path="/submit-claim" element={<SubmitClaim />} />
            <Route path="/claims" element={<ClaimsManagement />} />
            <Route path="/claims/:claimId" element={<ClaimDetails />} />
            <Route path="/fraud-detection" element={<FraudDetection />} />
            <Route path="/reports" element={<AIReports />} />
            <Route path="/policies" element={<PolicyManagement />} />
            <Route path="/audit-logs" element={<AuditLogs />} />
            <Route path="/settings" element={<Settings dbHealth={dbHealth} />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
