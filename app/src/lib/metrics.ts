/**
 * Lightweight per-app usage metrics: counters + a bounded ring of recent events,
 * persisted in localStorage under `qd:<slug>:metrics` and rendered on the Metrics page.
 *
 * This is the instrumentation layer, not domain code: it may read the wall clock,
 * but the clock is injectable (`now`) so tests stay deterministic. All storage is guarded.
 */
import { safeStorage, type StorageLike } from './storage'

export interface MetricEvent {
  at: number
  name: string
  props?: Record<string, string | number>
}

export interface MetricsState {
  since: number | null
  counters: Record<string, number>
  events: MetricEvent[]
}

export const EVENT_CAP = 200

const metricsKey = (slug: string) => `qd:${slug}:metrics`

const EMPTY: MetricsState = { since: null, counters: {}, events: [] }

export function getMetrics(slug: string, storage: StorageLike | null = safeStorage()): MetricsState {
  if (!storage) return { ...EMPTY }
  try {
    const raw = storage.getItem(metricsKey(slug))
    if (!raw) return { ...EMPTY }
    const parsed = JSON.parse(raw) as MetricsState
    return {
      since: parsed.since ?? null,
      counters: parsed.counters ?? {},
      events: Array.isArray(parsed.events) ? parsed.events : [],
    }
  } catch {
    return { ...EMPTY }
  }
}

export interface TrackOpts {
  storage?: StorageLike | null
  now?: () => number
}

export function track(
  slug: string,
  name: string,
  props?: Record<string, string | number>,
  opts: TrackOpts = {},
): MetricsState {
  const storage = opts.storage === undefined ? safeStorage() : opts.storage
  const now = opts.now ?? (() => Date.now())
  const state = getMetrics(slug, storage)
  const at = now()
  const next: MetricsState = {
    since: state.since ?? at,
    counters: { ...state.counters, [name]: (state.counters[name] ?? 0) + 1 },
    events: [...state.events, { at, name, ...(props ? { props } : {}) }].slice(-EVENT_CAP),
  }
  if (storage) {
    try {
      storage.setItem(metricsKey(slug), JSON.stringify(next))
    } catch {
      /* guarded: metrics must never break the app */
    }
  }
  return next
}

/** Run fn, record its duration under `<name>` with a ms prop, and return its result. */
export function timeIt<T>(slug: string, name: string, fn: () => T, opts: TrackOpts = {}): T {
  const now = opts.now ?? (() => Date.now())
  const t0 = now()
  const out = fn()
  track(slug, name, { ms: Math.max(0, now() - t0) }, opts)
  return out
}

export function resetMetrics(slug: string, storage: StorageLike | null = safeStorage()): void {
  try {
    storage?.removeItem(metricsKey(slug))
  } catch {
    /* guarded */
  }
}
