import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, setUnauthorizedHandler, tokenStore, type Role } from './api';

interface Me {
  name: string;
  role: Role;
  token_id: string;
  auth_enabled: boolean;
}

interface AuthState {
  me: Me | null;
  checking: boolean;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
  can: (role: Role) => boolean;
}

const RANK: Record<Role, number> = { viewer: 0, operator: 1, admin: 2 };
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [checking, setChecking] = useState(true);

  const signOut = useCallback(() => {
    tokenStore.clear();
    setMe(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    api<Me>('/api/me')
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setChecking(false));
  }, [signOut]);

  const signIn = useCallback(async (token: string) => {
    const profile = await api<Me>('/api/me', {}, token.trim());
    tokenStore.set(token.trim());
    setMe(profile);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ me, checking, signIn, signOut, can: (role) => !!me && RANK[me.role] >= RANK[role] }),
    [me, checking, signIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
