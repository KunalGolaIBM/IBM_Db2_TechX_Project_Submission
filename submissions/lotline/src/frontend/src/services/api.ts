export interface IncidentDetails {
  incident_id: string;
  source_lot_id: string;
  incident_type: string;
  severity: string;
  description: string;
  reported_by?: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  source_lot_details?: {
    lot_id: string;
    item_name: string;
    lot_type: string;
    supplier_id: string;
    supplier_name: string;
    contact_email?: string;
    country?: string;
    quantity_created: number;
    unit: string;
    status: string;
  };
}

export interface TraceNode {
  lot_id: string;
  item_name: string;
  lot_type: string;
  status: string;
  facility_id?: string;
  quantity?: number;
  unit?: string;
  depth: number;
}

export interface TraceLink {
  parent_lot_id: string;
  child_lot_id: string;
  depth: number;
}

export interface TraceData {
  incident_id: string;
  source_lot_id: string;
  total_downstream_lots: number;
  total_production_levels: number;
  finished_lots_count: number;
  nodes: TraceNode[];
  links: TraceLink[];
}

export interface ExposureCategory {
  label: string;
  quantity: number;
  percentage: number;
}

export interface AffectedBatch {
  lot_id: string;
  item_name: string;
  warehouse_units: number;
  delivered_units: number;
  in_transit_units: number;
  total_units: number;
}

export interface ExposureData {
  incident_id: string;
  total_affected_units: number;
  warehouse_units: number;
  retailer_delivered_units: number;
  in_transit_units: number;
  finished_product_lots_count: number;
  total_downstream_lots_count: number;
  categories: ExposureCategory[];
  affected_batches: AffectedBatch[];
}

export interface Shipment {
  shipment_id: string;
  lot_id: string;
  product_name: string;
  retailer: string;
  quantity: number;
  status: string;
  delivery_date?: string;
  source_facility?: string;
}

export interface RecallAction {
  action_id: string;
  incident_id: string;
  action_type: string;
  target_type: string;
  target_id: string;
  action_description: string;
  status: 'PROPOSED' | 'APPROVED' | 'REJECTED';
  proposed_by?: string;
  approved_by?: string;
  created_at?: string;
  approved_at?: string;
}

export interface AuditRecord {
  audit_id: string;
  incident_id: string;
  action_id?: string;
  entity_type?: string;
  entity_id?: string;
  event_type: string;
  actor: string;
  details?: string;
  created_at?: string;
}

export interface AgentStepResult {
  agent_name: string;
  task_definition: string;
  status: 'COMPLETED' | 'RUNNING' | 'FAILED';
  source_tables: string[];
  findings: Record<string, any>;
  ai_interpretation?: string | null;
  ai_status?: string | null;
  evidence_ids: string[];
  timestamp: string;
  supporting_evidence_refs?: string[];
  limitations_or_missing_info?: string;
  validation_status?: string;
}

export interface GeminiStatus {
  available: boolean;
  model?: string | null;
  status_code?: string;
  rationale?: string | null;
  note: string;
}

export interface AgentWorkflowResult {
  incident_id: string;
  source_lot_id: string;
  steps: AgentStepResult[];
  recommended_actions: RecallAction[];
  evidence: Array<{
    step: string;
    verified_source: string;
    [key: string]: any;
  }>;
  agent_logs: Array<{
    agent: string;
    message: string;
    status?: string;
    timestamp?: string;
  }>;
  gemini_status: GeminiStatus;
  error?: string;
}

const API_BASE = '/api';

export async function fetchDbHealth(): Promise<{ status: string; database: string; host: string }> {
  const res = await fetch(`${API_BASE}/db/health`);
  if (!res.ok) throw new Error('Database health check failed');
  return res.json();
}

export async function fetchIncident(incidentId: string): Promise<IncidentDetails> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`);
  if (!res.ok) throw new Error(`Failed to fetch incident ${incidentId}`);
  return res.json();
}

export async function fetchTrace(incidentId: string): Promise<TraceData> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/trace`);
  if (!res.ok) throw new Error(`Failed to fetch trace for ${incidentId}`);
  return res.json();
}

export async function fetchExposure(incidentId: string): Promise<ExposureData> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/exposure`);
  if (!res.ok) throw new Error(`Failed to fetch exposure for ${incidentId}`);
  return res.json();
}

export async function fetchShipments(incidentId: string): Promise<Shipment[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/shipments`);
  if (!res.ok) throw new Error(`Failed to fetch shipments for ${incidentId}`);
  return res.json();
}

export async function fetchActions(incidentId: string): Promise<RecallAction[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/actions`);
  if (!res.ok) throw new Error(`Failed to fetch actions for ${incidentId}`);
  return res.json();
}

export async function updateActionDecision(
  incidentId: string,
  actionId: string,
  decision: 'APPROVED' | 'REJECTED',
  operatorName = 'Operator (Current Session)',
  notes = ''
): Promise<{ success: boolean; new_status: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/actions/${actionId}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, operator_name: operatorName, notes }),
  });
  if (!res.ok) throw new Error('Failed to update action');
  return res.json();
}

export async function fetchAuditLog(incidentId: string): Promise<AuditRecord[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/audit`);
  if (!res.ok) throw new Error(`Failed to fetch audit log for ${incidentId}`);
  return res.json();
}

export async function runAgentWorkflow(incidentId: string): Promise<AgentWorkflowResult> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/agents/run`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to run agentic workflow');
  return res.json();
}

export async function resetDemoActions(incidentId: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/actions/reset`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to reset demo actions');
  return res.json();
}

export interface DossierPreview {
  incident_id: string;
  source_lot_id: string;
  contaminant: string;
  severity: string;
  supplier_name: string;
  supplier_country: string;
  raw_quantity: number;
  raw_unit: string;
  downstream_batches_count: number;
  production_levels: number;
  finished_goods_units: number;
  warehouse_units: number;
  delivered_units: number;
  transit_units: number;
  actions_total: number;
  actions_approved: number;
  actions_proposed: number;
  actions_rejected: number;
  audit_events_count: number;
  estimated_pages: number;
  fssai_profile_ready: boolean;
  fssai_missing_fields: Array<{ field: string; status: string; action_required: string }>;
  compliance_framework: string;
  legal_notice: string;
}

export async function fetchDossierPreview(incidentId: string): Promise<DossierPreview> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/dossier/preview`);
  if (!res.ok) throw new Error(`Failed to fetch dossier preview for ${incidentId}`);
  return res.json();
}

export async function downloadRecallDossier(
  incidentId: string,
  includeFssai = true,
  operatorName = 'Chief Safety Officer'
): Promise<{ filename: string; sha256: string; reportId: string; sizeBytes: number }> {
  const params = new URLSearchParams({
    include_fssai: String(includeFssai),
    operator_name: operatorName,
  });
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/dossier?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to generate recall dossier: ${res.statusText}`);

  const sha256 = res.headers.get('X-Dossier-SHA256') || '';
  const reportId = res.headers.get('X-Report-ID') || '';
  const sizeBytes = parseInt(res.headers.get('X-Byte-Size') || '0', 10);
  const contentDisposition = res.headers.get('Content-Disposition') || '';
  let filename = `LOTLINE-RECALL-DOSSIER-${incidentId}.pdf`;
  const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
  if (filenameMatch && filenameMatch[1]) {
    filename = filenameMatch[1];
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);

  return { filename, sha256, reportId, sizeBytes };
}

// ==========================================
// PHASE 5: CLOSED-LOOP RECALL EXECUTION TYPES & APIS
// ==========================================

export interface MassReconciliation {
  source_lot_id: string;
  item_name: string;
  unit: string;
  original_quantity: number;
  recorded_wip_consumption: number;
  quarantined_quantity: number;
  accounted_quantity: number;
  unaccounted_quantity: number;
  reconciliation_status: 'RECONCILED' | 'UNRECONCILED' | 'INVESTIGATION_REQUIRED';
  wip_breakdown: Array<{
    wip_lot_id: string;
    fin_lot_id: string;
    quantity_consumed: number;
    unit: string;
  }>;
  notes: string;
}

export interface RecallCommunication {
  comm_id: string;
  incident_id: string;
  recipient_entity_name: string;
  recipient_type: 'RETAILER' | 'DISTRIBUTOR' | 'CARRIER' | 'WAREHOUSE';
  recipient_contact: string;
  channel: 'EMAIL' | 'PORTAL' | 'EDI' | 'PHONE' | 'DIRECT';
  status: 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'SENT' | 'DELIVERED' | 'ACKNOWLEDGED' | 'FAILED' | 'ESCALATED';
  statutory_template_ref: string;
  approved_by?: string;
  approved_at?: string;
  sent_at?: string;
  acknowledged_at?: string;
  delivery_confirmation_ref?: string;
  escalation_reason?: string;
  operator_notes?: string;
  created_at: string;
}

export interface LogisticsIntervention {
  intervention_id: string;
  incident_id: string;
  shipment_id: string;
  carrier_name: string;
  vehicle_tracking_ref: string;
  current_status: 'NOT_INITIATED' | 'PENDING_APPROVAL' | 'REQUEST_SENT' | 'CARRIER_ACKNOWLEDGED' | 'INTERCEPTION_CONFIRMED' | 'INTERCEPTION_FAILED' | 'RETURNED_TO_WAREHOUSE';
  carrier_contact_person?: string;
  carrier_acknowledged_at?: string;
  carrier_action_taken?: string;
  last_known_cargo_location?: string;
  recovered_quantity: number;
  returned_facility_id?: string;
  intervention_notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ProductRecovery {
  recovery_id: string;
  incident_id: string;
  lot_id: string;
  source_location_type: 'WAREHOUSE' | 'RETAILER' | 'TRANSIT' | 'CUSTOMER_RETURN';
  source_entity_name: string;
  quantity_recovered: number;
  unit_of_measure: string;
  storage_facility_id: string;
  verification_method: 'BARCODE_SCAN' | 'PHYSICAL_AUDIT' | 'WEIGHT_CHECK' | 'SEAL_VERIFICATION';
  verified_by_operator: string;
  verified_at: string;
  notes?: string;
}

export interface BatchRecoverySummary {
  lot_id: string;
  item_name: string;
  total_exposed_units: number;
  warehouse_quarantined?: number;
  warehouse_recovered?: number;
  warehouse_contained_units?: number;
  warehouse_containment_pct?: number;
  market_distributed_units?: number;
  retailer_returned?: number;
  retailer_recovered?: number;
  retailer_returned_units?: number;
  transit_intercepted?: number;
  transit_recovered?: number;
  transit_intercepted_units?: number;
  total_recovered_units: number;
  market_recovered_units?: number;
  unrecovered_units?: number;
  outstanding_units?: number;
  market_outstanding_units?: number;
  recovery_rate_pct: number;
  market_recovery_pct?: number;
}

export interface RecoveryReconciliation {
  incident_id: string;
  total_affected_units?: number;
  aggregate_exposed_units: number;
  total_recovered_units?: number;
  aggregate_recovered_units: number;
  total_outstanding_units?: number;
  aggregate_unrecovered_units: number;
  overall_recovery_pct?: number;
  aggregate_recovery_pct: number;
  total_exposed_units?: number;
  warehouse_contained_units?: number;
  warehouse_containment_pct?: number;
  market_distributed_units?: number;
  market_recovered_units?: number;
  market_outstanding_units?: number;
  market_recovery_pct?: number;
  batches?: BatchRecoverySummary[];
  batch_breakdown?: BatchRecoverySummary[];
  audit_count: number;
}

export interface ProductDisposition {
  disposition_id: string;
  incident_id: string;
  lot_id: string;
  lot_type: string;
  quantity: number;
  unit_of_measure: string;
  quantity_unit?: string;
  disposition_type: 'CONTINUED_QUARANTINE' | 'RETURN_TO_SUPPLIER' | 'REPROCESSING' | 'DESTRUCTION' | 'AWAITING_AUTHORITY_INSTRUCTIONS';
  status: 'PROPOSED' | 'APPROVED' | 'EXECUTED' | 'REJECTED';
  lifecycle_status?: string;
  evidence_status?: string;
  is_synthetic_fixture?: boolean;
  is_fixture?: boolean;
  reason: string;
  proposed_method: string;
  authority_permission_ref?: string;
  authorized_by_operator?: string;
  authorized_at?: string;
  witnessed_by_operator?: string;
  destruction_facility_ref?: string;
  certificate_of_destruction_ref?: string;
  executed_at?: string;
  evidence_attachment?: string;
  created_at: string;
}

export interface FssaiChecklistItem {
  item_number: number;
  title: string;
  statutory_ref: string;
  status: 'Db2 verified' | 'Manually required' | 'Evidence missing' | 'Not applicable' | 'Awaiting human verification';
  db2_value?: string;
  compliance_notes: string;
}

export interface FssaiChecklist {
  incident_id: string;
  fssai_awareness_timestamp: string;
  statutory_deadline_timestamp: string;
  hours_remaining: number;
  deadline_status: 'WITHIN_DEADLINE' | 'EXPIRED' | 'CRITICAL_WINDOW';
  checklist_items: FssaiChecklistItem[];
  total_items: number;
  verified_count: number;
  manual_count: number;
  missing_count: number;
}

export interface RegulatorySubmission {
  submission_id: string;
  incident_id: string;
  regulatory_authority: string;
  portal_name: string;
  current_stage: 'SCHEDULE_I_DRAFT' | 'MISSING_INFO_REVIEW' | 'OPERATOR_VERIFIED' | 'INTERNAL_APPROVED' | 'SUBMITTED_TO_FOSCOS' | 'AUTHORITY_QUERY' | 'CLOSED';
  foscos_recall_ref?: string;
  foscos_reference_label?: string;
  is_official_portal_receipt?: boolean;
  target_submission_deadline: string;
  submitted_by_operator?: string;
  submitted_at?: string;
  authority_acknowledgement_ref?: string;
  authority_feedback?: string;
  pending_corrections?: string;
  created_at: string;
  updated_at: string;
}

export interface RecallEffectiveness {
  incident_id: string;
  source_lot_id?: string;
  incident_created_at?: string;
  statutory_24hr_deadline?: string;
  statutory_30day_followup_deadline?: string;
  hours_elapsed?: number;
  total_affected_units?: number;
  total_distributed_units?: number;
  orgs_identified?: number;
  orgs_notified?: number;
  orgs_acknowledged?: number;
  quantity_recovered?: number;
  quantity_destroyed?: number;
  quantity_destroyed_kg?: number;
  quantity_destroyed_units?: number;
  quantity_outstanding?: number;
  recall_effectiveness_pct?: number;
  consignee_response_pct?: number;
  recovery_pct?: number;
  unresolved_actions_count?: number;
  can_close_recall?: boolean;
  closure_blockers?: string[];
  blocker_codes?: string[];
  structured_blockers?: Array<{
    code: string;
    description: string;
    affected_quantity?: number;
    unit?: string;
    reference_id?: string;
    category?: string;
  }>;
  report_metrics?: Array<{ metric: string; value: string }>;
  post_recall_metrics?: {
    total_consignees_notified: number;
    total_consignees_acknowledged: number;
    consignee_response_rate_pct: number;
    total_exposed_units: number;
    total_recovered_units: number;
    product_recovery_rate_pct: number;
    total_disposition_records: number;
    total_destroyed_or_disposed: number;
    total_unresolved_quarantined: number;
    regulatory_stage: string;
    foscos_reference_number?: string;
    overall_effectiveness_score_pct: number;
  };
  closure_eligible?: boolean;
  blockers?: string[];
}

export async function fetchRawMassReconciliation(incidentId: string): Promise<MassReconciliation> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/reconciliation/raw`);
  if (!res.ok) throw new Error(`Failed to fetch raw mass reconciliation for ${incidentId}`);
  return res.json();
}

export async function fetchCommunications(incidentId: string): Promise<RecallCommunication[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/communications`);
  if (!res.ok) throw new Error(`Failed to fetch communications for ${incidentId}`);
  return res.json();
}

export async function updateCommunicationStatus(
  incidentId: string,
  commId: string,
  newStatus: string,
  operatorName = 'Regulatory Compliance Officer',
  notes = '',
  deliveryConfirmation = ''
): Promise<{ success: boolean; comm_id: string; new_status: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/communications/${commId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      new_status: newStatus,
      operator_name: operatorName,
      notes,
      delivery_confirmation: deliveryConfirmation,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update communication status' }));
    throw new Error(err.detail || 'Failed to update communication status');
  }
  return res.json();
}

export async function fetchLogisticsInterventions(incidentId: string): Promise<LogisticsIntervention[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/logistics/interventions`);
  if (!res.ok) throw new Error(`Failed to fetch logistics interventions for ${incidentId}`);
  return res.json();
}

export async function updateLogisticsIntervention(
  incidentId: string,
  interventionId: string,
  newStatus: string,
  operatorName = 'Logistics Operations Lead',
  cargoLocation = '',
  interceptionNotes = '',
  recoveredQuantity = 0,
  returnedFacilityId = 'FAC-PUN'
): Promise<{ success: boolean; intervention_id: string; new_status: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/logistics/interventions/${interventionId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      new_status: newStatus,
      operator_name: operatorName,
      cargo_location: cargoLocation,
      interception_notes: interceptionNotes,
      recovered_quantity: recoveredQuantity,
      returned_facility_id: returnedFacilityId,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update logistics intervention' }));
    throw new Error(err.detail || 'Failed to update logistics intervention');
  }
  return res.json();
}

export async function fetchProductRecoveries(incidentId: string): Promise<ProductRecovery[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/recoveries`);
  if (!res.ok) throw new Error(`Failed to fetch product recoveries for ${incidentId}`);
  return res.json();
}

export async function recordProductRecovery(
  incidentId: string,
  payload: {
    lot_id: string;
    source_location_type: string;
    source_entity_name: string;
    quantity_recovered: number;
    unit_of_measure?: string;
    storage_facility_id?: string;
    verification_method?: string;
    operator_name?: string;
    notes?: string;
  }
): Promise<{ success: boolean; recovery_id: string; lot_id: string; quantity_recovered: number }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/recoveries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to record product recovery' }));
    throw new Error(err.detail || 'Failed to record product recovery');
  }
  return res.json();
}

export async function fetchRecoveryReconciliation(incidentId: string): Promise<RecoveryReconciliation> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/recoveries/reconciliation`);
  if (!res.ok) throw new Error(`Failed to fetch recovery reconciliation for ${incidentId}`);
  return res.json();
}

export async function fetchProductDispositions(incidentId: string): Promise<ProductDisposition[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/dispositions`);
  if (!res.ok) throw new Error(`Failed to fetch product dispositions for ${incidentId}`);
  return res.json();
}

export async function proposeProductDisposition(
  incidentId: string,
  payload: {
    lot_id: string;
    lot_type: string;
    quantity: number;
    unit_of_measure: string;
    disposition_type: string;
    reason: string;
    proposed_method: string;
    authority_permission_ref?: string;
    operator_name?: string;
    evidence_attachment?: string;
  }
): Promise<{ success: boolean; disposition_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/dispositions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to propose disposition' }));
    throw new Error(err.detail || 'Failed to propose disposition');
  }
  return res.json();
}

export async function approveProductDisposition(
  incidentId: string,
  dispositionId: string,
  operatorName = 'Lead Product Safety Officer',
  notes = ''
): Promise<{ success: boolean; disposition_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/dispositions/${dispositionId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_name: operatorName, notes }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to approve disposition' }));
    throw new Error(err.detail || 'Failed to approve disposition');
  }
  return res.json();
}

export async function executeProductDisposition(
  incidentId: string,
  dispositionId: string,
  operatorName = 'Plant Operations Lead',
  evidenceAttachment = 'CERT-INC-001-DISP.pdf'
): Promise<{ success: boolean; disposition_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/dispositions/${dispositionId}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_name: operatorName, evidence_attachment: evidenceAttachment }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to execute disposition' }));
    throw new Error(err.detail || 'Failed to execute disposition');
  }
  return res.json();
}

export async function fetchFssaiChecklist(incidentId: string): Promise<FssaiChecklist> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/fssai/checklist`);
  if (!res.ok) throw new Error(`Failed to fetch FSSAI checklist for ${incidentId}`);
  return res.json();
}

export async function fetchRegulatorySubmissions(incidentId: string): Promise<RegulatorySubmission[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/fssai/submissions`);
  if (!res.ok) throw new Error(`Failed to fetch regulatory submissions for ${incidentId}`);
  return res.json();
}

export async function updateRegulatorySubmissionStage(
  incidentId: string,
  submissionId: string,
  newStage: string,
  operatorName = 'Regulatory Compliance Officer',
  foscosRecallRef = '',
  authorityFeedback = '',
  pendingCorrections = ''
): Promise<{ success: boolean; submission_id: string; new_stage: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/fssai/submissions/${submissionId}/stage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      new_stage: newStage,
      operator_name: operatorName,
      foscos_recall_ref: foscosRecallRef,
      authority_feedback: authorityFeedback,
      pending_corrections: pendingCorrections,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update regulatory submission stage' }));
    throw new Error(err.detail || 'Failed to update regulatory submission stage');
  }
  return res.json();
}

export async function fetchRecallEffectiveness(incidentId: string): Promise<RecallEffectiveness> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/effectiveness`);
  if (!res.ok) throw new Error(`Failed to fetch recall effectiveness for ${incidentId}`);
  return res.json();
}

export async function attemptCloseRecall(
  incidentId: string,
  operatorName = 'Chief Compliance Officer',
  justification = 'All recall parameters and recovery thresholds verified per FSSAI regulations.'
): Promise<{ success: boolean; incident_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/close`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_name: operatorName, justification }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Recall closure prerequisites not met' }));
    throw new Error(err.detail || 'Recall closure prerequisites not met');
  }
  return res.json();
}



