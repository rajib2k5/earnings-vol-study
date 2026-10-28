/**
 * Guarded browser storage shared by the theme and metrics helpers.
 *
 * Keys are namespaced per app slug (`qd:<slug>:<thing>`) so several apps served from one origin
 * never overwrite each other. Every storage access is guarded: incognito windows or blocked
 * site data must degrade to defaults, never throw.
 */
export interface StorageLike {
  getItem(k: string): string | null
  setItem(k: string, v: string): void
  removeItem(k: string): void
}

/**
 * In-memory fallback used when localStorage is missing or blocked (incognito windows,
 * storage-blocking browsers, Node's method-less experimental stub). Theme and metrics
 * then still work for the session — they just don't persist across reloads.
 */
const memMap = new Map<string, string>()
export const memoryFallback: StorageLike = {
  getItem: (k) => (memMap.has(k) ? (memMap.get(k) as string) : null),
  setItem: (k, v) => void memMap.set(k, v),
  removeItem: (k) => void memMap.delete(k),
}
export function resetMemoryFallback(): void {
  memMap.clear()
}

export function safeStorage(): StorageLike {
  try {
    const s = window.localStorage
    const probe = '__qd_probe__'
    s.setItem(probe, '1')
    s.removeItem(probe)
    return s
  } catch {
    return memoryFallback
  }
}
