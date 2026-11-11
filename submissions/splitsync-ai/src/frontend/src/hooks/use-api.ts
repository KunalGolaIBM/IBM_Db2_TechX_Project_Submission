'use client';

import { useState, useEffect, useCallback } from 'react';
import { api, ApiError } from '@/lib/api-client';

interface UseFetchResult<T> {
  data: T | null;
  error: ApiError | Error | null;
  isLoading: boolean;
  refetch: () => Promise<void>;
}

export function useFetch<T>(path: string | null): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(path !== null);

  const fetchData = useCallback(async () => {
    if (!path) {
      setData(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await api.get<T>(path);
      setData(result);
    } catch (err) {
      if (err instanceof ApiError || err instanceof Error) {
        setError(err);
      } else {
        setError(new Error('An unexpected error occurred'));
      }
    } finally {
      setIsLoading(false);
    }
  }, [path]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    error,
    isLoading,
    refetch: fetchData,
  };
}
