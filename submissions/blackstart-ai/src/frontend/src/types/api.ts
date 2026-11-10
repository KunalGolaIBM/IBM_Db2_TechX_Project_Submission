export interface PowerPlant {
  plant_id: number;
  plant_name: string;
  plant_type: string;
  capacity_mw: string | number;
  status: string;
  region: string;
}

export interface Substation {
  substation_id: number;
  substation_name: string;
  voltage_kv: string | number;
  load_mw: string | number;
  status: string;
  region: string;
}

export interface TransmissionLine {
  line_id: number;
  line_name: string;
  from_substation: number;
  to_substation: number;
  capacity_mw: string | number;
  current_load_mw: string | number;
  status: string;
}

export interface GridIncident {
  incident_id: number;
  incident_type: string;
  severity: string;
  location: string;
  description: string;
  status: string;
  detected_at: string;
}

export interface GridOverview {
  plants: PowerPlant[];
  substations: Substation[];
  lines: TransmissionLine[];
  incidents: GridIncident[];
}

export interface OverloadedLine {
  line: string;
  utilization: number;
}

export interface VoltFindings {
  open_incidents: GridIncident[];
  overloaded_lines: OverloadedLine[];
}

export interface LineConnection {
  line: string;
  from: number;
  to: number;
}

export interface PulseFindings {
  substation_count: number;
  transmission_line_count: number;
  online_substations: number;
  line_connections: LineConnection[];
}

export interface CascadeFindings {
  risk_level: string;
  overloaded_line_count: number;
  at_risk_lines: OverloadedLine[];
  simulation_mode: string;
}

export interface GuardianFindings {
  risk_level: string;
  open_incident_count: number;
  critical_alert: boolean;
  assessment: string;
}

export interface AgentFindings {
  volt: VoltFindings;
  pulse: PulseFindings;
  cascade: CascadeFindings;
  guardian: GuardianFindings;
}

export interface AnalysisResult {
  system: string;
  overall_risk: string;
  agents_executed: string[];
  findings: AgentFindings;
  recommendations: string[];
  execution_mode: string;
  data_source: string;
}

export interface HealthResponse {
  status: string;
  application: string;
  version: string;
}

export interface Db2Status {
  connected: boolean;
  message: string;
}

export type LoadState = 'idle' | 'loading' | 'success' | 'error';
export type AnalysisState = 'idle' | 'running' | 'success' | 'error';
