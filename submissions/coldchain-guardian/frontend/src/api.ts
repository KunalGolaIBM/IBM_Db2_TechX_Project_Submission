const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Dashboard
  getDashboard: () => apiFetch<DashboardStats>('/api/dashboard/'),

  // Products
  getProducts: () => apiFetch<Product[]>('/api/products/'),

  // Shipments
  getShipments: () => apiFetch<Shipment[]>('/api/shipments/'),
  getShipment: (id: number) => apiFetch<Shipment>(`/api/shipments/${id}`),
  getShipmentReadings: (id: number) => apiFetch<SensorReading[]>(`/api/shipments/${id}/readings`),

  // Incidents
  getIncidents: () => apiFetch<Incident[]>('/api/incidents/'),
  getIncident: (id: number) => apiFetch<Incident>(`/api/incidents/${id}`),
  detectIncidents: () => apiFetch<unknown>('/api/incidents/detect', { method: 'POST' }),

  // Recommendations
  getRecommendations: (incidentId?: number) =>
    apiFetch<Recommendation[]>(`/api/recommendations/${incidentId ? `?incident_id=${incidentId}` : ''}`),
  generateRecommendations: (incidentId: number) =>
    apiFetch<Recommendation[]>(`/api/recommendations/generate/${incidentId}`, { method: 'POST' }),
  approveRecommendation: (recId: number, status: 'APPROVED' | 'REJECTED') =>
    apiFetch<Recommendation>(`/api/recommendations/${recId}/approval`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  // Workflow
  runWorkflow: (readingId: number) =>
    apiFetch<WorkflowResult>(`/api/workflow/run/${readingId}`, { method: 'POST' }),

  // CrewAI
  analyseIncident: (incidentId: number) =>
    apiFetch<CrewAnalysisResponse>(`/api/crew/analyse/${incidentId}`, { method: 'POST' }),
};

// Types
export interface DashboardStats {
  products: number;
  shipments: number;
  shipments_in_transit: number;
  open_incidents: number;
  pending_recommendations: number;
  temperature_violations: number;
  risk_distribution: Record<string, number>;
  recent_incidents: Incident[];
  recent_shipments: ShipmentActivity[];
  temperature_trends: TemperatureTrendPoint[];
}

export interface TemperatureTrendPoint {
  reading_id: number;
  shipment_id: number;
  temperature: number;
  recorded_at: string | null;
  product_name: string;
}

export interface ShipmentActivity {
  shipment_id: number;
  product_name: string;
  vehicle_id: string;
  source_location: string;
  destination_location: string;
  shipment_status: string;
  departure_time: string | null;
  expected_arrival: string | null;
}

export interface Product {
  product_id: number;
  product_name: string;
  product_category: string;
  min_temperature: number;
  max_temperature: number;
  sensitivity_level: string;
}

export interface Shipment {
  shipment_id: number;
  product_id: number;
  product_name: string;
  vehicle_id: string;
  source_location: string;
  destination_location: string;
  shipment_status: string;
  departure_time: string | null;
  expected_arrival: string | null;
  // Present on the list endpoint (GET /api/shipments/); omitted by single-get.
  min_temperature?: number | null;
  max_temperature?: number | null;
  latest_temperature?: number | null;
  latest_reading_at?: string | null;
  temperature_violation?: boolean | null;
}

export interface SensorReading {
  reading_id: number;
  shipment_id: number;
  temperature: number;
  humidity: number | null;
  recorded_at: string;
}

export interface Incident {
  incident_id: number;
  shipment_id: number;
  incident_type: string;
  severity: string;
  description: string;
  status: string;
  created_at: string | null;
  risk_assessment_id: number | null;
  risk_score: number | null;
  risk_level: string | null;
}

export interface Recommendation {
  recommendation_id: number;
  incident_id: number;
  action: string;
  justification: string;
  priority: number;
  approval_status: string | null;
  created_at: string;
}

export interface WorkflowResult {
  reading_id: number;
  workflow_status: string;
  violation_detected: boolean;
  temperature_status: string | null;
  temperature_deviation: number | null;
  incident_id: number | null;
  incident_created: boolean;
  severity: string | null;
  risk_assessment_id: number | null;
  risk_score: number | null;
  risk_level: string | null;
  risk_explanation: string | null;
  risk_reused: boolean;
  crew_analysis: CrewFindings | null;
  crew_status: string | null;
  recommendations: Recommendation[];
  recommendation_ids: number[];
  recommendations_generated: boolean;
  error: string | null;
}

export interface SuggestedAction {
  action: string;
  justification: string;
  priority: number;
}

// Structured findings produced by the CrewAI node (or its deterministic fallback).
// The numeric deterministic risk score stays authoritative; this is explanatory.
export interface CrewFindings {
  source: string;
  available: boolean;
  reused?: boolean;
  summary: string;
  risk_analyst: string;
  domain_expert: string;
  recommendation_specialist: string;
  potential_product_damage: string;
  possible_causes: string[];
  containment_measures: string[];
  suggested_actions: SuggestedAction[];
  message?: string | null;
  deterministic_risk_score?: number | null;
  deterministic_risk_level?: string | null;
}

// Response of POST /api/crew/analyse/{incident_id}
export interface CrewAnalysisResponse {
  incident_id: number;
  severity: string | null;
  risk_score: number | null;
  risk_level: string | null;
  risk_assessment_id: number | null;
  risk_explanation: string | null;
  temperature_deviation: number | null;
  product_name: string | null;
  product_sensitivity: string | null;
  crew_status: string | null;
  crew_analysis: CrewFindings;
}
