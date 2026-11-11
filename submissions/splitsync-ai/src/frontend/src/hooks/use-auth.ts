'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api, ApiError } from '@/lib/api-client';
import { getToken, setToken, removeToken } from '@/lib/auth';
import type { User, AuthResponse } from '@/lib/types';

const USER_KEY = 'user_data';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  const loadUser = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    // Check cached user in storage first
    if (typeof window !== 'undefined') {
      const cached = localStorage.getItem(USER_KEY);
      if (cached) {
        try {
          setUser(JSON.parse(cached));
        } catch {
          // Ignore JSON parse error
        }
      }
    }

    try {
      const currentUser = await api.get<User>('/auth/me');
      setUser(currentUser);
      if (typeof window !== 'undefined') {
        localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        removeToken();
        setUser(null);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = async (email: string, password: string): Promise<User> => {
    setIsLoading(true);
    try {
      const response = await api.post<AuthResponse>('/auth/login', {
        email,
        password,
      });

      setToken(response.token);
      setUser(response.user);
      if (typeof window !== 'undefined') {
        localStorage.setItem(USER_KEY, JSON.stringify(response.user));
      }
      return response.user;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (name: string, email: string, password: string): Promise<User> => {
    setIsLoading(true);
    try {
      const response = await api.post<AuthResponse>('/auth/register', {
        display_name: name,
        email,
        password,
      });

      setToken(response.token);
      setUser(response.user);
      if (typeof window !== 'undefined') {
        localStorage.setItem(USER_KEY, JSON.stringify(response.user));
      }
      return response.user;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    removeToken();
    setUser(null);
    router.push('/login');
  };

  return {
    user,
    isLoading,
    login,
    register,
    logout,
    refetchUser: loadUser,
  };
}
