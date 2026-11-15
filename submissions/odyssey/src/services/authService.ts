import { supabase } from '../lib/supabase';
import type { Session, User } from '@supabase/supabase-js';

export const authService = {
  /**
   * Send a magic link / OTP email for passwordless sign-in.
   *
  * Return to /auth so the existing authenticated redirect sends the user
  * to /home after the client exchanges the token.
   */
  async signInWithOtp(email: string) {
    const redirectTo = typeof window !== 'undefined'
      ? `${window.location.origin}/auth`
      : undefined;

    const { data, error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: redirectTo,
        // shouldCreateUser: true is the default — new accounts are created
        // automatically on first magic-link sign-in.
      },
    });
    if (error) throw error;
    return data;
  },

  async signUp(email: string, password: string) {
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
    return data;
  },

  async signInWithPassword(email: string, password: string) {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    return data;
  },

  async resetPasswordForEmail(email: string) {
    const redirectTo = typeof window !== 'undefined'
      ? `${window.location.origin}/auth`
      : undefined;

    const { data, error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo });
    if (error) throw error;
    return data;
  },

  async updatePassword(password: string) {
    const { data, error } = await supabase.auth.updateUser({ password });
    if (error) throw error;
    return data;
  },

  /**
   * Start Google OAuth and return to the app after Supabase completes sign-in.
   */
  async signInWithGoogle() {
    const redirectTo = typeof window !== 'undefined'
      ? `${window.location.origin}/auth`
      : undefined;

    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo },
    });
    if (error) throw error;
    return data;
  },

  /**
   * Verify a 6-digit OTP token (fallback for token-based verification).
   */
  async verifyOtp(email: string, token: string) {
    const { data, error } = await supabase.auth.verifyOtp({
      email,
      token,
      type: 'email',
    });
    if (error) throw error;
    return data;
  },

  /**
   * Sign out the current user session.
   */
  async signOut() {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  },

  /**
   * Return the current persisted session (null if none).
   * Safe to call on every page load — supabase-js reads from localStorage.
   */
  async getSession(): Promise<Session | null> {
    const { data, error } = await supabase.auth.getSession();
    if (error) throw error;
    return data.session;
  },

  /**
   * Return the current authenticated user (server-verified).
   */
  async getUser(): Promise<User | null> {
    const { data, error } = await supabase.auth.getUser();
    if (error) throw error;
    return data.user;
  },

  /**
   * Subscribe to auth state changes (SIGNED_IN, SIGNED_OUT, TOKEN_REFRESHED…).
   * Returns the subscription object — call .unsubscribe() on cleanup.
   */
  onAuthStateChange(callback: (event: string, session: Session | null) => void) {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => callback(event, session)
    );
    return subscription;
  },
};
