import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldAlert,
  Send,
  Truck,
  PackageCheck,
  Flame,
  FileCheck2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ExternalLink,
  RefreshCw,
  Building2,
  Lock,
  ChevronRight,
  HelpCircle,
  FileText,
  UserCheck,
  XCircle,
  ArrowRight,
  Scale,
  Check,
  X,
  Radio,
  FileSignature
} from 'lucide-react';
import {
  fetchRawMassReconciliation,
  fetchCommunications,
  updateCommunicationStatus,
  fetchLogisticsInterventions,
  updateLogisticsIntervention,
  fetchProductRecoveries,
  recordProductRecovery,
  fetchRecoveryReconciliation,
  fetchProductDispositions,
  proposeProductDisposition,
  approveProductDisposition,
  executeProductDisposition,
  fetchFssaiChecklist,
  fetchRegulatorySubmissions,
  updateRegulatorySubmissionStage,
  fetchRecallEffectiveness,
  attemptCloseRecall,
  downloadRecallDossier,
  type MassReconciliation,
  type RecallCommunication,
  type LogisticsIntervention,
  type ProductRecovery,
  type RecoveryReconciliation,
  type ProductDisposition,
  type FssaiChecklist,
  type RegulatorySubmission,
  type RecallEffectiveness,
} from '../../services/api';

interface Props {
  incidentId: string;
  onViewOverview: () => void;
  onRefreshParent?: () => void;
}

type TabType = 'reconciliation' | 'communications' | 'logistics' | 'recoveries' | 'dispositions' | 'fssai' | 'effectiveness';

export const RecallExecutionControlTower: React.FC<Props> = ({
  incidentId,
  onViewOverview,
  onRefreshParent,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('reconciliation');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Phase 5 State
  const [massRecon, setMassRecon] = useState<MassReconciliation | null>(null);
  const [comms, setComms] = useState<RecallCommunication[]>([]);
  const [interventions, setInterventions] = useState<LogisticsIntervention[]>([]);
  const [recoveries, setRecoveries] = useState<ProductRecovery[]>([]);
  const [recoverySummary, setRecoverySummary] = useState<RecoveryReconciliation | null>(null);
  const [dispositions, setDispositions] = useState<ProductDisposition[]>([]);
  const [fssaiChecklist, setFssaiChecklist] = useState<FssaiChecklist | null>(null);
  const [submissions, setSubmissions] = useState<RegulatorySubmission[]>([]);
  const [effectiveness, setEffectiveness] = useState<RecallEffectiveness | null>(null);

  // Interactive Form Dialog States
  const [selectedComm, setSelectedComm] = useState<RecallCommunication | null>(null);
  const [commActionModal, setCommActionModal] = useState<'APPROVE' | 'SEND' | 'ACKNOWLEDGE' | null>(null);
  const [commNotes, setCommNotes] = useState('');
  const [commDeliveryRef, setCommDeliveryRef] = useState('');

  const [selectedIntervention, setSelectedIntervention] = useState<LogisticsIntervention | null>(null);
  const [interventionModal, setInterventionModal] = useState<boolean>(false);
  const [interventionNewStatus, setInterventionNewStatus] = useState<string>('CARRIER_ACKNOWLEDGED');
  const [interventionLocation, setInterventionLocation] = useState('');
  const [interventionNotes, setInterventionNotes] = useState('');
  const [interventionRecoveredQty, setInterventionRecoveredQty] = useState<number>(0);

  const [recoveryModal, setRecoveryModal] = useState<boolean>(false);
  const [recLotId, setRecLotId] = useState<string>('FIN-401');
  const [recLocationType, setRecLocationType] = useState<string>('RETAILER');
  const [recEntityName, setRecEntityName] = useState<string>('FreshMart Nagpur Central');
  const [recQuantity, setRecQuantity] = useState<number>(50);
  const [recVerificationMethod, setRecVerificationMethod] = useState<string>('PHYSICAL_AUDIT');
  const [recNotes, setRecNotes] = useState<string>('');

  const [dispositionModal, setDispositionModal] = useState<boolean>(false);
  const [dispLotId, setDispLotId] = useState<string>('FIN-401');
  const [dispType, setDispType] = useState<string>('DESTRUCTION');
  const [dispQty, setDispQty] = useState<number>(100);
  const [dispReason, setDispReason] = useState<string>('Confirmed Salmonella contamination via source lot RAW-204');
  const [dispMethod, setDispMethod] = useState<string>('Municipal high-temperature incineration per pollution control board norms');

  const [foscosRefInput, setFoscosRefInput] = useState<string>('FOSCOS-REC-2026-MH-08492');
  const [closureJustification, setClosureJustification] = useState<string>('');

  // Load all operational data
  const loadControlTowerData = useCallback(async () => {
    try {
      setError(null);
      const [
        reconData,
        commsData,
        intData,
        recList,
        recSummary,
        dispData,
        fssaiData,
        subData,
        effData,
      ] = await Promise.all([
        fetchRawMassReconciliation(incidentId),
        fetchCommunications(incidentId),
        fetchLogisticsInterventions(incidentId),
        fetchProductRecoveries(incidentId),
        fetchRecoveryReconciliation(incidentId),
        fetchProductDispositions(incidentId),
        fetchFssaiChecklist(incidentId),
        fetchRegulatorySubmissions(incidentId),
        fetchRecallEffectiveness(incidentId),
      ]);

      setMassRecon(reconData);
      setComms(commsData);
      setInterventions(intData);
      setRecoveries(recList);
      setRecoverySummary(recSummary);
      setDispositions(dispData);
      setFssaiChecklist(fssaiData);
      setSubmissions(subData);
      setEffectiveness(effData);
    } catch (err: any) {
      console.error('Failed to load Control Tower data:', err);
      setError(err?.message || 'Failed to load closed-loop execution data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [incidentId]);

  useEffect(() => {
    loadControlTowerData();
  }, [loadControlTowerData]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadControlTowerData();
    if (onRefreshParent) onRefreshParent();
  };

  const showNotification = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 4500);
  };

  // 1. Communication Status Update
  const handleUpdateComm = async (newStatus: string) => {
    if (!selectedComm) return;
    try {
      await updateCommunicationStatus(
        incidentId,
        selectedComm.comm_id,
        newStatus,
        'Lead Regulatory Officer',
        commNotes || `Status updated to ${newStatus} via Control Tower.`,
        commDeliveryRef
      );
      showNotification(`Communication ${selectedComm.comm_id} advanced to ${newStatus}`);
      setSelectedComm(null);
      setCommActionModal(null);
      setCommNotes('');
      setCommDeliveryRef('');
      loadControlTowerData();
    } catch (e: any) {
      alert(`Error updating communication: ${e.message}`);
    }
  };

  // 2. Logistics Intervention Update
  const handleUpdateIntervention = async () => {
    if (!selectedIntervention) return;
    try {
      await updateLogisticsIntervention(
        incidentId,
        selectedIntervention.intervention_id,
        interventionNewStatus,
        'Logistics Operations Director',
        interventionLocation || 'Pune Expressway Toll Plaza',
        interventionNotes || 'Driver instructed to hold cargo in refrigerated compartment.',
        Number(interventionRecoveredQty) || 0,
        'FAC-PUN'
      );
      showNotification(`Intervention ${selectedIntervention.intervention_id} updated to ${interventionNewStatus}`);
      setInterventionModal(false);
      setSelectedIntervention(null);
      loadControlTowerData();
    } catch (e: any) {
      alert(`Error updating intervention: ${e.message}`);
    }
  };

  // 3. Record Recovery
  const handleRecordRecovery = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await recordProductRecovery(incidentId, {
        lot_id: recLotId,
        source_location_type: recLocationType,
        source_entity_name: recEntityName,
        quantity_recovered: Number(recQuantity),
        unit_of_measure: 'UNIT',
        storage_facility_id: 'FAC-PUN',
        verification_method: recVerificationMethod,
        operator_name: 'Lead Quality Control Officer',
        notes: recNotes || 'Physical audit and serial barcode scan completed at quarantine dock.',
      });
      showNotification(`Recorded physical recovery of ${recQuantity} units of ${recLotId}`);
      setRecoveryModal(false);
      setRecNotes('');
      loadControlTowerData();
    } catch (e: any) {
      alert(`Recovery recording failed: ${e.message}`);
    }
  };

  // 4. Propose Disposition
  const handleProposeDisposition = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await proposeProductDisposition(incidentId, {
        lot_id: dispLotId,
        lot_type: dispLotId.startsWith('RAW') ? 'RAW_MATERIAL' : 'FINISHED_PRODUCT',
        quantity: Number(dispQty),
        unit_of_measure: dispLotId.startsWith('RAW') ? 'KG' : 'UNIT',
        disposition_type: dispType,
        reason: dispReason,
        proposed_method: dispMethod,
        authority_permission_ref: 'FSSAI-DISP-REQ-2026-001',
        operator_name: 'Product Safety Coordinator',
        evidence_attachment: 'CHAIN-OF-CUSTODY-EVID-001.pdf',
      });
      showNotification(`Proposed disposition for ${dispQty} units of ${dispLotId}`);
      setDispositionModal(false);
      loadControlTowerData();
    } catch (e: any) {
      alert(`Failed to propose disposition: ${e.message}`);
    }
  };

  // 5. Approve Disposition
  const handleApproveDisposition = async (dispId: string) => {
    if (!window.confirm('Confirm human safety authorization for this product disposition?')) return;
    try {
      await approveProductDisposition(incidentId, dispId, 'Chief Safety Officer', 'Authorized per microbiological laboratory evidence.');
      showNotification(`Disposition ${dispId} APPROVED by Chief Safety Officer`);
      loadControlTowerData();
    } catch (e: any) {
      alert(`Error approving disposition: ${e.message}`);
    }
  };

  // 6. Execute Disposition
  const handleExecuteDisposition = async (dispId: string) => {
    if (!window.confirm('Confirm destruction/disposition execution and witness verification?')) return;
    try {
      await executeProductDisposition(incidentId, dispId, 'Plant Operations Director', 'CERT-DESTRUCTION-INC-001.pdf');
      showNotification(`Disposition ${dispId} marked EXECUTED with certificate attached.`);
      loadControlTowerData();
    } catch (e: any) {
      alert(`Error executing disposition: ${e.message}`);
    }
  };

  // 7. FoSCoS Submission Stage Update
  const handleUpdateSubmissionStage = async (subId: string, newStage: string) => {
    try {
      await updateRegulatorySubmissionStage(
        incidentId,
        subId,
        newStage,
        'Regulatory Affairs Lead',
        foscosRefInput,
        'Schedule-I verified against ERP ground truth.',
        ''
      );
      showNotification(`FoSCoS regulatory stage advanced to ${newStage}`);
      loadControlTowerData();
    } catch (e: any) {
      alert(`Failed to update FoSCoS stage: ${e.message}`);
    }
  };

  // 8. Attempt Recall Closure
  const handleAttemptClose = async () => {
    const isEligible = effectiveness?.closure_eligible ?? effectiveness?.can_close_recall ?? false;
    const blockersList = effectiveness?.blockers ?? effectiveness?.closure_blockers ?? [];
    if (!isEligible) {
      alert(`Cannot close recall! Active regulatory blockers remain:\n\n${blockersList.join('\n')}`);
      return;
    }
    const just = prompt('Enter statutory closure justification:', closureJustification || 'All recall effectiveness parameters met.');
    if (!just) return;
    try {
      await attemptCloseRecall(incidentId, 'Chief Executive & Compliance Officer', just);
      showNotification('RECALL INC-2026-001 SUCCESSFULLY CLOSED IN IBM DB2.');
      loadControlTowerData();
    } catch (e: any) {
      alert(`Closure rejected by database audit validator:\n\n${e.message}`);
    }
  };

  return (
    <div className="relative min-h-screen bg-[#070b10] text-[#f2f4f8] font-sans pb-20 selection:bg-[#23cad2] selection:text-[#041222]">
      {/* Top Banner & Breadcrumb Switcher */}
      <div className="sticky top-0 z-30 bg-[#0d141e]/95 backdrop-blur-md border-b border-white/10 px-4 sm:px-6 py-3.5 transition-all">
        <div className="max-w-[1720px] mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={onViewOverview}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium text-white/70 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 transition-all cursor-pointer"
            >
              <ArrowRight className="w-3.5 h-3.5 rotate-180 text-[#23cad2]" />
              <span>RETURN TO OVERVIEW</span>
            </button>
            <div className="h-4 w-px bg-white/15 hidden sm:block" />
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#23cad2] animate-pulse" />
              <h1 className="text-sm sm:text-base font-bold font-mono tracking-tight text-white flex items-center gap-2">
                <span>RECALL CONTROL TOWER</span>
                <span className="text-white/40 font-normal">/</span>
                <span className="text-[#8ef5e6] font-mono text-xs sm:text-sm">INC-2026-001</span>
              </h1>
            </div>
            <span className="hidden lg:inline-flex px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-amber-500/10 border border-amber-500/30 text-amber-300">
              OPERATIONAL EXECUTION
            </span>
          </div>

          <div className="flex items-center gap-2.5 w-full md:w-auto justify-end">
            {successMessage && (
              <span className="text-xs font-mono text-[#8ef5e6] bg-[#23cad2]/15 border border-[#23cad2]/30 px-3 py-1 rounded-md animate-fade-in flex items-center gap-1.5">
                <Check className="w-3.5 h-3.5 text-[#23cad2]" />
                {successMessage}
              </span>
            )}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-white transition-all cursor-pointer active:scale-95"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-[#23cad2] ${refreshing ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">SYNC DB2</span>
            </button>
            <button
              onClick={() => downloadRecallDossier(incidentId, true, 'Safety Officer')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-[#23cad2] text-[#061826] hover:bg-[#1dbec6] transition-all cursor-pointer shadow-[0_0_15px_rgba(35,202,210,0.3)]"
            >
              <FileSignature className="w-3.5 h-3.5" />
              <span>EXPORT DOSSIER</span>
            </button>
          </div>
        </div>
      </div>

      {/* Control Tower Telemetry Strip */}
      <div className="max-w-[1720px] mx-auto px-4 sm:px-6 pt-5">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {/* KPI 1: Mass Balance */}
          <div className="p-3.5 rounded-xl bg-[#0f1724] border border-white/8 flex flex-col justify-between">
            <span className="text-[10px] font-mono tracking-wider uppercase text-white/50 flex items-center gap-1">
              <Scale className="w-3 h-3 text-[#23cad2]" /> MASS RECONCILIATION
            </span>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-amber-300">
                {massRecon ? `${massRecon.unaccounted_quantity} ${massRecon.unit}` : '...'}
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold">
                {massRecon?.reconciliation_status || 'AUDITING'}
              </span>
            </div>
            <span className="text-[10px] font-mono text-white/40 mt-1">400 KG WIP + 50 KG Q / 500 KG</span>
          </div>

          {/* KPI 2: Consignee Comms */}
          <div className="p-3.5 rounded-xl bg-[#0f1724] border border-white/8 flex flex-col justify-between">
            <span className="text-[10px] font-mono tracking-wider uppercase text-white/50 flex items-center gap-1">
              <Send className="w-3 h-3 text-[#23cad2]" /> CONSIGNEE COMMS
            </span>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-white">
                {comms.filter((c) => c.status === 'ACKNOWLEDGED').length} / {comms.length}
              </span>
              <span className="text-[10px] font-mono text-white/50">ACKNOWLEDGED</span>
            </div>
            <span className="text-[10px] font-mono text-white/40 mt-1">
              {comms.filter((c) => c.status === 'SENT' || c.status === 'DELIVERED').length} in transit / pending
            </span>
          </div>

          {/* KPI 3: Logistics Interception */}
          <div className="p-3.5 rounded-xl bg-[#0f1724] border border-white/8 flex flex-col justify-between">
            <span className="text-[10px] font-mono tracking-wider uppercase text-white/50 flex items-center gap-1">
              <Truck className="w-3 h-3 text-[#23cad2]" /> LOGISTICS INTERCEPT
            </span>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-[#8ef5e6]">
                {interventions[0]?.current_status === 'RETURNED_TO_WAREHOUSE' || interventions[0]?.current_status === 'INTERCEPTION_CONFIRMED'
                  ? 'CONFIRMED'
                  : interventions[0]?.current_status || 'STANDBY'}
              </span>
            </div>
            <span className="text-[10px] font-mono text-white/40 mt-1">SHP-002 • 200 units FIN-401</span>
          </div>

          {/* KPI 4: Market Recovery */}
          <div className="p-3.5 rounded-xl bg-[#0f1724] border border-white/8 flex flex-col justify-between">
            <span className="text-[10px] font-mono tracking-wider uppercase text-white/50 flex items-center gap-1">
              <PackageCheck className="w-3 h-3 text-[#23cad2]" /> MARKET RECOVERY
            </span>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-white">
                {recoverySummary ? `${(recoverySummary.market_recovery_pct ?? 0).toFixed(1)}%` : '0.0%'}
              </span>
              <span className="text-[10px] font-mono text-white/50">
                {recoverySummary ? `${recoverySummary.market_recovered_units ?? 0} / ${recoverySummary.market_distributed_units ?? 1050} units` : ''}
              </span>
            </div>
            <span className="text-[10px] font-mono text-white/40 mt-1">
              {recoverySummary ? `${recoverySummary.market_outstanding_units ?? 1050} units in trade (${recoverySummary.warehouse_contained_units ?? 1350} in whs)` : ''}
            </span>
          </div>

          {/* KPI 5: 24-hr FSSAI Deadline */}
          <div className="p-3.5 rounded-xl bg-[#0f1724] border border-white/8 flex flex-col justify-between">
            <span className="text-[10px] font-mono tracking-wider uppercase text-white/50 flex items-center gap-1">
              <Clock className="w-3 h-3 text-amber-400" /> FSSAI 24HR DEADLINE
            </span>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-amber-300">
                {fssaiChecklist ? `${(fssaiChecklist.hours_remaining ?? 0).toFixed(1)}h` : '...'}
              </span>
              <span className="text-[10px] font-mono text-white/50">REMAINING</span>
            </div>
            <span className="text-[10px] font-mono text-white/40 mt-1">Statutory awareness window</span>
          </div>

          {/* KPI 6: Recall Closure Status */}
          <div className="p-3.5 rounded-xl bg-[#0f1724] border border-white/8 flex flex-col justify-between">
            <span className="text-[10px] font-mono tracking-wider uppercase text-white/50 flex items-center gap-1">
              <Lock className="w-3 h-3 text-red-400" /> RECALL CLOSURE
            </span>
            <div className="mt-1 flex items-baseline gap-2">
              <span className={`text-xl font-bold font-mono ${(effectiveness?.closure_eligible ?? effectiveness?.can_close_recall) ? 'text-emerald-400' : 'text-red-400'}`}>
                {(effectiveness?.closure_eligible ?? effectiveness?.can_close_recall) ? 'ELIGIBLE' : 'BLOCKED'}
              </span>
            </div>
            <span className="text-[10px] font-mono text-white/40 mt-1">
              {(effectiveness?.blockers ?? effectiveness?.closure_blockers ?? []).length} statutory blockers
            </span>
          </div>
        </div>
      </div>

      {/* Primary Tab Navigation */}
      <div className="max-w-[1720px] mx-auto px-4 sm:px-6 pt-6">
        <div className="border-b border-white/10 flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
          {[
            { id: 'reconciliation', label: '1. Mass Reconciliation', icon: Scale },
            { id: 'communications', label: '2. Consignee Comms', icon: Send },
            { id: 'logistics', label: '3. Logistics Interception', icon: Truck },
            { id: 'recoveries', label: '4. Recovery Reconciliation', icon: PackageCheck },
            { id: 'dispositions', label: '5. Product Disposition', icon: Flame },
            { id: 'fssai', label: '6. FSSAI FoSCoS Tracker', icon: FileCheck2 },
            { id: 'effectiveness', label: '7. Effectiveness & Closure', icon: CheckCircle2 },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                data-tab-id={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg font-mono text-xs font-semibold whitespace-nowrap transition-all cursor-pointer border-b-2 ${
                  isActive
                    ? 'text-[#8ef5e6] bg-[#0f1c2b] border-[#23cad2] shadow-[0_2px_8px_rgba(35,202,210,0.15)]'
                    : 'text-white/60 hover:text-white hover:bg-white/[0.04] border-transparent'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[#23cad2]' : 'text-white/40'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-[1720px] mx-auto px-4 sm:px-6 pt-6">
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-3 text-white/50 font-mono text-sm">
            <RefreshCw className="w-6 h-6 animate-spin text-[#23cad2]" />
            <span>Connecting to IBM Db2 and querying closed-loop operational records...</span>
          </div>
        ) : error ? (
          <div className="p-6 rounded-xl bg-red-950/40 border border-red-500/30 text-red-200 font-mono text-sm">
            <div className="flex items-center gap-2 font-bold mb-2">
              <ShieldAlert className="w-5 h-5 text-red-400" />
              <span>Database Query Error</span>
            </div>
            <p>{error}</p>
          </div>
        ) : (
          <>
            {/* TAB 1: MASS RECONCILIATION */}
            {activeTab === 'reconciliation' && massRecon && (
              <div className="space-y-6 animate-fade-in">
                {/* Statutory Warning Box */}
                <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 flex items-start gap-3.5">
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <div className="text-xs font-mono text-amber-200/90 leading-relaxed">
                    <p className="font-bold text-amber-300 uppercase tracking-wider mb-1">
                      Statutory Forensic Integrity Rule (Phase 4 / A1 Correction)
                    </p>
                    <p>
                      Original raw intake quantity is <strong className="text-white">500.0 KG</strong>. Recorded WIP batch consumption across production levels is <strong className="text-white">400.0 KG</strong>. Quarantined physical stock is <strong className="text-white">50.0 KG</strong>. A remaining variance of <strong className="text-amber-300">50.0 KG</strong> is unaccounted in ERP genealogy records. Under regulatory audit protocol, this variance is flagged as <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40">UNRECONCILED</span>. Automated or silent inventory balancing is strictly prohibited.
                    </p>
                  </div>
                </div>

                {/* Mass Balance Table & Breakdown */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Left 2 Cols: Mass Balance Ledger */}
                  <div className="lg:col-span-2 p-5 rounded-2xl bg-[#0c131d] border border-white/8 space-y-4">
                    <div className="flex items-center justify-between border-b border-white/8 pb-3">
                      <div>
                        <h2 className="text-sm font-bold font-mono tracking-tight text-white flex items-center gap-2">
                          <Scale className="w-4 h-4 text-[#23cad2]" />
                          <span>DETERMINISTIC RAW MATERIAL RECONCILIATION LEDGER</span>
                        </h2>
                        <p className="text-xs font-mono text-white/50 mt-0.5">
                          Source Lot: {massRecon.source_lot_id} ({massRecon.item_name})
                        </p>
                      </div>
                      <span className="px-2.5 py-1 rounded text-xs font-mono font-bold bg-amber-500/15 border border-amber-500/30 text-amber-300">
                        STATUS: {massRecon.reconciliation_status}
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead>
                          <tr className="border-b border-white/8 text-white/40 uppercase">
                            <th className="py-2.5">Mass Component</th>
                            <th className="py-2.5">Quantity</th>
                            <th className="py-2.5">Unit</th>
                            <th className="py-2.5">% of Intake</th>
                            <th className="py-2.5">Audit Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                          <tr className="text-white">
                            <td className="py-3 font-semibold text-white">Original Raw Material Intake</td>
                            <td className="py-3 font-bold text-white">{massRecon.original_quantity.toFixed(1)}</td>
                            <td className="py-3 text-white/60">{massRecon.unit}</td>
                            <td className="py-3">100.0%</td>
                            <td className="py-3 text-[#8ef5e6]">Db2 Verified (SUPPLIER PO-9801)</td>
                          </tr>
                          <tr className="text-white/80">
                            <td className="py-3">Recorded WIP Production Consumption</td>
                            <td className="py-3 font-bold text-[#8ef5e6]">{massRecon.recorded_wip_consumption.toFixed(1)}</td>
                            <td className="py-3 text-white/60">{massRecon.unit}</td>
                            <td className="py-3">{((massRecon.recorded_wip_consumption / massRecon.original_quantity) * 100).toFixed(1)}%</td>
                            <td className="py-3 text-white/70">Db2 Verified (LOT_LINEAGE)</td>
                          </tr>
                          <tr className="text-white/80">
                            <td className="py-3">Quarantined Raw Material Stock</td>
                            <td className="py-3 font-bold text-emerald-400">{massRecon.quarantined_quantity.toFixed(1)}</td>
                            <td className="py-3 text-white/60">{massRecon.unit}</td>
                            <td className="py-3">{((massRecon.quarantined_quantity / massRecon.original_quantity) * 100).toFixed(1)}%</td>
                            <td className="py-3 text-emerald-400">Db2 Verified (INVENTORY FAC-PUN)</td>
                          </tr>
                          <tr className="text-white/80 bg-white/[0.02]">
                            <td className="py-3 font-semibold text-white">Total Accounted Mass</td>
                            <td className="py-3 font-bold text-white">{massRecon.accounted_quantity.toFixed(1)}</td>
                            <td className="py-3 text-white/60">{massRecon.unit}</td>
                            <td className="py-3">{((massRecon.accounted_quantity / massRecon.original_quantity) * 100).toFixed(1)}%</td>
                            <td className="py-3 text-white/60">Subtotal</td>
                          </tr>
                          <tr className="bg-amber-500/10 text-amber-200">
                            <td className="py-3 font-bold text-amber-300">Remaining Unaccounted Variance</td>
                            <td className="py-3 font-extrabold text-amber-300">{massRecon.unaccounted_quantity.toFixed(1)}</td>
                            <td className="py-3 font-semibold text-amber-300">{massRecon.unit}</td>
                            <td className="py-3 font-bold text-amber-300">{((massRecon.unaccounted_quantity / massRecon.original_quantity) * 100).toFixed(1)}%</td>
                            <td className="py-3 font-bold text-amber-300">UNRECONCILED (Audit Discrepancy)</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <div className="pt-2 text-[11px] font-mono text-white/50 leading-relaxed border-t border-white/5">
                      <p>
                        <strong>Audit Note:</strong> {massRecon.notes}
                      </p>
                    </div>
                  </div>

                  {/* Right 1 Col: WIP Batch Genealogy Allocation */}
                  <div className="p-5 rounded-2xl bg-[#0c131d] border border-white/8 space-y-4">
                    <h3 className="text-xs font-bold font-mono tracking-wider uppercase text-white/70">
                      WIP Batch Mass Genealogy
                    </h3>
                    <div className="space-y-3">
                      {massRecon.wip_breakdown.map((wip) => (
                        <div key={wip.wip_lot_id} className="p-3 rounded-xl bg-white/[0.03] border border-white/6 space-y-1">
                          <div className="flex items-center justify-between text-xs font-mono">
                            <span className="font-bold text-[#8ef5e6]">{wip.wip_lot_id}</span>
                            <span className="text-white/40">feeds {wip.fin_lot_id}</span>
                          </div>
                          <div className="flex items-baseline justify-between text-xs font-mono">
                            <span className="text-white/60">Consumed Raw Quantity</span>
                            <span className="font-bold text-white">{wip.quantity_consumed} {wip.unit}</span>
                          </div>
                          {/* Visual Bar */}
                          <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden mt-1">
                            <div
                              className="bg-[#23cad2] h-full"
                              style={{ width: `${(wip.quantity_consumed / massRecon.original_quantity) * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="p-3.5 rounded-xl bg-[#091018] border border-white/6 text-xs font-mono text-white/60 space-y-1">
                      <div className="flex justify-between">
                        <span>Sum of WIP:</span>
                        <span className="font-bold text-white">{massRecon.recorded_wip_consumption} KG</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Physical Quarantine:</span>
                        <span className="font-bold text-emerald-400">{massRecon.quarantined_quantity} KG</span>
                      </div>
                      <div className="flex justify-between border-t border-white/10 pt-1 text-amber-300 font-bold">
                        <span>Forensic Delta:</span>
                        <span>{massRecon.unaccounted_quantity} KG</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: CONSIGNEE COMMUNICATIONS */}
            {activeTab === 'communications' && (
              <div className="space-y-5 animate-fade-in">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-white/8 pb-4">
                  <div>
                    <h2 className="text-sm font-bold font-mono tracking-tight text-white flex items-center gap-2">
                      <Send className="w-4 h-4 text-[#23cad2]" />
                      <span>DOWNSTREAM CONSIGNEE RECALL COMMUNICATIONS</span>
                    </h2>
                    <p className="text-xs font-mono text-white/50 mt-0.5">
                      Statutory recall notices for commercial retailers holding affected finished batches.
                    </p>
                  </div>
                  <div className="text-xs font-mono text-white/60 bg-white/[0.04] px-3 py-1.5 rounded-lg border border-white/8">
                    Workflow: <span className="text-white font-bold">DRAFT → PENDING APPROVAL → APPROVED → SENT → DELIVERED → ACKNOWLEDGED</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {comms.map((c) => {
                    const isAck = c.status === 'ACKNOWLEDGED';
                    const isSent = c.status === 'SENT' || c.status === 'DELIVERED';
                    const isPending = c.status === 'PENDING_APPROVAL';
                    const isApproved = c.status === 'APPROVED';

                    return (
                      <div
                        key={c.comm_id}
                        className={`p-4 rounded-2xl bg-[#0c131d] border transition-all ${
                          isAck
                            ? 'border-emerald-500/30 bg-emerald-950/10'
                            : isSent
                            ? 'border-[#23cad2]/30'
                            : isApproved
                            ? 'border-blue-500/30'
                            : 'border-white/8'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-white/50">{c.comm_id}</span>
                              <span className="text-xs font-mono font-bold text-white">{c.recipient_entity_name}</span>
                            </div>
                            <p className="text-xs font-mono text-white/60">{c.recipient_contact} • {c.channel}</p>
                          </div>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase border ${
                              isAck
                                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                                : isSent
                                ? 'bg-[#23cad2]/15 border-[#23cad2]/30 text-[#8ef5e6]'
                                : isApproved
                                ? 'bg-blue-500/15 border-blue-500/30 text-blue-300'
                                : 'bg-amber-500/15 border-amber-500/30 text-amber-300'
                            }`}
                          >
                            {c.status}
                          </span>
                        </div>

                        <div className="mt-3 text-xs font-mono text-white/50 space-y-1 border-t border-white/5 pt-2">
                          <div className="flex justify-between">
                            <span>Template Ref:</span>
                            <span className="text-white/80">{c.statutory_template_ref}</span>
                          </div>
                          {c.approved_by && (
                            <div className="flex justify-between">
                              <span>Approved By:</span>
                              <span className="text-white/80">{c.approved_by}</span>
                            </div>
                          )}
                          {c.sent_at && (
                            <div className="flex justify-between">
                              <span>Sent Timestamp:</span>
                              <span className="text-white/80">{c.sent_at}</span>
                            </div>
                          )}
                          {c.delivery_confirmation_ref && (
                            <div className="flex justify-between">
                              <span>Delivery Proof:</span>
                              <span className="text-[#8ef5e6]">{c.delivery_confirmation_ref}</span>
                            </div>
                          )}
                          {c.acknowledged_at && (
                            <div className="flex justify-between text-emerald-400 font-bold">
                              <span>Consignee Acknowledged:</span>
                              <span>{c.acknowledged_at}</span>
                            </div>
                          )}
                        </div>

                        {/* Lifecycle Action Buttons */}
                        <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-end gap-2">
                          {c.status === 'PENDING_APPROVAL' && (
                            <button
                              onClick={() => {
                                setSelectedComm(c);
                                setCommActionModal('APPROVE');
                              }}
                              className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-all cursor-pointer flex items-center gap-1.5"
                            >
                              <UserCheck className="w-3.5 h-3.5" />
                              <span>APPROVE NOTICE</span>
                            </button>
                          )}

                          {c.status === 'APPROVED' && (
                            <button
                              onClick={() => {
                                setSelectedComm(c);
                                setCommActionModal('SEND');
                              }}
                              className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-[#23cad2] hover:bg-[#1dbec6] text-[#05131f] transition-all cursor-pointer flex items-center gap-1.5"
                            >
                              <Send className="w-3.5 h-3.5" />
                              <span>DISPATCH NOTICE</span>
                            </button>
                          )}

                          {(c.status === 'SENT' || c.status === 'DELIVERED') && (
                            <button
                              onClick={() => {
                                setSelectedComm(c);
                                setCommActionModal('ACKNOWLEDGE');
                              }}
                              className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-all cursor-pointer flex items-center gap-1.5"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>RECORD ACKNOWLEDGEMENT</span>
                            </button>
                          )}

                          {c.status === 'ACKNOWLEDGED' && (
                            <span className="text-xs font-mono text-emerald-400 flex items-center gap-1">
                              <Check className="w-3.5 h-3.5" /> Complete
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* TAB 3: LOGISTICS INTERCEPTION */}
            {activeTab === 'logistics' && (
              <div className="space-y-6 animate-fade-in">
                {/* Important Distinction Banner */}
                <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-500/30 flex items-start gap-3.5">
                  <Truck className="w-5 h-5 text-[#23cad2] shrink-0 mt-0.5" />
                  <div className="text-xs font-mono text-blue-200/90 leading-relaxed">
                    <p className="font-bold text-[#8ef5e6] uppercase tracking-wider mb-1">
                      Logistics Interception vs Retailer Notification Distinction (Phase 4 / A2 Correction)
                    </p>
                    <p>
                      Action <strong className="text-white">ACT-002</strong> is a commercial retailer notice for <em className="text-white">FreshMart Nagpur Central</em>. In-transit shipment <strong className="text-white">SHP-002</strong> comprises 200 units of <em className="text-white">FIN-401</em> en route to <em className="text-white">FreshMart Pune West</em> via carrier <strong className="text-white">ColdChain Logistics Pvt Ltd</strong>. ACT-002 must NOT be represented as proof that the carrier was intercepted. Under strict regulatory traceability, interception is only verified when a logistics officer records the actual carrier response and cargo location.
                    </p>
                  </div>
                </div>

                <div className="p-5 rounded-2xl bg-[#0c131d] border border-white/8 space-y-4">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-white/8 pb-3">
                    <div>
                      <h3 className="text-sm font-bold font-mono text-white flex items-center gap-2">
                        <Truck className="w-4 h-4 text-[#23cad2]" />
                        <span>ACTIVE IN-TRANSIT SHIPMENT INTERCEPTION MANAGEMENT</span>
                      </h3>
                      <p className="text-xs font-mono text-white/50 mt-0.5">
                        Shipment: SHP-002 • 200 Units of FIN-401 • In-Transit to FreshMart Pune West
                      </p>
                    </div>
                    {interventions[0] && (
                      <span className="px-3 py-1 rounded text-xs font-mono font-bold bg-[#23cad2]/15 border border-[#23cad2]/30 text-[#8ef5e6]">
                        CARRIER STATUS: {interventions[0].current_status}
                      </span>
                    )}
                  </div>

                  {interventions.map((intv) => (
                    <div key={intv.intervention_id} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs font-mono">
                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/6 space-y-1">
                        <span className="text-white/40 uppercase text-[10px]">Carrier Details</span>
                        <p className="font-bold text-white text-sm">{intv.carrier_name}</p>
                        <p className="text-white/60">Contact: {intv.carrier_contact_person || 'Dispatch Central'}</p>
                        <p className="text-white/50">Tracking: {intv.vehicle_tracking_ref}</p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/6 space-y-1">
                        <span className="text-white/40 uppercase text-[10px]">Cargo Location</span>
                        <p className="font-bold text-[#8ef5e6] text-sm">{intv.last_known_cargo_location || 'Pune Expressway Toll Dock'}</p>
                        <p className="text-white/60">Facility Return: {intv.returned_facility_id || 'FAC-PUN'}</p>
                        <p className="text-emerald-400 font-bold">Recovered: {intv.recovered_quantity} units</p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/6 space-y-1">
                        <span className="text-white/40 uppercase text-[10px]">Intervention Notes</span>
                        <p className="text-white/80 leading-relaxed">{intv.intervention_notes || 'Driver instructed to halt at cold storage checkpoint.'}</p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/6 flex flex-col justify-between">
                        <span className="text-white/40 uppercase text-[10px]">Operational Actions</span>
                        <button
                          onClick={() => {
                            setSelectedIntervention(intv);
                            setInterventionNewStatus(intv.current_status);
                            setInterventionLocation(intv.last_known_cargo_location || '');
                            setInterventionNotes(intv.intervention_notes || '');
                            setInterventionRecoveredQty(intv.recovered_quantity || 200);
                            setInterventionModal(true);
                          }}
                          className="w-full mt-2 py-2 px-3 rounded-lg text-xs font-mono font-semibold bg-[#23cad2] hover:bg-[#1dbec6] text-[#061826] transition-all cursor-pointer flex items-center justify-center gap-1.5"
                        >
                          <Truck className="w-3.5 h-3.5" />
                          <span>UPDATE CARRIER STATUS</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 4: PRODUCT RECOVERY RECONCILIATION */}
            {activeTab === 'recoveries' && recoverySummary && (
              <div className="space-y-6 animate-fade-in">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-white/8 pb-4">
                  <div>
                    <h2 className="text-sm font-bold font-mono tracking-tight text-white flex items-center gap-2">
                      <PackageCheck className="w-4 h-4 text-[#23cad2]" />
                      <span>PHYSICAL PRODUCT RECOVERY RECONCILIATION</span>
                    </h2>
                    <p className="text-xs font-mono text-white/50 mt-0.5">
                      Batch-level audit tracking across Warehouse, In-Transit Interception, and Retailer Returns.
                    </p>
                  </div>
                  <button
                    onClick={() => setRecoveryModal(true)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-mono font-semibold bg-[#23cad2] text-[#061826] hover:bg-[#1dbec6] transition-all cursor-pointer flex items-center gap-1.5 shadow-[0_0_15px_rgba(35,202,210,0.2)]"
                  >
                    <PackageCheck className="w-3.5 h-3.5" />
                    <span>RECORD NEW RECOVERY</span>
                  </button>
                </div>

                {/* Batch Breakdown Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {(recoverySummary.batches ?? recoverySummary.batch_breakdown ?? []).map((batch: any) => {
                    const mktRecoveryPct = Number(batch.market_recovery_pct ?? batch.recovery_rate_pct ?? 0);
                    const whContained = batch.warehouse_contained_units ?? batch.warehouse_quarantined ?? batch.warehouse_recovered ?? 0;
                    const retReturned = batch.retailer_returned_units ?? batch.retailer_returned ?? batch.retailer_recovered ?? 0;
                    const transIntercepted = batch.transit_intercepted_units ?? batch.transit_intercepted ?? batch.transit_recovered ?? 0;
                    const mktRecovered = batch.market_recovered_units ?? (retReturned + transIntercepted);
                    const mktOutstanding = batch.market_outstanding_units ?? batch.unrecovered_units ?? batch.outstanding_units ?? 0;
                    const distributed = batch.market_distributed_units ?? (batch.total_exposed_units - whContained);

                    return (
                      <div key={batch.lot_id} className="p-4 rounded-2xl bg-[#0c131d] border border-white/8 space-y-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-xs font-bold font-mono text-[#8ef5e6]">{batch.lot_id}</span>
                            <p className="text-xs font-mono text-white/70">{batch.item_name}</p>
                          </div>
                          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-white/5 text-white">
                            {mktRecoveryPct.toFixed(1)}% Mkt Rec
                          </span>
                        </div>

                        {/* Progress Bar */}
                        <div className="w-full bg-white/5 h-2 rounded-full overflow-hidden">
                          <div
                            className="bg-[#23cad2] h-full transition-all duration-300"
                            style={{ width: `${Math.min(100, mktRecoveryPct)}%` }}
                          />
                        </div>

                        <div className="text-xs font-mono text-white/60 space-y-1 pt-1 border-t border-white/5">
                          <div className="flex justify-between">
                            <span>Total Exposed Units:</span>
                            <span className="font-bold text-white">{batch.total_exposed_units}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Warehouse Contained:</span>
                            <span className="text-emerald-400 font-bold">{whContained} (Quarantined)</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Market Distributed:</span>
                            <span className="text-white/80">{distributed}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Retailer Returns:</span>
                            <span className="text-[#8ef5e6]">{retReturned}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Transit Intercepted:</span>
                            <span className="text-blue-300">{transIntercepted}</span>
                          </div>
                          <div className="flex justify-between border-t border-white/10 pt-1 text-white font-bold">
                            <span>Market Recovered:</span>
                            <span>{mktRecovered} / {distributed}</span>
                          </div>
                          <div className="flex justify-between text-amber-300 font-semibold">
                            <span>Market Outstanding:</span>
                            <span>{mktOutstanding}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Physical Recovery Audit Trail */}
                <div className="p-5 rounded-2xl bg-[#0c131d] border border-white/8 space-y-4">
                  <h3 className="text-xs font-bold font-mono tracking-wider uppercase text-white/70">
                    Physical Recovery Verified Audit Log ({recoveries.length} entries)
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead>
                        <tr className="border-b border-white/8 text-white/40 uppercase">
                          <th className="py-2.5">Recovery ID</th>
                          <th className="py-2.5">Batch</th>
                          <th className="py-2.5">Location Type</th>
                          <th className="py-2.5">Source Entity</th>
                          <th className="py-2.5">Quantity</th>
                          <th className="py-2.5">Verification</th>
                          <th className="py-2.5">Verified By</th>
                          <th className="py-2.5">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {recoveries.map((r) => (
                          <tr key={r.recovery_id} className="text-white/80 hover:bg-white/[0.02]">
                            <td className="py-3 font-semibold text-white">{r.recovery_id}</td>
                            <td className="py-3 text-[#8ef5e6] font-bold">{r.lot_id}</td>
                            <td className="py-3">{r.source_location_type}</td>
                            <td className="py-3 text-white">{r.source_entity_name}</td>
                            <td className="py-3 font-bold text-emerald-400">{r.quantity_recovered} {r.unit_of_measure}</td>
                            <td className="py-3 text-white/60">{r.verification_method}</td>
                            <td className="py-3 text-white/70">{r.verified_by_operator}</td>
                            <td className="py-3 text-white/50">{r.verified_at}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 5: PRODUCT DISPOSITION */}
            {activeTab === 'dispositions' && (
              <div className="space-y-6 animate-fade-in">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-white/8 pb-4">
                  <div>
                    <h2 className="text-sm font-bold font-mono tracking-tight text-white flex items-center gap-2">
                      <Flame className="w-4 h-4 text-[#23cad2]" />
                      <span>CONTROLLED PRODUCT DISPOSITION & DESTRUCTION</span>
                    </h2>
                    <p className="text-xs font-mono text-white/50 mt-0.5">
                      Statutory disposition pathways requiring explicit Human-in-the-Loop authorization.
                    </p>
                  </div>
                  <button
                    onClick={() => setDispositionModal(true)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-mono font-semibold bg-[#23cad2] text-[#061826] hover:bg-[#1dbec6] transition-all cursor-pointer flex items-center gap-1.5"
                  >
                    <Flame className="w-3.5 h-3.5" />
                    <span>PROPOSE DISPOSITION</span>
                  </button>
                </div>

                {/* Disposition Integrity Banner */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-xl bg-white/[0.02] border border-white/8 text-xs font-mono">
                  <div className="flex items-center justify-between border-b sm:border-b-0 sm:border-r border-white/8 pb-2 sm:pb-0 sm:pr-4">
                    <span className="text-white/60">Operational Verified Destruction:</span>
                    <span className="font-bold text-emerald-400">0.0 KG Raw • 0 UNIT Finished</span>
                  </div>
                  <div className="flex items-center justify-between sm:pl-4">
                    <span className="text-white/60">Synthetic Automated Test Fixtures:</span>
                    <span className="font-bold text-amber-300">25.0 KG (Excluded from Operational Totals)</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dispositions.map((d) => {
                    const isApproved = d.status === 'APPROVED';
                    const isExecuted = d.status === 'EXECUTED';
                    const isProposed = d.status === 'PROPOSED';
                    const isFixture = d.is_synthetic_fixture || d.is_fixture;

                    return (
                      <div
                        key={d.disposition_id}
                        className={`p-4 rounded-2xl bg-[#0c131d] border transition-all ${
                          isFixture
                            ? 'border-purple-500/30 bg-purple-950/10'
                            : isExecuted
                            ? 'border-emerald-500/30 bg-emerald-950/10'
                            : isApproved
                            ? 'border-blue-500/30 bg-blue-950/10'
                            : 'border-amber-500/30'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <span className="font-mono text-xs font-bold text-white/50">{d.disposition_id}</span>
                            <h3 className="text-xs font-bold font-mono text-white flex items-center gap-2">
                              <span>Lot: {d.lot_id}</span>
                              <span className="text-white/40">•</span>
                              <span className="text-white font-bold">{d.quantity} {d.unit_of_measure}</span>
                            </h3>
                          </div>
                          <div className="flex flex-col items-end gap-1">
                            {isFixture && (
                              <span className="px-2 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider uppercase bg-purple-500/20 border border-purple-500/40 text-purple-300">
                                DEMO FIXTURE (SYNTHETIC)
                              </span>
                            )}
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase border ${
                                isExecuted
                                  ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                                  : isApproved
                                  ? 'bg-blue-500/15 border-blue-500/30 text-blue-300'
                                  : 'bg-amber-500/15 border-amber-500/30 text-amber-300'
                              }`}
                            >
                              {d.status}
                            </span>
                          </div>
                        </div>

                        <div className="mt-3 text-xs font-mono text-white/60 space-y-1 border-t border-white/5 pt-2">
                          <div className="flex justify-between">
                            <span>Disposition Type:</span>
                            <span className="text-amber-300 font-bold">{d.disposition_type}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Proposed Method:</span>
                            <span className="text-white/80">{d.proposed_method}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Reason:</span>
                            <span className="text-white/70">{d.reason}</span>
                          </div>
                          {d.authorized_by_operator && (
                            <div className="flex justify-between text-blue-300">
                              <span>Authorized By:</span>
                              <span>{d.authorized_by_operator} ({d.authorized_at})</span>
                            </div>
                          )}
                          {d.evidence_attachment && (
                            <div className="flex justify-between text-[#8ef5e6]">
                              <span>Certificate Proof:</span>
                              <span>{d.evidence_attachment}</span>
                            </div>
                          )}
                        </div>

                        {/* Disposition Actions */}
                        <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-end gap-2">
                          {isProposed && (
                            <button
                              onClick={() => handleApproveDisposition(d.disposition_id)}
                              className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-all cursor-pointer flex items-center gap-1.5"
                            >
                              <UserCheck className="w-3.5 h-3.5" />
                              <span>APPROVE DISPOSITION</span>
                            </button>
                          )}

                          {isApproved && (
                            <button
                              onClick={() => handleExecuteDisposition(d.disposition_id)}
                              className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-all cursor-pointer flex items-center gap-1.5"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>RECORD EXECUTION & EVIDENCE</span>
                            </button>
                          )}

                          {isExecuted && (
                            <span className="text-xs font-mono text-emerald-400 flex items-center gap-1">
                              <Check className="w-3.5 h-3.5" /> Executed & Verified
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* TAB 6: FSSAI FOSCOS OPERATIONS TRACKER */}
            {activeTab === 'fssai' && fssaiChecklist && (
              <div className="space-y-6 animate-fade-in">
                {/* 24-hr Countdown Banner */}
                <div className="p-4 rounded-xl bg-[#0c131d] border border-amber-500/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <Clock className="w-6 h-6 text-amber-400 shrink-0" />
                    <div className="space-y-0.5">
                      <h3 className="text-xs font-bold font-mono text-white tracking-wider uppercase">
                        Statutory 24-Hour Recall Alert Window (FSSAI Reg. 2017)
                      </h3>
                      <p className="text-xs font-mono text-white/50">
                        Awareness timestamp: {fssaiChecklist.fssai_awareness_timestamp} • Deadline: {fssaiChecklist.statutory_deadline_timestamp}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-2xl font-black font-mono text-amber-300">
                      {fssaiChecklist.hours_remaining.toFixed(1)}h
                    </span>
                    <span className="text-xs font-mono font-bold px-2.5 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      {fssaiChecklist.deadline_status}
                    </span>
                  </div>
                </div>

                {/* FoSCoS Portal Submission Record */}
                <div className="p-5 rounded-2xl bg-[#0c131d] border border-white/8 space-y-4">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-white/8 pb-3">
                    <div>
                      <h3 className="text-sm font-bold font-mono text-white flex items-center gap-2">
                        <FileCheck2 className="w-4 h-4 text-[#23cad2]" />
                        <span>FSSAI FoSCoS PORTAL SUBMISSION WORKFLOW TRACKER</span>
                      </h3>
                      <p className="text-xs font-mono text-white/50 mt-0.5">
                        FSSAI Order dt. 18.03.2026: FBO filing tracking in FoSCoS portal.
                      </p>
                    </div>
                    {submissions[0] && (
                      <span className="px-3 py-1 rounded text-xs font-mono font-bold bg-[#23cad2]/15 border border-[#23cad2]/30 text-[#8ef5e6]">
                        STAGE: {submissions[0].current_stage}
                      </span>
                    )}
                  </div>

                  {submissions.map((sub) => (
                    <div key={sub.submission_id} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs font-mono">
                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/6 space-y-1">
                        <span className="text-white/40 uppercase text-[10px]">Portal Authority</span>
                        <p className="font-bold text-white text-sm">{sub.regulatory_authority}</p>
                        <p className="text-white/60">Portal: {sub.portal_name}</p>
                        <p className="text-white/50">Target Deadline: {sub.target_submission_deadline}</p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/6 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 uppercase text-[10px]">FoSCoS Reference Number</span>
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                            {sub.foscos_reference_label || 'Internal tracking reference (synthetic/demo)'}
                          </span>
                        </div>
                        <input
                          type="text"
                          value={foscosRefInput}
                          onChange={(e) => setFoscosRefInput(e.target.value)}
                          className="w-full bg-[#070b10] border border-white/15 rounded px-2.5 py-1.5 text-xs font-mono text-[#8ef5e6] font-bold focus:border-[#23cad2] outline-none"
                        />
                        <p className="text-white/40 text-[10px]">Assigned for internal demo tracking; not an official portal receipt.</p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/6 flex flex-col justify-between">
                        <span className="text-white/40 uppercase text-[10px]">Advance Workflow Stage</span>
                        <div className="flex gap-2 mt-2">
                          {sub.current_stage === 'SCHEDULE_I_DRAFT' && (
                            <button
                              onClick={() => handleUpdateSubmissionStage(sub.submission_id, 'OPERATOR_VERIFIED')}
                              className="w-full py-1.5 px-3 rounded text-xs font-mono font-semibold bg-[#23cad2] text-[#061826] hover:bg-[#1dbec6]"
                            >
                              MARK VERIFIED
                            </button>
                          )}
                          {sub.current_stage === 'OPERATOR_VERIFIED' && (
                            <button
                              onClick={() => handleUpdateSubmissionStage(sub.submission_id, 'INTERNAL_APPROVED')}
                              className="w-full py-1.5 px-3 rounded text-xs font-mono font-semibold bg-blue-600 text-white hover:bg-blue-500"
                            >
                              APPROVE SUBMISSION
                            </button>
                          )}
                          {sub.current_stage === 'INTERNAL_APPROVED' && (
                            <button
                              onClick={() => handleUpdateSubmissionStage(sub.submission_id, 'SUBMITTED_TO_FOSCOS')}
                              className="w-full py-1.5 px-3 rounded text-xs font-mono font-semibold bg-emerald-600 text-white hover:bg-emerald-500"
                            >
                              RECORD FOSCOS SUBMISSION
                            </button>
                          )}
                          {sub.current_stage === 'SUBMITTED_TO_FOSCOS' && (
                            <span className="text-emerald-400 font-bold flex items-center gap-1">
                              <Check className="w-4 h-4" /> SUBMITTED TO FOSCOS
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* 14-Item Schedule-I Statutory Checklist Table */}
                <div className="p-5 rounded-2xl bg-[#0c131d] border border-white/8 space-y-4">
                  <div className="flex items-center justify-between border-b border-white/8 pb-3">
                    <h3 className="text-xs font-bold font-mono tracking-wider uppercase text-white/70">
                      FSSAI Schedule-I Preparation Readiness Profile (14 Items)
                    </h3>
                    <div className="flex items-center gap-3 text-xs font-mono">
                      <span className="text-emerald-400 font-bold">{fssaiChecklist.verified_count} Db2 Verified</span>
                      <span className="text-amber-300 font-bold">{fssaiChecklist.manual_count} Manual Required</span>
                      <span className="text-red-400 font-bold">{fssaiChecklist.missing_count} Missing</span>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead>
                        <tr className="border-b border-white/8 text-white/40 uppercase">
                          <th className="py-2.5 w-12">#</th>
                          <th className="py-2.5">Schedule-I Item</th>
                          <th className="py-2.5">Statutory Reference</th>
                          <th className="py-2.5">Verification Status</th>
                          <th className="py-2.5">Db2 Ground-Truth Value</th>
                          <th className="py-2.5">Compliance Notes</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {(fssaiChecklist.checklist_items ?? (fssaiChecklist as any).items ?? []).map((item: any) => {
                          const itemNo = item.item_number ?? item.item_no;
                          const itemTitle = item.title ?? item.field_name;
                          const statRef = item.statutory_ref ?? item.statutory_mandate;
                          const val = item.db2_value ?? item.current_value;
                          const notes = item.compliance_notes ?? item.notes;
                          return (
                            <tr key={itemNo} className="text-white/80 hover:bg-white/[0.02]">
                              <td className="py-3 font-mono font-bold text-white/40">{itemNo}</td>
                              <td className="py-3 font-semibold text-white">{itemTitle}</td>
                              <td className="py-3 text-white/50">{statRef}</td>
                              <td className="py-3">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                                    item.status === 'Db2 verified'
                                      ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                                      : item.status === 'Manually required'
                                      ? 'bg-amber-500/15 border-amber-500/30 text-amber-300'
                                      : item.status === 'Evidence missing'
                                      ? 'bg-red-500/15 border-red-500/30 text-red-300'
                                      : 'bg-white/5 border-white/10 text-white/50'
                                  }`}
                                >
                                  {item.status}
                                </span>
                              </td>
                              <td className="py-3 font-mono text-[#8ef5e6]">{val || '—'}</td>
                              <td className="py-3 text-white/50 text-[11px] max-w-xs">{notes}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 7: POST-RECALL EFFECTIVENESS & CLOSURE */}
            {activeTab === 'effectiveness' && effectiveness && (() => {
              const isEligible = effectiveness.closure_eligible ?? effectiveness.can_close_recall ?? false;
              const blockersList = effectiveness.blockers ?? effectiveness.closure_blockers ?? [];
              const pMetrics = effectiveness.post_recall_metrics ?? {
                total_consignees_notified: effectiveness.orgs_notified ?? 0,
                total_consignees_acknowledged: effectiveness.orgs_acknowledged ?? 0,
                consignee_response_rate_pct: effectiveness.consignee_response_pct ?? 0,
                total_exposed_units: effectiveness.total_affected_units ?? 2400,
                total_recovered_units: effectiveness.quantity_recovered ?? 0,
                product_recovery_rate_pct: effectiveness.recall_effectiveness_pct ?? 0,
                total_disposition_records: dispositions.length,
                total_destroyed_or_disposed: effectiveness.quantity_destroyed ?? 0,
                total_unresolved_quarantined: (effectiveness.total_affected_units ?? 2400) - (effectiveness.quantity_destroyed ?? 0),
                regulatory_stage: 'SCHEDULE_I_DRAFT',
                foscos_reference_number: 'FOSCOS-REC-2026-MH-08492',
                overall_effectiveness_score_pct: effectiveness.recall_effectiveness_pct ?? 0,
              };

              return (
                <div className="space-y-6 animate-fade-in">
                  {/* Closure Blocker Alert Banner */}
                  {!isEligible && (
                    <div className="p-4 rounded-xl bg-red-950/30 border border-red-500/40 flex items-start gap-3.5">
                      <ShieldAlert className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                      <div className="text-xs font-mono text-red-200/90 leading-relaxed">
                        <p className="font-bold text-red-300 uppercase tracking-wider mb-1">
                          Recall Closure Blocked by IBM Db2 Regulatory Audit Engine
                        </p>
                        <p className="mb-2">
                          A recall cannot be closed while unresolved physical exposure remains unrecovered, consignee acknowledgements are incomplete, or pending disposition executions exist:
                        </p>
                        <ul className="space-y-1 text-red-300">
                          {effectiveness.structured_blockers ? (
                            effectiveness.structured_blockers.map((b: any, idx: number) => (
                              <li key={idx} className="flex items-start gap-2">
                                <span className="font-bold text-red-400 bg-red-950/60 px-1.5 py-0.5 rounded border border-red-500/30 text-[10px] shrink-0">
                                  {b.code}
                                </span>
                                <span>{b.description}</span>
                              </li>
                            ))
                          ) : (
                            blockersList.map((b, idx) => (
                              <li key={idx} className="list-disc ml-5">{b}</li>
                            ))
                          )}
                        </ul>
                      </div>
                    </div>
                  )}

                  {/* 12 Statutory Effectiveness Metrics Grid */}
                  <div className="p-5 rounded-2xl bg-[#0c131d] border border-white/8 space-y-4">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-white/8 pb-3">
                      <div>
                        <h3 className="text-sm font-bold font-mono text-white flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-[#23cad2]" />
                          <span>STATUTORY POST-RECALL REPORTING METRICS (12 INDICATORS)</span>
                        </h3>
                        <p className="text-xs font-mono text-white/50 mt-0.5">
                          Food Safety and Standards (Food Recall Procedure) Regulations, 2017 - Regulation 12
                        </p>
                      </div>
                      <div className="text-xs font-mono text-white/70">
                        Overall Effectiveness Score: <strong className="text-emerald-400 font-bold">{Number(pMetrics.overall_effectiveness_score_pct ?? 0).toFixed(1)}%</strong>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs font-mono">
                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">1. Total Exposed Units</span>
                        <p className="text-base font-bold text-white mt-1">{pMetrics.total_exposed_units}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">2. Total Recovered Units</span>
                        <p className="text-base font-bold text-emerald-400 mt-1">{pMetrics.total_recovered_units}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">3. Product Recovery %</span>
                        <p className="text-base font-bold text-[#8ef5e6] mt-1">{Number(pMetrics.product_recovery_rate_pct ?? 0).toFixed(1)}%</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">4. Consignees Notified</span>
                        <p className="text-base font-bold text-white mt-1">{pMetrics.total_consignees_notified}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">5. Consignees Acknowledged</span>
                        <p className="text-base font-bold text-emerald-400 mt-1">{pMetrics.total_consignees_acknowledged}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">6. Consignee Response %</span>
                        <p className="text-base font-bold text-[#8ef5e6] mt-1">{Number(pMetrics.consignee_response_rate_pct ?? 0).toFixed(1)}%</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">7. Destroyed / Disposed Units</span>
                        <p className="text-base font-bold text-white mt-1">{pMetrics.total_destroyed_or_disposed}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">8. Unresolved Quarantined</span>
                        <p className="text-base font-bold text-amber-300 mt-1">{pMetrics.total_unresolved_quarantined}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">9. 24hr Alert Deadline</span>
                        <p className="text-xs font-bold text-white/70 mt-1">{effectiveness.statutory_24hr_deadline || '2026-11-10T15:36:48'}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">10. 30-Day Follow-Up Deadline</span>
                        <p className="text-xs font-bold text-white/70 mt-1">{effectiveness.statutory_30day_followup_deadline || '2026-12-09T15:36:48'}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">11. Regulatory FoSCoS Stage</span>
                        <p className="text-xs font-bold text-white mt-1">{pMetrics.regulatory_stage}</p>
                      </div>

                      <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6">
                        <span className="text-white/40 uppercase text-[10px]">12. FoSCoS Portal Ref</span>
                        <p className="text-xs font-bold text-[#8ef5e6] mt-1">{pMetrics.foscos_reference_number || 'PENDING'}</p>
                      </div>
                    </div>

                    {/* Closure Action Bar */}
                    <div className="pt-4 border-t border-white/8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                      <div className="text-xs font-mono text-white/50 max-w-xl">
                        <strong>Audit Requirement:</strong> Final recall closure requires zero unaccounted finished goods in retail circulation and 100% consignee acknowledgement.
                      </div>
                      <button
                        onClick={handleAttemptClose}
                        disabled={!isEligible}
                        className={`px-5 py-2.5 rounded-xl font-mono text-xs font-bold tracking-wider uppercase transition-all flex items-center gap-2 cursor-pointer ${
                          isEligible
                            ? 'bg-emerald-500 hover:bg-emerald-400 text-[#041620] shadow-[0_0_20px_rgba(16,185,129,0.4)]'
                            : 'bg-white/5 text-white/30 border border-white/10 cursor-not-allowed'
                        }`}
                      >
                        <Lock className="w-4 h-4" />
                        <span>OFFICIALLY CLOSE RECALL INCIDENT</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })()}
          </>
        )}
      </div>

      {/* MODAL 1: COMMUNICATION STATUS ADVANCE */}
      {selectedComm && commActionModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-[#0d141e] border border-white/10 p-6 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="font-bold text-white text-sm">
                Advance Notice: {selectedComm.recipient_entity_name}
              </h3>
              <button onClick={() => setCommActionModal(null)} className="text-white/40 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-white/70">
              Current Status: <strong className="text-white">{selectedComm.status}</strong>
            </p>

            {commActionModal === 'APPROVE' && (
              <div className="space-y-3">
                <p className="text-blue-300">
                  Confirm Human Operator approval to authorize this statutory recall communication.
                </p>
                <button
                  onClick={() => handleUpdateComm('APPROVED')}
                  className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold"
                >
                  CONFIRM APPROVAL
                </button>
              </div>
            )}

            {commActionModal === 'SEND' && (
              <div className="space-y-3">
                <p className="text-[#8ef5e6]">
                  Record dispatch through secure EDI/Email transmission channel.
                </p>
                <button
                  onClick={() => handleUpdateComm('SENT')}
                  className="w-full py-2 rounded-lg bg-[#23cad2] hover:bg-[#1dbec6] text-[#061826] font-bold"
                >
                  CONFIRM DISPATCH (SENT)
                </button>
              </div>
            )}

            {commActionModal === 'ACKNOWLEDGE' && (
              <div className="space-y-3">
                <p className="text-emerald-300">
                  Record official consignee receipt and quarantine acknowledgement.
                </p>
                <div>
                  <label className="text-white/60 block mb-1">Delivery / Receipt Reference:</label>
                  <input
                    type="text"
                    value={commDeliveryRef}
                    onChange={(e) => setCommDeliveryRef(e.target.value)}
                    placeholder="e.g. ACK-FM-NAGPUR-098"
                    className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  />
                </div>
                <button
                  onClick={() => handleUpdateComm('ACKNOWLEDGED')}
                  className="w-full py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
                >
                  CONFIRM ACKNOWLEDGEMENT
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* MODAL 2: LOGISTICS INTERVENTION UPDATE */}
      {interventionModal && selectedIntervention && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-[#0d141e] border border-white/10 p-6 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="font-bold text-white text-sm">
                Update Logistics Interception ({selectedIntervention.shipment_id})
              </h3>
              <button onClick={() => setInterventionModal(false)} className="text-white/40 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-white/60 block mb-1">New Carrier Interception Status:</label>
                <select
                  value={interventionNewStatus}
                  onChange={(e) => setInterventionNewStatus(e.target.value)}
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                >
                  <option value="CARRIER_ACKNOWLEDGED">CARRIER_ACKNOWLEDGED (Carrier driver reached)</option>
                  <option value="INTERCEPTION_CONFIRMED">INTERCEPTION_CONFIRMED (Vehicle halted en route)</option>
                  <option value="RETURNED_TO_WAREHOUSE">RETURNED_TO_WAREHOUSE (Returned to FAC-PUN dock)</option>
                  <option value="INTERCEPTION_FAILED">INTERCEPTION_FAILED (Delivered prior to halt)</option>
                </select>
              </div>

              <div>
                <label className="text-white/60 block mb-1">Last Known Cargo Location:</label>
                <input
                  type="text"
                  value={interventionLocation}
                  onChange={(e) => setInterventionLocation(e.target.value)}
                  placeholder="e.g. Pune Expressway KM 48 Checkpoint"
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                />
              </div>

              <div>
                <label className="text-white/60 block mb-1">Physical Units Recovered / Secured:</label>
                <input
                  type="number"
                  value={interventionRecoveredQty}
                  onChange={(e) => setInterventionRecoveredQty(Number(e.target.value))}
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                />
              </div>

              <div>
                <label className="text-white/60 block mb-1">Intervention & Driver Verification Notes:</label>
                <textarea
                  value={interventionNotes}
                  onChange={(e) => setInterventionNotes(e.target.value)}
                  rows={2}
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setInterventionModal(false)}
                  className="px-4 py-2 rounded-lg bg-white/5 text-white/60 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleUpdateIntervention}
                  className="px-4 py-2 rounded-lg bg-[#23cad2] text-[#061826] font-bold hover:bg-[#1dbec6]"
                >
                  SAVE INTERVENTION
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: RECORD RECOVERY FORM */}
      {recoveryModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleRecordRecovery} className="w-full max-w-lg rounded-2xl bg-[#0d141e] border border-white/10 p-6 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="font-bold text-white text-sm">
                Record Physical Product Recovery
              </h3>
              <button type="button" onClick={() => setRecoveryModal(false)} className="text-white/40 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-white/60 block mb-1">Target Lot:</label>
                  <select
                    value={recLotId}
                    onChange={(e) => setRecLotId(e.target.value)}
                    className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  >
                    <option value="FIN-401">FIN-401 (Organic Baby Spinach 250g)</option>
                    <option value="FIN-402">FIN-402 (Spinach Salad Bowl 300g)</option>
                    <option value="FIN-403">FIN-403 (Green Power Smoothie 500ml)</option>
                  </select>
                </div>

                <div>
                  <label className="text-white/60 block mb-1">Source Location Type:</label>
                  <select
                    value={recLocationType}
                    onChange={(e) => setRecLocationType(e.target.value)}
                    className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  >
                    <option value="RETAILER">RETAILER (Store return)</option>
                    <option value="WAREHOUSE">WAREHOUSE (Internal dock)</option>
                    <option value="TRANSIT">TRANSIT (Intercepted en route)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-white/60 block mb-1">Source Entity / Facility:</label>
                <input
                  type="text"
                  value={recEntityName}
                  onChange={(e) => setRecEntityName(e.target.value)}
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-white/60 block mb-1">Quantity Recovered (Units):</label>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={recQuantity}
                    onChange={(e) => setRecQuantity(Number(e.target.value))}
                    className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                    required
                  />
                </div>

                <div>
                  <label className="text-white/60 block mb-1">Verification Method:</label>
                  <select
                    value={recVerificationMethod}
                    onChange={(e) => setRecVerificationMethod(e.target.value)}
                    className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  >
                    <option value="BARCODE_SCAN">BARCODE_SCAN</option>
                    <option value="PHYSICAL_AUDIT">PHYSICAL_AUDIT</option>
                    <option value="WEIGHT_CHECK">WEIGHT_CHECK</option>
                    <option value="SEAL_VERIFICATION">SEAL_VERIFICATION</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-white/60 block mb-1">Audit Notes:</label>
                <textarea
                  value={recNotes}
                  onChange={(e) => setRecNotes(e.target.value)}
                  rows={2}
                  placeholder="Verification notes and storage bay..."
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setRecoveryModal(false)}
                  className="px-4 py-2 rounded-lg bg-white/5 text-white/60 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-[#23cad2] text-[#061826] font-bold hover:bg-[#1dbec6]"
                >
                  RECORD RECOVERY
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* MODAL 4: PROPOSE DISPOSITION */}
      {dispositionModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleProposeDisposition} className="w-full max-w-lg rounded-2xl bg-[#0d141e] border border-white/10 p-6 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="font-bold text-white text-sm">
                Propose Product Disposition / Destruction
              </h3>
              <button type="button" onClick={() => setDispositionModal(false)} className="text-white/40 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-white/60 block mb-1">Target Lot:</label>
                  <select
                    value={dispLotId}
                    onChange={(e) => setDispLotId(e.target.value)}
                    className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  >
                    <option value="FIN-401">FIN-401 (Finished Goods)</option>
                    <option value="FIN-402">FIN-402 (Finished Goods)</option>
                    <option value="FIN-403">FIN-403 (Finished Goods)</option>
                    <option value="RAW-204">RAW-204 (Quarantined Raw Material)</option>
                  </select>
                </div>

                <div>
                  <label className="text-white/60 block mb-1">Disposition Pathway:</label>
                  <select
                    value={dispType}
                    onChange={(e) => setDispType(e.target.value)}
                    className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  >
                    <option value="DESTRUCTION">DESTRUCTION (Incineration / Landfill)</option>
                    <option value="CONTINUED_QUARANTINE">CONTINUED_QUARANTINE (Locked Bay)</option>
                    <option value="RETURN_TO_SUPPLIER">RETURN_TO_SUPPLIER (GreenLeaf Foods)</option>
                    <option value="AWAITING_AUTHORITY_INSTRUCTIONS">AWAITING_AUTHORITY_INSTRUCTIONS</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-white/60 block mb-1">Quantity:</label>
                <input
                  type="number"
                  min="1"
                  value={dispQty}
                  onChange={(e) => setDispQty(Number(e.target.value))}
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  required
                />
              </div>

              <div>
                <label className="text-white/60 block mb-1">Regulatory Reason:</label>
                <input
                  type="text"
                  value={dispReason}
                  onChange={(e) => setDispReason(e.target.value)}
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  required
                />
              </div>

              <div>
                <label className="text-white/60 block mb-1">Proposed Destruction / Safe Handling Method:</label>
                <textarea
                  value={dispMethod}
                  onChange={(e) => setDispMethod(e.target.value)}
                  rows={2}
                  className="w-full bg-[#070b10] border border-white/15 rounded p-2 text-white"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setDispositionModal(false)}
                  className="px-4 py-2 rounded-lg bg-white/5 text-white/60 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-[#23cad2] text-[#061826] font-bold hover:bg-[#1dbec6]"
                >
                  SUBMIT FOR APPROVAL
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
