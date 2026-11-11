import React, { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { DemoJourneyGuide } from './components/DemoJourneyGuide';
import { CitizenDashboard } from './components/citizen/CitizenDashboard';
import { ReportComplaintForm } from './components/citizen/ReportComplaintForm';
import { MyComplaints } from './components/citizen/MyComplaints';
import { UserProfileView } from './components/citizen/UserProfileView';
import { AdminDashboard } from './components/admin/AdminDashboard';
import { DepartmentManagement } from './components/admin/DepartmentManagement';
import { CategoryManagement } from './components/admin/CategoryManagement';
import { AdminAnalytics } from './components/admin/AdminAnalytics';
import { AdminSettings } from './components/admin/AdminSettings';
import { DepartmentDashboard } from './components/staff/DepartmentDashboard';
import { NotificationCenter } from './components/notifications/NotificationCenter';
import { ComplaintDetailsModal } from './components/complaints/ComplaintDetailsModal';
import { Complaint, UserRole } from './types';
import {
  fetchAllComplaints,
  fetchCitizenComplaints,
  seedInitialDepartments
} from './services/complaintService';
import { Loader2, ShieldCheck, Building2 } from 'lucide-react';

function MainLayout() {
  const { activeRole, userProfile, currentUser, loading: authLoading } = useAuth();

  // Active tab state
  const [currentTab, setCurrentTab] = useState<string>('citizen-overview');
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [loadingComplaints, setLoadingComplaints] = useState<boolean>(true);
  const [selectedComplaint, setSelectedComplaint] = useState<Complaint | null>(null);
  const [reportPreset, setReportPreset] = useState<'pothole' | 'garbage' | 'streetlight' | null>(null);

  // Sync active default tab when role changes
  useEffect(() => {
    if (activeRole === 'admin') {
      setCurrentTab('admin-dashboard');
    } else if (activeRole === 'staff') {
      setCurrentTab('staff-dashboard');
    } else {
      setCurrentTab('citizen-overview');
    }
  }, [activeRole]);

  // Load complaints from Firestore
  const loadComplaints = useCallback(async () => {
    try {
      setLoadingComplaints(true);
      // Ensure default departments are seeded
      await seedInitialDepartments();

      // Fetch complaints from Firestore
      const list = await fetchAllComplaints();
      setComplaints(list || []);

      // If user had a modal open, sync its updated data
      if (selectedComplaint) {
        const refreshed = list.find(c => c.id === selectedComplaint.id);
        if (refreshed) setSelectedComplaint(refreshed);
      }
    } catch (err) {
      console.warn('Error loading complaints list:', err);
    } finally {
      setLoadingComplaints(false);
    }
  }, [selectedComplaint?.id]);

  useEffect(() => {
    loadComplaints();
  }, []);

  const handleOpenReportForm = (preset?: 'pothole' | 'garbage' | 'streetlight') => {
    setReportPreset(preset || null);
    setCurrentTab('citizen-report');
  };

  const handleSelectComplaintById = (complaintId: string) => {
    const found = complaints.find(c => c.complaintId === complaintId);
    if (found) {
      setSelectedComplaint(found);
    }
  };

  // Filter complaints for citizen view if in citizen mode
  const displayedComplaintsForCitizen = activeRole === 'citizen' && userProfile?.uid
    ? complaints.filter(c => c.userId === userProfile.uid || c.userId.startsWith('demo-citizen'))
    : complaints;

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
        <Building2 className="w-12 h-12 text-teal-400 animate-pulse mb-3" />
        <h2 className="text-lg font-bold">Connecting to CivicConnect...</h2>
        <p className="text-xs text-slate-400 mt-1">Verifying secure Firebase Firestore connection</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* Top Navigation */}
      <Navbar
        onOpenNotifications={() => setCurrentTab('notifications')}
        onSelectComplaint={handleSelectComplaintById}
      />

      {/* 9-Step Demo Journey Walkthrough Helper */}
      <DemoJourneyGuide
        onNavigateTab={(tab) => setCurrentTab(tab)}
        onOpenReportPotholePreset={() => handleOpenReportForm('pothole')}
      />

      {/* Main App Body with Sidebar & Content */}
      <div className="flex-1 flex max-w-7xl w-full mx-auto">
        {/* Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onSelectTab={(tab) => setCurrentTab(tab)}
        />

        {/* Dynamic Content Pane */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
          {/* CITIZEN VIEWS */}
          {currentTab === 'citizen-overview' && (
            <CitizenDashboard
              complaints={displayedComplaintsForCitizen}
              onOpenReportForm={handleOpenReportForm}
              onSelectComplaint={(c) => setSelectedComplaint(c)}
              onNavigateTab={(tab) => setCurrentTab(tab)}
            />
          )}

          {currentTab === 'citizen-report' && (
            <ReportComplaintForm
              initialPreset={reportPreset}
              onSuccess={(comp) => {
                loadComplaints();
                setSelectedComplaint(comp);
              }}
              onCancel={() => setCurrentTab('citizen-overview')}
            />
          )}

          {currentTab === 'citizen-complaints' && (
            <MyComplaints
              complaints={displayedComplaintsForCitizen}
              onSelectComplaint={(c) => setSelectedComplaint(c)}
              onOpenReportForm={() => handleOpenReportForm()}
            />
          )}

          {currentTab === 'citizen-profile' && (
            <UserProfileView />
          )}

          {/* ADMIN VIEWS */}
          {currentTab === 'admin-dashboard' && (
            <AdminDashboard
              complaints={complaints}
              onSelectComplaint={(c) => setSelectedComplaint(c)}
              onNavigateTab={(tab) => setCurrentTab(tab)}
            />
          )}

          {currentTab === 'admin-complaints' && (
            <AdminDashboard
              complaints={complaints}
              onSelectComplaint={(c) => setSelectedComplaint(c)}
              onNavigateTab={(tab) => setCurrentTab(tab)}
            />
          )}

          {currentTab === 'admin-departments' && (
            <DepartmentManagement complaints={complaints} />
          )}

          {currentTab === 'admin-categories' && (
            <CategoryManagement complaints={complaints} />
          )}

          {currentTab === 'admin-analytics' && (
            <AdminAnalytics complaints={complaints} />
          )}

          {currentTab === 'admin-settings' && (
            <AdminSettings onRefreshComplaints={loadComplaints} />
          )}

          {/* STAFF VIEWS */}
          {(currentTab === 'staff-dashboard' || currentTab === 'staff-complaints' || currentTab === 'staff-updates') && (
            <DepartmentDashboard
              complaints={complaints}
              onSelectComplaint={(c) => setSelectedComplaint(c)}
            />
          )}

          {/* SHARED NOTIFICATIONS VIEW */}
          {currentTab === 'notifications' && (
            <NotificationCenter onSelectComplaintId={handleSelectComplaintById} />
          )}
        </main>
      </div>

      {/* COMPLAINT DETAILS & AUDIT TIMELINE MODAL */}
      {selectedComplaint && (
        <ComplaintDetailsModal
          complaint={selectedComplaint}
          onClose={() => setSelectedComplaint(null)}
          onComplaintUpdated={loadComplaints}
        />
      )}
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MainLayout />
    </AuthProvider>
  );
}
