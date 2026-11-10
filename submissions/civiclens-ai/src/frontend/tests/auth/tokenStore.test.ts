import { afterEach, describe, expect, it, vi } from 'vitest'
import { tokenStore } from '../../src/auth/tokenStore'

const KEY = 'civiclens.session-token'
afterEach(() => vi.restoreAllMocks())

describe('tokenStore', () => {
  it('keeps the token in sessionStorage only: never localStorage, never a cookie', () => {
    tokenStore.set('abc')
    expect(window.sessionStorage.getItem(KEY)).toBe('abc')
    expect(window.localStorage.length).toBe(0)
    expect(document.cookie).toBe('')
    expect(tokenStore.get()).toBe('abc')
  })

  it('removing the token from storage really removes it (no hidden in-memory copy)', () => {
    tokenStore.set('abc')
    window.sessionStorage.removeItem(KEY)
    expect(tokenStore.get()).toBeNull()
  })

  it('clear() forgets everything', () => {
    tokenStore.set('abc')
    tokenStore.clear()
    expect(tokenStore.get()).toBeNull()
    expect(window.sessionStorage.getItem(KEY)).toBeNull()
  })

  it('falls back to memory only when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    tokenStore.set('mem-token')
    expect(tokenStore.get()).toBe('mem-token')
    vi.restoreAllMocks()
    tokenStore.clear()
    expect(tokenStore.get()).toBeNull()
  })
})
