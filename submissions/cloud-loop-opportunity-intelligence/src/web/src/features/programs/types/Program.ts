export interface Program {
  id: string;
  slug: string;
  name: string;
  provider: string;
  providerLogo?: string;
  category: string;
  status: "open" | "closed";
  difficulty: string;
  duration: string;
  deadline: string;
  eligibility: string;
  keyBenefit: string;
  description: string;
  tags: string[];
  website: string;
  featured?: boolean;
  applicants?: number;
  registrationForm?: string;
  facilitatorCode?: string;
}
