export interface Certification {
  id: string;
  slug: string;
  name: string;
  provider: string;
  providerLogo?: string;
  providerLink?: string;
  interestedCount: string;
  cost: "Free" | "Paid";
  badge: string;
  enrollUrl: string;
  thumbnail: string;
  description: string;
  skills: string[];
  difficulty: string;
  duration: string;
}
