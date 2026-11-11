export interface Internship {
  id: string;
  slug: string;
  company: string;
  companyLogo?: string;
  role: string;
  location: string;
  locationType: "remote" | "hybrid" | "onsite";
  stipend: string;
  duration: string;
  isPaid: boolean;
  deadline: string;
  skills: string[];
  description: string;
  tags: string[];
  applyUrl: string;
  eligibleBatch?: string;
  isNew?: boolean;
}
