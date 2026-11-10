import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './pages/Dashboard';
import { Events } from './pages/Events';
import { Alerts } from './pages/Alerts';
import { Incidents } from './pages/Incidents';
import { Investigation } from './pages/Investigation';
import { Approvals } from './pages/Approvals';
import { Settings } from './pages/Settings';
import { SentinelApi } from './services/api';

export const App: React.FC = () => {
  const [db2Connected, setDb2Connected] = useState<boolean>(true);
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  const checkStatus = async () => {
    try {
      const stat = await SentinelApi.getHealth();
      setDb2Connected(stat?.status === 'healthy' || stat?.status === 'degraded');
      setIsDemoMode(stat?.database_mode?.includes('Demo') || stat?.database_mode?.includes('Local'));
    } catch (err) {
      console.warn('Backend connection check warning:', err);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
    checkStatus();
  };

  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-[#070D18] text-slate-100 font-sans antialiased selection:bg-cyan-500 selection:text-white">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <Header
            db2Connected={db2Connected}
            isDemoMode={isDemoMode}
            onRefresh={handleRefresh}
          />
          <main className="flex-1 p-8 overflow-y-auto max-w-[1600px] w-full mx-auto" key={refreshKey}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/events" element={<Events />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/incidents" element={<Incidents />} />
              <Route path="/investigation" element={<Investigation />} />
              <Route path="/approvals" element={<Approvals />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
};

export default App;
