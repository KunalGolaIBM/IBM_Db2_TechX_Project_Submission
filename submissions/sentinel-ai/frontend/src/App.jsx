import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import DashboardPage from './pages/DashboardPage';
import MonitoringPage from './pages/MonitoringPage';
import IncidentDetailsPage from './pages/IncidentDetailsPage';
import ApprovalsPage from './pages/ApprovalsPage';
import ReportViewPage from './pages/ReportViewPage';
import SystemStatusPage from './pages/SystemStatusPage';
import { SentinelApi } from './services/api';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

export default function App() {
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [logins, setLogins] = useState([]);
  const [accessLogs, setAccessLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [selectedIncidentDetails, setSelectedIncidentDetails] = useState(null);
  const [reportIncidentId, setReportIncidentId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [bannerNotice, setBannerNotice] = useState(null);

  // Load initial telemetry on mount
  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    setLoading(true);
    try {
      const [statsData, incData, altData, loginData, accData, userData, recData] = await Promise.all([
        SentinelApi.getDashboardStats().catch(() => null),
        SentinelApi.getIncidents().catch(() => []),
        SentinelApi.getAlerts().catch(() => []),
        SentinelApi.getLogins().catch(() => []),
        SentinelApi.getAccessLogs().catch(() => []),
        SentinelApi.getUsers().catch(() => []),
        SentinelApi.getRecommendations().catch(() => [])
      ]);

      if (statsData) setStats(statsData);
      setIncidents(incData);
      setAlerts(altData);
      setLogins(loginData);
      setAccessLogs(accData);
      setUsers(userData);
      setRecommendations(recData);
    } catch (err) {
      console.error('Failed to load telemetry data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectIncident = async (incidentId) => {
    setLoading(true);
    try {
      const details = await SentinelApi.getIncidentDetails(incidentId);
      setSelectedIncidentDetails(details);
      setCurrentTab('incident-details');
    } catch (err) {
      console.error('Failed to fetch incident details:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerSimulation = async () => {
    setLoading(true);
    setBannerNotice({ type: 'info', message: 'Simulating Section 8 attack scenario and orchestrating 5 LangGraph agents...' });
    try {
      const result = await SentinelApi.simulateAttack('USR-101');
      await loadAllData();
      
      setBannerNotice({
        type: 'success',
        message: `Attack Scenario correlated successfully! Incident ${result.incident_id} created with CRITICAL severity (Risk Score: ${result.risk_score}/100).`
      });

      if (result.incident_id) {
        await handleSelectIncident(result.incident_id);
      }
    } catch (err) {
      setBannerNotice({ type: 'error', message: `Attack simulation failed: ${err.message}` });
    } finally {
      setLoading(false);
      setTimeout(() => setBannerNotice(null), 8000);
    }
  };

  const handleInvestigateUser = async (userId) => {
    setLoading(true);
    setBannerNotice({ type: 'info', message: `Executing LangGraph Multi-Agent investigation on ${userId}...` });
    try {
      const result = await SentinelApi.investigateAccount(userId, 24);
      await loadAllData();
      setBannerNotice({
        type: 'success',
        message: `Investigation completed for ${userId}. Severity: ${result.severity} (Risk: ${result.risk_score}/100).`
      });
      if (result.incident_id) {
        await handleSelectIncident(result.incident_id);
      }
    } catch (err) {
      setBannerNotice({ type: 'error', message: `Investigation failed: ${err.message}` });
    } finally {
      setLoading(false);
      setTimeout(() => setBannerNotice(null), 8000);
    }
  };

  const handleExecuteRecommendation = async (recId, action, adminName, notes) => {
    try {
      await SentinelApi.actOnRecommendation(recId, action, adminName, notes);
      await loadAllData();
      if (selectedIncidentDetails) {
        await handleSelectIncident(selectedIncidentDetails.incident.incident_id);
      }
      setBannerNotice({
        type: 'success',
        message: `Recommendation ${recId} successfully ${action === 'APPROVE' ? 'AUTHORIZED and EXECUTED' : 'REJECTED'}.`
      });
      setTimeout(() => setBannerNotice(null), 6000);
    } catch (err) {
      alert(`Action error: ${err.message}`);
    }
  };

  const handleViewReport = (incidentId) => {
    setReportIncidentId(incidentId);
    setCurrentTab('reports');
  };

  const pendingApprovalsCount = recommendations.filter(r => r.status === 'PENDING_APPROVAL').length;

  return (
    <div className="min-h-screen bg-[#070d18] text-slate-100 flex flex-col bg-grid-pattern">
      <Navbar systemStatus={stats?.system_status} />

      {/* Floating System Notification Banner */}
      {bannerNotice && (
        <div className={`py-2 px-6 text-xs font-mono-code font-bold flex items-center justify-between transition-all ${
          bannerNotice.type === 'success' 
            ? 'bg-emerald-950/90 text-emerald-300 border-b border-emerald-800' 
            : bannerNotice.type === 'error'
            ? 'bg-rose-950/90 text-rose-300 border-b border-rose-800'
            : 'bg-blue-950/90 text-cyan-300 border-b border-blue-800'
        }`}>
          <div className="flex items-center space-x-2">
            {bannerNotice.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertCircle className="w-4 h-4 text-cyan-400" />
            )}
            <span>{bannerNotice.message}</span>
          </div>
          <button onClick={() => setBannerNotice(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}

      <div className="flex flex-1">
        <Sidebar 
          currentTab={currentTab} 
          setTab={setCurrentTab} 
          pendingCount={pendingApprovalsCount}
          onTriggerSimulation={handleTriggerSimulation}
        />

        <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
          {currentTab === 'dashboard' && (
            <DashboardPage
              stats={stats}
              incidents={incidents}
              alerts={alerts}
              onSelectIncident={handleSelectIncident}
              onTriggerSimulation={handleTriggerSimulation}
              onInvestigateUser={handleInvestigateUser}
              loading={loading}
              onRefresh={loadAllData}
            />
          )}

          {currentTab === 'monitoring' && (
            <MonitoringPage
              logins={logins}
              accessLogs={accessLogs}
              alerts={alerts}
              users={users}
              onInvestigateUser={handleInvestigateUser}
            />
          )}

          {currentTab === 'incidents' && (
            <DashboardPage
              stats={stats}
              incidents={incidents}
              alerts={alerts}
              onSelectIncident={handleSelectIncident}
              onTriggerSimulation={handleTriggerSimulation}
              onInvestigateUser={handleInvestigateUser}
              loading={loading}
              onRefresh={loadAllData}
            />
          )}

          {currentTab === 'incident-details' && (
            <IncidentDetailsPage
              incidentDetails={selectedIncidentDetails}
              onBack={() => setCurrentTab('dashboard')}
              onViewReport={handleViewReport}
              onExecuteRecommendation={handleExecuteRecommendation}
            />
          )}

          {currentTab === 'approvals' && (
            <ApprovalsPage
              recommendations={recommendations}
              onExecuteRecommendation={handleExecuteRecommendation}
              onRefresh={loadAllData}
            />
          )}

          {currentTab === 'reports' && (
            <ReportViewPage
              incidents={incidents}
              defaultIncidentId={reportIncidentId || incidents[0]?.incident_id}
            />
          )}

          {currentTab === 'system' && (
            <SystemStatusPage
              systemStatus={stats?.system_status}
            />
          )}
        </main>
      </div>
    </div>
  );
}

