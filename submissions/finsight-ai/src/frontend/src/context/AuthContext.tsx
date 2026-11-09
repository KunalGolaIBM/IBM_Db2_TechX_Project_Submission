import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { apiClient, User, ApiError } from '../api/client';

interface AuthContextType {
  user: User | null;
  csrfToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (fullName: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Initialize session verification from backend via HttpOnly cookie
  const refreshMe = useCallback(async () => {
    try {
      const res = await apiClient.auth.me();
      setUser(res.user);
      setCsrfToken(res.csrf_token);
    } catch {
      // Unauthenticated or expired session
      setUser(null);
      setCsrfToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshMe();
  }, [refreshMe]);

  const login = async (email: string, password: string): Promise<User> => {
    const res = await apiClient.auth.login({ email, password });
    setUser(res.user);
    setCsrfToken(res.csrf_token);
    return res.user;
  };

  const register = async (fullName: string, email: string, password: string): Promise<User> => {
    const res = await apiClient.auth.register({
      full_name: fullName,
      email,
      password,
    });
    setUser(res.user);
    setCsrfToken(res.csrf_token);
    return res.user;
  };

  const logout = async (): Promise<void> => {
    try {
      await apiClient.auth.logout(csrfToken);
    } catch (err) {
      // Even if network fails or session was already revoked on server,
      // re-check session to ensure client does not show stale state
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        // Session already revoked
      } else {
        throw err;
      }
    } finally {
      setUser(null);
      setCsrfToken(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        csrfToken,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        refreshMe,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
