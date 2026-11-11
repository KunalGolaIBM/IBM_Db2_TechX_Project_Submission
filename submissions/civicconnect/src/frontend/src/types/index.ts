export type UserRole = 'citizen' | 'admin' | 'staff';

export interface UserProfile {
  uid: string;
  name: string;
  email: string;
  role: UserRole;
  departmentId?: string;
  departmentName?: string;
  createdAt: string;
}

export type ComplaintStatus =
  | 'Submitted'
  | 'Under Review'
  | 'Assigned'
  | 'In Progress'
  | 'Resolved'
  | 'Rejected'
  | 'Reopened';

export type ComplaintPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface Complaint {
  id: string; // Firestore document ID
  complaintId: string; // Human-readable unique ID, e.g. CCMS-2026-0001
  userId: string;
  citizenName: string;
  citizenEmail: string;
  title: string;
  description: string;
  category: string;
  departmentId?: string;
  departmentName?: string;
  location: string;
  landmark?: string;
  imageUrl?: string;
  priority: ComplaintPriority;
  status: ComplaintStatus;
  rejectionReason?: string;
  reopenReason?: string;
  resolutionProofUrl?: string;
  resolutionNotes?: string;
  aiSummary?: string;
  aiKeywords?: string[];
  createdAt: string;
  updatedAt: string;
  resolvedAt?: string;
}

export interface ComplaintUpdate {
  id: string;
  complaintId: string;
  previousStatus: string;
  newStatus: string;
  updatedBy: string;
  updatedByUid: string;
  role: string;
  note: string;
  timestamp: string;
}

export interface Department {
  id: string;
  departmentId: string;
  name: string;
  description: string;
  active: boolean;
  staffCount?: number;
  suggestedCategories?: string[];
}

export interface NotificationItem {
  id: string;
  userId: string;
  title: string;
  message: string;
  complaintId?: string;
  read: boolean;
  createdAt: string;
}

export interface CitizenFeedback {
  id: string;
  complaintId: string;
  userId: string;
  rating: number; // 1 to 5
  comment: string;
  createdAt: string;
}

export interface CategoryInfo {
  name: string;
  defaultDepartment: string;
  description: string;
  iconName: string;
}

export const CIVIC_CATEGORIES: CategoryInfo[] = [
  {
    name: 'Garbage Collection',
    defaultDepartment: 'Sanitation Department',
    description: 'Overflowing dumpsters, uncollected domestic waste, road sweeping',
    iconName: 'Trash2'
  },
  {
    name: 'Road Damage / Potholes',
    defaultDepartment: 'Public Works Department',
    description: 'Deep potholes, broken tarmac, cave-ins, dangerous road craters',
    iconName: 'Construction'
  },
  {
    name: 'Streetlight Problems',
    defaultDepartment: 'Electricity Department',
    description: 'Dark streets, flickering bulbs, damaged electrical poles, open wire hazard',
    iconName: 'Lightbulb'
  },
  {
    name: 'Water Leakage',
    defaultDepartment: 'Water Supply Department',
    description: 'Main pipeline bursts, low pressure, contaminated water, leaking joints',
    iconName: 'Droplets'
  },
  {
    name: 'Drainage and Sewage',
    defaultDepartment: 'Drainage Department',
    description: 'Clogged storm drains, overflowing manholes, foul sewage stagnation',
    iconName: 'Waves'
  },
  {
    name: 'Public Property Damage',
    defaultDepartment: 'Public Works Department',
    description: 'Vandalized public parks, broken benches, damaged bus shelters, signage',
    iconName: 'ShieldAlert'
  },
  {
    name: 'Other Civic Issues',
    defaultDepartment: 'Municipal Administration',
    description: 'Encroachments, noise pollution, stray animals, general municipal issues',
    iconName: 'HelpCircle'
  }
];

export const DEFAULT_DEPARTMENTS: Omit<Department, 'id'>[] = [
  {
    departmentId: 'DEPT-SAN',
    name: 'Sanitation Department',
    description: 'Solid waste management, garbage clearance, and urban sanitation drives.',
    active: true,
    suggestedCategories: ['Garbage Collection']
  },
  {
    departmentId: 'DEPT-PWD',
    name: 'Public Works Department',
    description: 'Road repairs, civic infrastructure, public structures, and pavements.',
    active: true,
    suggestedCategories: ['Road Damage / Potholes', 'Public Property Damage']
  },
  {
    departmentId: 'DEPT-ELEC',
    name: 'Electricity Department',
    description: 'Streetlight maintenance, municipal electrical poles, and public illumination.',
    active: true,
    suggestedCategories: ['Streetlight Problems']
  },
  {
    departmentId: 'DEPT-WATER',
    name: 'Water Supply Department',
    description: 'Drinking water distribution, pipeline leak repairs, and municipal water pressure.',
    active: true,
    suggestedCategories: ['Water Leakage']
  },
  {
    departmentId: 'DEPT-DRAIN',
    name: 'Drainage Department',
    description: 'Stormwater drains, sewer lines, underground drainage, and monsoon flood relief.',
    active: true,
    suggestedCategories: ['Drainage and Sewage']
  },
  {
    departmentId: 'DEPT-ADMIN',
    name: 'Municipal Administration',
    description: 'General civic oversight, multi-department coordination, and public inquiries.',
    active: true,
    suggestedCategories: ['Other Civic Issues']
  }
];
