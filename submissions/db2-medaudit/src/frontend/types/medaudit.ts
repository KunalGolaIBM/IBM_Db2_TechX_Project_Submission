export type NecessityTier = 'essential' | 'conditional' | 'unwarranted';

export interface DiagnosticTestItem {
  id: string;
  testCode: string;
  testName: string;
  category: 'Radiology' | 'Biochemistry' | 'Pathology' | 'Genetics' | 'Cardiology';
  orderedPrice: number;
  benchmarkPrice: number;
  necessityTier: NecessityTier;
  clinicalReason: string;
  guidelineReference: string;
  isLabCommissionFlagged: boolean;
  commissionPct?: number;
  potentialKickbackAmount?: number;
  safeAlternativeRecommendation?: string;
}

export interface PatientPrescription {
  patientName: string;
  age: number;
  gender: 'Female' | 'Male' | 'Other';
  chiefComplaint: string;
  symptomDuration: string;
  vitalsAndNotes: string;
  doctorName: string;
  doctorSpecialty: string;
  hospitalName: string;
  recommendedLabName: string;
  tests: Array<{
    testName: string;
    category: 'Radiology' | 'Biochemistry' | 'Pathology' | 'Genetics' | 'Cardiology';
    price: number;
  }>;
}

export interface ClinicalGuideline {
  guidelineId: string;
  conditionCode: string;
  conditionName: string;
  authority: string; // e.g. WHO, NICE, ICMR, American College of Physicians
  indicatedTests: string[];
  conditionalTests: string[];
  unwarrantedOrContraindicated: string[];
  clinicalRationale: string;
}

export interface DoctorProfile {
  doctorId: string;
  name: string;
  specialty: string;
  hospital: string;
  suspicionScore: number; // 0 - 100
  activeContractsCount: number;
  totalPrescriptionsAudited: number;
  unnecessaryPrescriptionRate: number; // percentage
}

export interface DiagnosticLab {
  labId: string;
  name: string;
  accreditation: 'NABL' | 'CAP' | 'ISO 15189' | 'Unaccredited';
  city: string;
  avgMarkupPct: number;
  activeKickbackContracts: number;
}

export interface LabCommissionContract {
  contractId: string;
  doctorId: string;
  doctorName: string;
  labId: string;
  labName: string;
  testCategory: string;
  commissionPct: number;
  kickbackType: 'Direct Fee Per Referral' | 'End-of-Month Volume Rebate' | 'Sponsored Conference / Gift';
  lastAuditDate: string;
}

export interface AuditReport {
  auditId: string;
  timestamp: string;
  patientName: string;
  conditionDetected: string;
  totalTestsOrdered: number;
  totalOrderedCost: number;
  justifiedCost: number;
  unwarrantedCost: number;
  potentialSavings: number;
  kickbackRiskLevel: 'High Risk' | 'Moderate Risk' | 'Low Risk / Clean';
  executiveSummary: string;
  clinicalJustification: string;
  testEvaluations: DiagnosticTestItem[];
  patientActionSteps: string[];
  alternativeLabs: Array<{
    labName: string;
    accreditation: string;
    estimatedCost: number;
    distance: string;
    savings: number;
  }>;
}

export interface DB2ConnectionConfig {
  host: string;
  port: number;
  database: string;
  username: string;
  password?: string;
  ssl: boolean;
  status: 'connected' | 'disconnected' | 'testing' | 'simulated';
  lastPingMs?: number;
}
