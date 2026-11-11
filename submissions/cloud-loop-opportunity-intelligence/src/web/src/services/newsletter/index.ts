import { aiServiceFetch } from "@/services/api/client";

export async function subscribeNewsletter(email: string): Promise<{
  status: string;
  email: string;
  created_at: string;
}> {
  return aiServiceFetch("/api/v1/newsletter", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}
