import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useMarketDataStore } from './stores/marketStore';

import CarbonNovaLayout from './components/layout/CarbonNovaLayout';
import AuthLayout from './components/layout/AuthLayout';
import RoleLayout from './components/layout/RoleLayout';

import HomeDashboard from './pages/HomeDashboard';
import LandAnalysis from './pages/LandAnalysis';
import CarbonEstimates from './pages/CarbonEstimates';
import MonitoringPage from './pages/MonitoringPage';
import ProjectsPage from './pages/ProjectsPage';
import CarbonCreditsPage from './pages/CarbonCreditsPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import Marketplace from './pages/Marketplace';
import ListingDetail from './pages/ListingDetail';
import SellerDashboard from './pages/seller/Dashboard';
import BuyerDashboard from './pages/buyer/Dashboard';
import AdminDashboard from './pages/admin/Dashboard';
import Login from './pages/auth/Login';
import Signup from './pages/auth/Signup';
import Onboarding from './pages/auth/Onboarding';
import RoleSelect from './pages/RoleSelect';

import DemoSellerDashboard from './pages/demo/seller/Dashboard';
import DemoSellerMarketplace from './pages/demo/seller/Marketplace';
import DemoSellerLandIntel from './pages/demo/seller/LandIntelligence';
import DemoSellerLandReg from './pages/demo/seller/LandRegistration';
import DemoSellerProjects from './pages/demo/seller/Projects';
import DemoSellerCredits from './pages/demo/seller/Credits';
import DemoSellerTx from './pages/demo/seller/Transactions';
import DemoSellerProfile from './pages/demo/seller/Profile';

import DemoBuyerDashboard from './pages/demo/buyer/Dashboard';
import DemoBuyerMarketplace from './pages/demo/buyer/Marketplace';
import DemoBuyerExplore from './pages/demo/buyer/Explore';
import DemoBuyerQuality from './pages/demo/buyer/Quality';
import DemoBuyerDocs from './pages/demo/buyer/DocumentVerification';
import DemoBuyerPortfolio from './pages/demo/buyer/Portfolio';
import DemoBuyerTx from './pages/demo/buyer/Transactions';
import DemoBuyerProfile from './pages/demo/buyer/Profile';

import DemoAdminDashboard from './pages/demo/admin/Dashboard';
import DemoAdminUsers, { AdminSellers, AdminBuyers } from './pages/demo/admin/Users';
import DemoAdminLandProjects from './pages/demo/admin/LandProjects';
import DemoAdminCredits from './pages/demo/admin/CreditVerification';
import DemoAdminMarketplace from './pages/demo/admin/MarketplaceMgmt';
import DemoAdminTx from './pages/demo/admin/Transactions';
import DemoAdminAudit from './pages/demo/admin/Audit';
import DemoAdminSettings from './pages/demo/admin/Settings';

const App = () => {
  const { startSimulation, stopSimulation } = useMarketDataStore();
  useEffect(() => {
    startSimulation();
    return () => stopSimulation();
  }, [startSimulation, stopSimulation]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/role-select" element={<RoleSelect />} />

        <Route element={<RoleLayout role="seller" />}>
          <Route path="/demo/seller/dashboard" element={<DemoSellerDashboard />} />
          <Route path="/demo/seller/marketplace" element={<DemoSellerMarketplace />} />
          <Route path="/demo/seller/land-intelligence" element={<DemoSellerLandIntel />} />
          <Route path="/demo/seller/land-registration" element={<DemoSellerLandReg />} />
          <Route path="/demo/seller/projects" element={<DemoSellerProjects />} />
          <Route path="/demo/seller/credits" element={<DemoSellerCredits />} />
          <Route path="/demo/seller/transactions" element={<DemoSellerTx />} />
          <Route path="/demo/seller/profile" element={<DemoSellerProfile />} />
          <Route path="/demo/seller/*" element={<Navigate to="/demo/seller/dashboard" replace />} />
        </Route>

        <Route element={<RoleLayout role="buyer" />}>
          <Route path="/demo/buyer/dashboard" element={<DemoBuyerDashboard />} />
          <Route path="/demo/buyer/marketplace" element={<DemoBuyerMarketplace />} />
          <Route path="/demo/buyer/explore" element={<DemoBuyerExplore />} />
          <Route path="/demo/buyer/quality" element={<DemoBuyerQuality />} />
          <Route path="/demo/buyer/documents" element={<DemoBuyerDocs />} />
          <Route path="/demo/buyer/portfolio" element={<DemoBuyerPortfolio />} />
          <Route path="/demo/buyer/transactions" element={<DemoBuyerTx />} />
          <Route path="/demo/buyer/profile" element={<DemoBuyerProfile />} />
          <Route path="/demo/buyer/*" element={<Navigate to="/demo/buyer/dashboard" replace />} />
        </Route>

        <Route element={<RoleLayout role="admin" />}>
          <Route path="/demo/admin/dashboard" element={<DemoAdminDashboard />} />
          <Route path="/demo/admin/users" element={<DemoAdminUsers />} />
          <Route path="/demo/admin/sellers" element={<AdminSellers />} />
          <Route path="/demo/admin/buyers" element={<AdminBuyers />} />
          <Route path="/demo/admin/land-projects" element={<DemoAdminLandProjects />} />
          <Route path="/demo/admin/credit-verification" element={<DemoAdminCredits />} />
          <Route path="/demo/admin/marketplace" element={<DemoAdminMarketplace />} />
          <Route path="/demo/admin/transactions" element={<DemoAdminTx />} />
          <Route path="/demo/admin/audit" element={<DemoAdminAudit />} />
          <Route path="/demo/admin/settings" element={<DemoAdminSettings />} />
          <Route path="/demo/admin/*" element={<Navigate to="/demo/admin/dashboard" replace />} />
        </Route>

        {/* Existing CarbonNova application preserved */}
        <Route element={<CarbonNovaLayout />}>
          <Route path="/" element={<HomeDashboard />} />
          <Route path="/home" element={<HomeDashboard />} />
          <Route path="/land-analysis" element={<LandAnalysis />} />
          <Route path="/carbon-estimates" element={<CarbonEstimates />} />
          <Route path="/monitoring" element={<MonitoringPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectsPage />} />
          <Route path="/carbon-credits" element={<CarbonCreditsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/marketplace" element={<Marketplace />} />
          <Route path="/marketplace/:id" element={<ListingDetail />} />
          <Route path="/seller/dashboard" element={<SellerDashboard />} />
          <Route path="/seller/projects" element={<ProjectsPage />} />
          <Route path="/seller/monitoring" element={<MonitoringPage />} />
          <Route path="/seller/reports" element={<ReportsPage />} />
          <Route path="/buyer/dashboard" element={<BuyerDashboard />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
        </Route>

        <Route element={<AuthLayout />}>
          <Route path="/auth/login" element={<Login />} />
          <Route path="/auth/signup" element={<Signup />} />
          <Route path="/auth/onboarding" element={<Onboarding />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
