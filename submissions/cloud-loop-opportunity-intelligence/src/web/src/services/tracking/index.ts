import { aiServiceFetch } from "@/services/api/client";

export interface TrackedOpportunity {
  user_id: string;
  opportunity_id: string;
  status: "None" | "Applied" | "Interviewing" | "Offer" | "Rejected";
  bookmarked: boolean;
  updated_at: string;
}

export async function fetchUserTracking(userId: string): Promise<TrackedOpportunity[]> {
  return aiServiceFetch<TrackedOpportunity[]>("/api/v1/tracking", {
    method: "GET",
    userId,
  });
}

export async function updateUserTracking(
  userId: string,
  payload: {
    opportunity_id: string;
    status?: string;
    bookmarked?: boolean;
  }
): Promise<TrackedOpportunity> {
  return aiServiceFetch<TrackedOpportunity>("/api/v1/tracking", {
    method: "PUT",
    userId,
    body: JSON.stringify(payload),
  });
}
