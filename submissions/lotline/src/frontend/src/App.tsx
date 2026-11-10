import React, { useEffect, useState, useCallback, useRef } from 'react';
import { SoffitBackground } from './components/shader/SoffitBackground';
import { TopNav } from './components/layout/TopNav';
import { HeroSection } from './components/layout/HeroSection';
import { ActiveIncidentCard } from './components/bento/ActiveIncidentCard';
import { IncidentBriefCard } from './components/bento/IncidentBriefCard';
import { ExposureIntelligenceCard } from './components/bento/ExposureIntelligenceCard';
import { TraceabilityCard } from './components/bento/TraceabilityCard';
import { ResponseQueueCard } from './components/bento/ResponseQueueCard';
import { ShipmentExposureTable } from './components/incidents/ShipmentExposureTable';
import { ProductExposureSection } from './components/incidents/ProductExposureSection';
import { AuditTimelineSection } from './components/incidents/AuditTimelineSection';
import { AgentIntelligenceModal } from './components/incidents/AgentIntelligenceModal';
import { DossierExportModal } from './components/incidents/DossierExportModal';
import { RecallExecutionControlTower } from './components/execution/RecallExecutionControlTower';
import { useSpringEntrance } from './hooks/useSpringEntrance';
import {
  fetchDbHealth,
  fetchIncident,
  fetchTrace,
  fetchExposure,
  fetchShipments,
  fetchActions,
  fetchAuditLog,
  updateActionDecision,
  runAgentWorkflow,
  resetDemoActions,
} from './services/api';
import type {
  IncidentDetails,
  TraceData,
  ExposureData,
  Shipment,
  RecallAction,
  AuditRecord,
  AgentWorkflowResult,
  TraceNode,
} from './services/api';

export function App() {
  const [viewMode, setViewMode] = useState<'overview' | 'execution'>('overview');
  const [dbStatus, setDbStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connecting');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isAgentRunning, setIsAgentRunning] = useState(false);
  const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);
  const [isDossierModalOpen, setIsDossierModalOpen] = useState(false);
  const [isActionProcessing, setIsActionProcessing] = useState(false);

  // Core Data States
  const [incident, setIncident] = useState<IncidentDetails | null>(null);
  const [trace, setTrace] = useState<TraceData | null>(null);
  const [exposure, setExposure] = useState<ExposureData | null>(null);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [actions, setActions] = useState<RecallAction[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([]);
  const [agentResult, setAgentResult] = useState<AgentWorkflowResult | null>(null);

  // Overview stage container ref for exact full-container WebGL2 canvas sizing
  const overviewStageRef = useRef<HTMLDivElement | null>(null);

  // Spring Entrance Animation Hook (stagger = 45ms, tension = 220, friction = 26)
  const { registerItem, replay } = useSpringEntrance(9, 45);

  // Load live Db2 data
  const loadData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [health, incData, traceData, expData, shpData, actData, audData] =
        await Promise.all([
          fetchDbHealth().catch(() => ({ status: 'disconnected', database: 'LOTLINE', host: '127.0.0.1:50000' })),
          fetchIncident('INC-2026-001'),
          fetchTrace('INC-2026-001'),
          fetchExposure('INC-2026-001'),
          fetchShipments('INC-2026-001'),
          fetchActions('INC-2026-001'),
          fetchAuditLog('INC-2026-001'),
        ]);

      setDbStatus(health.status === 'connected' ? 'connected' : 'disconnected');
      setIncident(incData);
      setTrace(traceData);
      setExposure(expData);
      setShipments(shpData);
      setActions(actData);
      setAuditLogs(audData);
    } catch (err) {
      console.error('Failed to load Db2 data:', err);
      setDbStatus('disconnected');
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Action Decisions (Approve / Reject) with Db2 ACID Transaction
  const handleActionDecision = async (actionId: string, decision: 'APPROVED' | 'REJECTED') => {
    setIsActionProcessing(true);
    try {
      await updateActionDecision(
        'INC-2026-001',
        actionId,
        decision,
        'Lead Product Safety Officer',
        `Human operator confirmed ${decision} via LOTLINE Response Terminal.`
      );
      const [newActions, newAudit] = await Promise.all([
        fetchActions('INC-2026-001'),
        fetchAuditLog('INC-2026-001'),
      ]);
      setActions(newActions);
      setAuditLogs(newAudit);
      setAgentResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          recommended_actions: newActions,
        };
      });
    } catch (e) {
      console.error('Error submitting decision:', e);
      alert('Failed to update action decision in IBM Db2.');
    } finally {
      setIsActionProcessing(false);
    }
  };

  // Reset Demo Actions in IBM Db2
  const handleResetDemo = async () => {
    setIsActionProcessing(true);
    try {
      await resetDemoActions('INC-2026-001');
      const [newActions, newAudit] = await Promise.all([
        fetchActions('INC-2026-001'),
        fetchAuditLog('INC-2026-001'),
      ]);
      setActions(newActions);
      setAuditLogs(newAudit);
      setAgentResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          recommended_actions: newActions,
        };
      });
    } catch (e) {
      console.error('Error resetting demo:', e);
      alert('Failed to reset demo actions in IBM Db2.');
    } finally {
      setIsActionProcessing(false);
    }
  };

  // Run LangGraph Autonomous Agent Workflow
  const handleRunAgents = async () => {
    setIsAgentRunning(true);
    setIsAgentModalOpen(true);
    try {
      const result = await runAgentWorkflow('INC-2026-001');
      setAgentResult(result);
    } catch (e) {
      console.error('Agent workflow error:', e);
    } finally {
      setIsAgentRunning(false);
    }
  };

  const handleSelectLot = (_lot: TraceNode | string) => {
    const target = document.getElementById('product-exposure');
    if (target) {
      target.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="relative min-h-screen bg-[#0a0a0a] text-[#f2f2f2] font-sans overflow-x-hidden selection:bg-[#23cad2] selection:text-[#041222]">
      {/* 1. Fixed Top Navigation */}
      <div ref={registerItem(0)}>
        <TopNav
          dbStatus={dbStatus}
          onRefresh={loadData}
          isRefreshing={isRefreshing}
          viewMode={viewMode}
          onToggleView={setViewMode}
        />
      </div>

      {viewMode === 'execution' ? (
        /* PHASE 5: CLOSED-LOOP RECALL EXECUTION CONTROL TOWER */
        <RecallExecutionControlTower
          incidentId="INC-2026-001"
          onViewOverview={() => setViewMode('overview')}
          onRefreshParent={loadData}
        />
      ) : (
        /* APPROVED OVERVIEW DASHBOARD */
        <>
          {/* 2. OVERVIEW STAGE CONTAINER (Encloses Hero & full heights of all 5 Bento cards) */}
          <div
            ref={overviewStageRef}
            id="overview-stage"
            className="relative w-full overflow-hidden"
          >
            {/* Soffit 002 WebGL2 Living Atmospheric Gradient Engine */}
            <SoffitBackground containerRef={overviewStageRef} />

            {/* Ambient bottom fade transition into #0a0a0a page surface */}
            <div
              className="absolute inset-x-0 bottom-0 h-44 bg-gradient-to-b from-transparent via-[#0a0a0a]/75 to-[#0a0a0a] pointer-events-none z-10"
              aria-hidden="true"
            />

            {/* Foreground Content */}
            <div className="relative z-20">
              {/* Hero Section */}
              <div ref={registerItem(1)}>
                <HeroSection
                  onInvestigate={() => {
                    const el = document.getElementById('bento-grid');
                    el?.scrollIntoView({ behavior: 'smooth' });
                  }}
                  onRunAgents={handleRunAgents}
                  onExportDossier={() => setIsDossierModalOpen(true)}
                  isAgentRunning={isAgentRunning}
                />
              </div>

              {/* MAIN BENTO COMPOSITION: Controlled Responsive Layout (3-Col Desktop, 2-Col Tablet, 1-Col Mobile) */}
              <main id="bento-grid" className="max-w-[1720px] mx-auto px-4 sm:px-6 pt-2 pb-14">
                <div className="bento-layout-grid">
                  {/* CARD 1: ACTIVE INCIDENT (Left 32% Desktop, Col A Tablet) */}
                  <div ref={registerItem(2)} className="bento-area-active h-full">
                    <ActiveIncidentCard
                      incident={incident}
                      onSelectLot={handleSelectLot}
                      onExportDossier={() => setIsDossierModalOpen(true)}
                    />
                  </div>

                  {/* CARD 2: INCIDENT BRIEF (Middle Top Desktop, Col B Top Tablet) */}
                  <div ref={registerItem(3)} className="bento-area-brief h-full">
                    <IncidentBriefCard incident={incident} />
                  </div>

                  {/* CARD 3: EXPOSURE INTELLIGENCE (Middle Bottom Desktop, Col B Middle Tablet) */}
                  <div ref={registerItem(4)} className="bento-area-exposure h-full">
                    <ExposureIntelligenceCard exposure={exposure} />
                  </div>

                  {/* CARD 4: TRACEABILITY NETWORK (Right Top Desktop, Col A Bottom Tablet) */}
                  <div ref={registerItem(5)} className="bento-area-trace h-full">
                    <TraceabilityCard
                      trace={trace}
                      onSelectLot={handleSelectLot}
                    />
                  </div>

                  {/* CARD 5: RESPONSE QUEUE (Right Bottom Desktop, Col B Bottom Tablet) */}
                  <div ref={registerItem(6)} className="bento-area-response h-full">
                    <ResponseQueueCard
                      actions={actions}
                      onDecision={handleActionDecision}
                      isProcessing={isActionProcessing}
                    />
                  </div>
                </div>
              </main>
            </div>
          </div>

          {/* 3. BELOW-THE-FOLD OPERATIONAL SECTIONS */}
          <div className="relative z-20 bg-[#0a0a0a] border-t border-white/8">
            <div className="max-w-[1720px] mx-auto px-4 sm:px-6 py-10 space-y-8">
              <div ref={registerItem(7)}>
                <ShipmentExposureTable shipments={shipments} />
              </div>

              <div ref={registerItem(8)}>
                <ProductExposureSection batches={exposure?.affected_batches || []} />
              </div>

              <div>
                <AuditTimelineSection auditLogs={auditLogs} />
              </div>
            </div>
          </div>
        </>
      )}

      {/* 4. Footer Telemetry */}
      <footer className="border-t border-white/8 py-8 px-4 sm:px-6 text-xs font-mono text-white/40 bg-[#0a0a0a]">
        <div className="max-w-[1720px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#23cad2]" />
            <span>LOTLINE AGENTIC PLATFORM • IBM Db2Hack 2026</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 sm:gap-6">
            <span>DATABASE: IBM DB2 12.1</span>
            <span>SCHEMA: LOTLINE_APP</span>
            <button
              onClick={replay}
              title="Shortcut: Shift + R"
              className="text-[#8ef5e6] hover:underline cursor-pointer"
            >
              Replay Entrance (Shift+R)
            </button>
          </div>
        </div>
      </footer>

      {/* LangGraph Multi-Agent Modal */}
      <AgentIntelligenceModal
        isOpen={isAgentModalOpen}
        onClose={() => setIsAgentModalOpen(false)}
        workflowResult={agentResult}
        isRunning={isAgentRunning}
        onRunAgain={handleRunAgents}
        onDecision={handleActionDecision}
        onResetDemo={handleResetDemo}
        onExportDossier={() => setIsDossierModalOpen(true)}
        isProcessing={isActionProcessing}
      />

      {/* Official Recall Dossier PDF Generator Modal */}
      <DossierExportModal
        isOpen={isDossierModalOpen}
        onClose={() => setIsDossierModalOpen(false)}
        incidentId="INC-2026-001"
        onDossierGenerated={loadData}
      />
    </div>
  );
}

export default App;
