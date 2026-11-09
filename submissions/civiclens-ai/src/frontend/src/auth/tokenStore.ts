/**
 * Bearer-token storage. sessionStorage (per tab, cleared when the tab closes) rather than localStorage,
 * and never a cookie, a URL or a build-time variable.
 *
 * Memory is only a fallback for when storage itself is unavailable (private mode, blocked): the token is
 * never duplicated into memory while storage works, so removing it from storage really removes it.
 */
const KEY = 'civiclens.session-token'
let fallback: string | null = null

export const tokenStore = {
  get(): string | null {
    try {
      const stored = window.sessionStorage.getItem(KEY)
      if (stored !== null) return stored
    } catch {
      /* storage unavailable: use the fallback */
    }
    return fallback
  },
  set(token: string): void {
    try {
      window.sessionStorage.setItem(KEY, token)
      fallback = null
    } catch {
      fallback = token
    }
  },
  clear(): void {
    fallback = null
    try {
      window.sessionStorage.removeItem(KEY)
    } catch {
      /* nothing to clear */
    }
  },
}
