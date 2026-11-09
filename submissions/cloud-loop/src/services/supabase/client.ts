/**
 * @file supabase/client.ts
 * @description Supabase client used for AI search, recommendations, and analytics.
 * This is the PRIMARY database layer. IBM Db2 is optional/additive.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { supabaseConfig } from "@/config/env";

let _adminClient: SupabaseClient | null = null;
let _publicClient: SupabaseClient | null = null;

const fallbackUrl = "https://placeholder-project.supabase.co";
const fallbackKey = "placeholder-anon-key";

/** Server-side Supabase admin client (bypasses RLS). Use in API routes only. */
export function getSupabaseAdmin(): SupabaseClient {
  if (!_adminClient) {
    const url = supabaseConfig.url || fallbackUrl;
    const key = supabaseConfig.serviceKey || fallbackKey;
    _adminClient = createClient(url, key, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
  }
  return _adminClient;
}

/** Public Supabase client (respects RLS). Use in client components via anon key. */
export function getSupabasePublic(): SupabaseClient {
  if (!_publicClient) {
    const url = supabaseConfig.url || fallbackUrl;
    const key = supabaseConfig.anonKey || supabaseConfig.serviceKey || fallbackKey;
    _publicClient = createClient(url, key);
  }
  return _publicClient;
}

/** Check if Supabase is configured */
export const isSupabaseConfigured = !!(supabaseConfig.url && (supabaseConfig.serviceKey || supabaseConfig.anonKey));
