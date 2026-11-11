import { env } from "@/services/config/env";

export interface ApiFetchOptions extends RequestInit {
  userId?: string;
  params?: Record<string, string | number | boolean | undefined>;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Server-side client to call the Python AI service securely.
 * Never import or use this function on client components.
 */
export async function aiServiceFetch<T = any>(
  endpoint: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { userId, params, headers, ...rest } = options;

  let url = `${env.AI_SERVICE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const defaultHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    "x-internal-key": env.INTERNAL_API_KEY,
  };

  if (userId) {
    defaultHeaders["x-user-id"] = userId;
  }

  const response = await fetch(url, {
    ...rest,
    headers: {
      ...defaultHeaders,
      ...(headers as Record<string, string>),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = await response.text();
    }
    throw new ApiError(
      response.status,
      `AI Service responded with status ${response.status}: ${JSON.stringify(errorData)}`,
      errorData
    );
  }

  return response.json() as Promise<T>;
}
