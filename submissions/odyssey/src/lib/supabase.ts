import { createClient } from '@supabase/supabase-js';

/**
 * Sanitizes the Supabase URL to ensure it is a clean base origin URL
 * without trailing endpoint paths like /rest/v1 or /auth/v1.
 */
function sanitizeSupabaseUrl(url: string | undefined): string {
  if (!url) return 'https://placeholder.supabase.co';
  let cleaned = url.trim();
  // Remove /rest/v1 or /auth/v1 path suffix if accidentally included in configuration
  cleaned = cleaned.replace(/\/(rest|auth)\/v1\/?$/i, '');
  // Remove trailing slashes
  cleaned = cleaned.replace(/\/+$/, '');
  return cleaned;
}

const rawUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseUrl = sanitizeSupabaseUrl(rawUrl);

const supabaseKey =
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  'placeholder-key';

if (!import.meta.env.VITE_SUPABASE_URL || (!import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY && !import.meta.env.VITE_SUPABASE_ANON_KEY)) {
  console.warn(
    'Supabase environment variables (VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY) are missing. Please set them in your .env file.'
  );
}

export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
