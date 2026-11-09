import { QueryClient } from '@tanstack/react-query'
import { isApiError } from './errors'

/** Never retry client errors (a 403/409/422 will not fix itself); retry transient failures once. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (isApiError(error) && error.kind === 'http' && error.status < 500) return false
          return failureCount < 1
        },
      },
      mutations: { retry: false },
    },
  })
}
