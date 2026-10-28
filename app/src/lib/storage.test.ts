import { describe, it, expect, afterEach, vi } from 'vitest'
import { memoryFallback, resetMemoryFallback, safeStorage } from './storage'

afterEach(() => {
  vi.restoreAllMocks()
  resetMemoryFallback()
})

describe('memoryFallback', () => {
  it('stores, reads back, removes, and reports missing keys as null', () => {
    expect(memoryFallback.getItem('k')).toBeNull()
    memoryFallback.setItem('k', 'v')
    expect(memoryFallback.getItem('k')).toBe('v')
    memoryFallback.removeItem('k')
    expect(memoryFallback.getItem('k')).toBeNull()
  })
  it('resetMemoryFallback clears every key', () => {
    memoryFallback.setItem('a', '1')
    memoryFallback.setItem('b', '2')
    resetMemoryFallback()
    expect(memoryFallback.getItem('a')).toBeNull()
    expect(memoryFallback.getItem('b')).toBeNull()
  })
})

describe('safeStorage', () => {
  it('returns window.localStorage when it works, and leaves no probe key behind', () => {
    const s = safeStorage()
    expect(s).toBe(window.localStorage)
    expect(window.localStorage.getItem('__qd_probe__')).toBeNull()
  })
  it('falls back to the in-memory store when localStorage throws (blocked site data)', () => {
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    expect(safeStorage()).toBe(memoryFallback)
  })
  it('falls back when localStorage exists but writes throw (quota exceeded)', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    expect(safeStorage()).toBe(memoryFallback)
  })
})
