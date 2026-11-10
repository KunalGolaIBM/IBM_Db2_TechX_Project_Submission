import { Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { CommandOverview } from './pages/CommandOverview';
import { GridInfrastructure } from './pages/GridInfrastructure';
import { IncidentIntelligence } from './pages/IncidentIntelligence';
import { AgentIntelligence } from './pages/AgentIntelligence';
import { CascadeSimulation } from './pages/CascadeSimulation';
import { RecoveryRecommendations } from './pages/RecoveryRecommendations';
import { SystemHealth } from './pages/SystemHealth';
import { NotFound } from './pages/NotFound';

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<CommandOverview />} />
        <Route path="/infrastructure" element={<GridInfrastructure />} />
        <Route path="/incidents" element={<IncidentIntelligence />} />
        <Route path="/agents" element={<AgentIntelligence />} />
        <Route path="/cascade" element={<CascadeSimulation />} />
        <Route path="/recovery" element={<RecoveryRecommendations />} />
        <Route path="/health" element={<SystemHealth />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
