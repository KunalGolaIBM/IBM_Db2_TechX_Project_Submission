export interface SecurityEvent {
  event_id: number;
  event_type: string;
  username: string;
  source_ip: string;
  database_name: string;
  sql_operation: string;
  object_name: string | null;
  status: string;
  event_timestamp: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  event_source: string;
  raw_details: string;
}

export interface SecurityAlert {
  alert_id: number;
  event_id: number;
  alert_name: string;
  description: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  risk_score: number;
  status: string;
  created_at: string;
}

export interface SecurityIncident {
  incident_id: string;
  title: string;
  description: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  risk_score: number;
  status: string;
  assigned_to: string;
  created_at: string;
  updated_at: string;
  ai_summary: string | null;
}

export interface ApprovalRequest {
  approval_id: string;
  incident_id: string;
  proposed_action: string;
  requested_by: string;
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reviewer: string | null;
  reviewed_at: string | null;
  audit_notes: string | null;
}

export interface DashboardMetrics {
  total_events: number;
  total_alerts: number;
  open_incidents: number;
  critical_incidents: number;
  avg_risk_score: number;
}

export interface Db2Status {
  active_mode: 'db2_connected' | 'demo_fallback' | 'error';
  engine: string;
  connected: boolean;
  is_demo_mode: boolean;
  message?: string;
  details?: any;
}
