import { z } from "zod";

const envSchema = z.object({
  AI_SERVICE_URL: z.string().url().default("http://127.0.0.1:8000"),
  INTERNAL_API_KEY: z.string().default("dev-internal-key-change-in-production"),
  AUTH_MODE: z.enum(["clerk", "demo"]).default("demo"),
  NEXT_PUBLIC_APP_URL: z.string().url().default("http://localhost:3000"),
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: z.string().optional(),
  CLERK_SECRET_KEY: z.string().optional(),
});

export const env = envSchema.parse({
  AI_SERVICE_URL: process.env.AI_SERVICE_URL,
  INTERNAL_API_KEY: process.env.INTERNAL_API_KEY,
  AUTH_MODE: (process.env.AUTH_MODE as "clerk" | "demo") || "demo",
  NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000"),
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
  CLERK_SECRET_KEY: process.env.CLERK_SECRET_KEY,
});
