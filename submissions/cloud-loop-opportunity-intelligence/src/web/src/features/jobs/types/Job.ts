export interface Job {
  id: string;
  slug: string;
  company: string;
  companyLogo?: string;
  role: string;
  location: string;
  locationType: "remote" | "hybrid" | "onsite";
  salaryRange: string;
  experience: string;
  category: string;
  skills: string[];
  isEasyApply: boolean;
  deadline: string;
  posted: string;
  description: string;
  tags: string[];
  applyUrl: string;
  eligibleBatch?: string;
  isNew?: boolean;
}
