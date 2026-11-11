export interface Event {
  id: string;
  slug: string;
  title: string;
  organizer: string;
  organizerLogo?: string;
  type: string;
  date: string;
  endDate?: string;
  location: string;
  isOnline: boolean;
  banner?: string;
  registrationDeadline: string;
  description: string;
  prize?: string;
  tags: string[];
  registered?: number;
  applyUrl?: string;
}
