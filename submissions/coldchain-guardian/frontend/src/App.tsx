import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { LayoutDashboard, Package2, Ship, AlertTriangle, Star, Zap, ChevronRight } from 'lucide-react';
import DashboardPage from './pages/DashboardPage';
import ShipmentsPage from './pages/ShipmentsPage';
import IncidentsPage from './pages/IncidentsPage';
import RecommendationsPage from './pages/RecommendationsPage';
import WorkflowPage from './pages/WorkflowPage';
import RiskAnalysisPage from './pages/RiskAnalysisPage';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/shipments', label: 'Shipments', icon: Ship },
  { to: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { to: '/risk', label: 'AI Risk Analysis', icon: Star },
  { to: '/recommendations', label: 'Recommendations', icon: ChevronRight },
  { to: '/workflow', label: 'Workflow', icon: Zap },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-navy-900 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-navy-800 border-r border-navy-600 flex flex-col flex-shrink-0">
          {/* Logo */}
          <div className="p-6 border-b border-navy-600">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center">
                <Package2 className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-white font-bold text-sm leading-tight">ColdChain</h1>
                <p className="text-teal-400 text-xs font-medium">Guardian</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            {navItems.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
                      : 'text-slate-400 hover:text-white hover:bg-navy-600'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {label}
              </NavLink>
            ))}
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-navy-600">
            <p className="text-xs text-slate-500">Powered by IBM Db2</p>
            <p className="text-xs text-slate-600">LangGraph · CrewAI</p>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/shipments" element={<ShipmentsPage />} />
            <Route path="/incidents" element={<IncidentsPage />} />
            <Route path="/risk" element={<RiskAnalysisPage />} />
            <Route path="/recommendations" element={<RecommendationsPage />} />
            <Route path="/workflow" element={<WorkflowPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
