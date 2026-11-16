export type UserRole = 'resident' | 'responder' | 'admin' | 'guardian';

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone?: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  emergency_notes?: string;
  address?: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string;
  full_name: string;
  role: UserRole;
}

export interface TrustedContact {
  id: number;
  user_id: number;
  name: string;
  relationship: string;
  phone: string;
  email?: string;
  can_receive_sos: boolean;
  can_track_location: boolean;
  created_at: string;
}

export type IncidentPriority = 'P1_CRITICAL' | 'P2_HIGH' | 'P3_MODERATE' | 'P4_ADVISORY';
export type IncidentStatus = 
  | 'reported' 
  | 'acknowledged' 
  | 'responder_en_route' 
  | 'on_scene' 
  | 'resolving' 
  | 'resolved' 
  | 'false_alarm';

export interface IncidentStatusHistory {
  id: number;
  status: IncidentStatus;
  notes?: string;
  updated_by_name?: string;
  created_at: string;
}

export interface Incident {
  id: number;
  reference_code: string;
  reporter_id: number;
  reporter_name?: string;
  title: string;
  description: string;
  incident_type: string;
  priority: IncidentPriority;
  status: IncidentStatus;
  location_address?: string;
  latitude?: number;
  longitude?: number;
  assigned_responder_id?: number;
  assigned_responder_name?: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
  status_history: IncidentStatusHistory[];
}

export interface ChildJourney {
  id: number;
  guardian_id: number;
  child_name: string;
  origin: string;
  destination: string;
  expected_arrival_time: string;
  actual_arrival_time?: string;
  status: 'active' | 'completed' | 'delayed' | 'alert_triggered';
  last_check_in?: string;
  notes?: string;
  created_at: string;
}

export interface ElderCheckIn {
  id: number;
  user_id: number;
  user_name?: string;
  scheduled_time: string;
  checked_in_at?: string;
  status: 'pending' | 'completed' | 'missed' | 'flagged';
  wellness_status: 'good' | 'needs_assistance' | 'emergency';
  notes?: string;
  created_at: string;
}

export interface AssistanceRequest {
  id: number;
  user_id: number;
  user_name?: string;
  request_type: string;
  description: string;
  urgency: 'low' | 'medium' | 'high';
  status: 'open' | 'assigned' | 'in_progress' | 'completed';
  assigned_to_name?: string;
  created_at: string;
  resolved_at?: string;
}

export interface CommunityHazard {
  id: number;
  reported_by_id: number;
  title: string;
  hazard_type: string;
  severity: 'low' | 'medium' | 'high';
  address: string;
  latitude?: number;
  longitude?: number;
  status: 'active' | 'verified' | 'resolved';
  created_at: string;
}

export interface PriorityResponseTime {
  priority: string;
  incidents: number;
  acknowledged: number;
  avg_ack_minutes: number | null;
  median_ack_minutes: number | null;
  p90_ack_minutes: number | null;
  avg_resolve_minutes: number | null;
  ack_target_minutes: number;
}

export interface IncidentHotspot {
  rank: number;
  location: string;
  incidents: number;
  open_incidents: number;
  last_reported: string;
}

export interface CommunityInsights {
  total_incidents: number;
  active_incidents: number;
  resolved_incidents: number;
  average_response_time_minutes: number | null;
  incidents_by_type: Record<string, number>;
  incidents_by_priority: Record<string, number>;
  active_hazards: CommunityHazard[];
  safety_health_score: number;
  ai_safety_advisory: string;
  analytics_engine: string;
  window_days: number;
  response_times: PriorityResponseTime[];
  hotspots: IncidentHotspot[];
  incidents_by_hour: Record<string, number>;
  sla_breaches: number;
}

export interface SimilarIncident {
  id: number;
  reference_code: string;
  title: string;
  incident_type: string;
  priority: string;
  status: string;
  location_address?: string | null;
  created_at: string;
  similarity: number;
  same_location: boolean;
}

export interface AIAnalysisResult {
  parsed_category: string;
  extracted_location?: string;
  suggested_priority: IncidentPriority;
  triage_reasoning: string;
  missing_critical_info: string[];
  immediate_safety_checklist: string[];
  retrieved_civic_protocols: Array<{
    title: string;
    source: string;
    protocol_snippet: string;
  }>;
  advisory_notice: string;
}
