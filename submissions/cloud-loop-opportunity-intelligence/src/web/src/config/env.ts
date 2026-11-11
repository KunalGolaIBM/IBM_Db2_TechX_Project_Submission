/**
 * @file env.ts
 * @description Centralised, typed environment variable access.
 * Import from here — never use process.env directly in app code.
 */

/** IBM Db2 connection settings */
export const db2Config = {
  hostname: process.env.DB2_HOSTNAME ?? "localhost",
  port: parseInt(process.env.DB2_PORT ?? "50000", 10),
  database: process.env.DB2_DATABASE ?? "CLOUDLOOP",
  uid: process.env.DB2_UID ?? "",
  pwd: process.env.DB2_PWD ?? "",
  sslDsn: process.env.DB2_SSL_DSN ?? "",
  ssl: process.env.DB2_SSL !== "false",
  /** True only when all required Db2 credentials are present */
  isConfigured:
    !!process.env.DB2_HOSTNAME &&
    !!process.env.DB2_UID &&
    !!process.env.DB2_PWD,
};

/** Supabase connection settings */
export const supabaseConfig = {
  url: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
  serviceKey:
    process.env.SUPABASE_SERVICE_ROLE_KEY ??
    process.env.SUPABASE_SECRET_KEY ??
    process.env.SUPABASE_SERVICE_KEY ??
    "",
  anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
};

/** Clerk auth settings */
export const clerkConfig = {
  publishableKey: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "",
  secretKey: process.env.CLERK_SECRET_KEY ?? "",
};

/** AI / LLM settings */
export const aiConfig = {
  openaiKey: process.env.OPENAI_API_KEY ?? "",
  googleAiKey: process.env.GOOGLE_AI_API_KEY ?? "",
  /** Which provider to use: "openai" | "google" | "none" */
  provider: process.env.AI_PROVIDER ?? (process.env.OPENAI_API_KEY ? "openai" : process.env.GOOGLE_AI_API_KEY ? "google" : "none"),
};

/** App-level settings */
export const appConfig = {
  baseUrl: process.env.NEXT_PUBLIC_BASE_URL ?? "https://cloudloop.dev",
  nodeEnv: process.env.NODE_ENV ?? "development",
  isDev: process.env.NODE_ENV === "development",
  isProd: process.env.NODE_ENV === "production",
};

