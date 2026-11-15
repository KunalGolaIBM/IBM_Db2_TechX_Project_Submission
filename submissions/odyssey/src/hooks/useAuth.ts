import { useEffect, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { authService } from '../services/authService';

export function useAuth() {
  const [session,  setSession]  = useState<Session | null>(null);
  const [user,     setUser]     = useState<User | null>(null);
  const [loading,  setLoading]  = useState<boolean>(true);

  useEffect(() => {
    // Subscribe first so we never miss an event that fires during getSession()
    const subscription = authService.onAuthStateChange((_event, currentSession) => {
      setSession(currentSession);
      setUser(currentSession?.user ?? null);
      setLoading(false);
    });

    // Then fetch the current session (also handles URL token exchange if not
    // already handled by the auto-initialize path)
    authService.getSession().then((initialSession) => {
      setSession(initialSession);
      setUser(initialSession?.user ?? null);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  return {
    session,
    user,
    loading,
    isAuthenticated: !!user,
    // Methods are bound to the service object to preserve 'this' context when
    // destructured and called directly by consumers.
    signInWithOtp: authService.signInWithOtp.bind(authService),
    signUp:        authService.signUp.bind(authService),
    signInWithPassword: authService.signInWithPassword.bind(authService),
    resetPasswordForEmail: authService.resetPasswordForEmail.bind(authService),
    updatePassword: authService.updatePassword.bind(authService),
    signInWithGoogle: authService.signInWithGoogle.bind(authService),
    verifyOtp:     authService.verifyOtp.bind(authService),
    signOut:       authService.signOut.bind(authService),
  };
}
