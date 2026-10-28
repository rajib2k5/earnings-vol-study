import { describe, it, expect } from 'vitest'
import { getMetrics, track, timeIt, resetMetrics, EVENT_CAP } from './metrics'
import type { StorageLike } from './storage'

function memStorage(): StorageLike {
  const map = new Map<string, string>()
  return {
    getItem: (k) => (map.has(k) ? (map.get(k) as string) : null),
    setItem: (k, v) => void map.set(k, v),
    removeItem: (k) => void map.delete(k),
  }
}

const fixedNow = (t: number) => () => t

describe('metrics', () => {
  it('increments counters and appends events with the injected clock', () => {
    const st = memStorage()
    track('app', 'chart.open', { n: 3 }, { storage: st, now: fixedNow(1000) })
    track('app', 'chart.open', undefined, { storage: st, now: fixedNow(2000) })
    track('app', 'theme.toggle', undefined, { storage: st, now: fixedNow(3000) })
    const m = getMetrics('app', st)
    expect(m.counters).toEqual({ 'chart.open': 2, 'theme.toggle': 1 })
    expect(m.since).toBe(1000)
    expect(m.events).toHaveLength(3)
    expect(m.events[0]).toEqual({ at: 1000, name: 'chart.open', props: { n: 3 } })
  })
  it('caps the event ring at EVENT_CAP while counters keep counting', () => {
    const st = memStorage()
    for (let i = 0; i < EVENT_CAP + 25; i++) track('app', 'tick', undefined, { storage: st, now: fixedNow(i) })
    const m = getMetrics('app', st)
    expect(m.events).toHaveLength(EVENT_CAP)
    expect(m.counters.tick).toBe(EVENT_CAP + 25)
    expect(m.events[0].at).toBe(25)
  })
  it('timeIt returns the function result and records a ms prop', () => {
    const st = memStorage()
    let t = 100
    const now = () => (t += 40)
    const out = timeIt('app', 'compute.curve', () => 42, { storage: st, now })
    expect(out).toBe(42)
    const m = getMetrics('app', st)
    expect(m.counters['compute.curve']).toBe(1)
    expect(m.events[0].props?.ms).toBe(40)
  })
  it('never throws without storage and resets cleanly', () => {
    expect(() => track('app', 'x', undefined, { storage: null, now: fixedNow(1) })).not.toThrow()
    const st = memStorage()
    track('app', 'x', undefined, { storage: st, now: fixedNow(1) })
    resetMetrics('app', st)
    expect(getMetrics('app', st)).toEqual({ since: null, counters: {}, events: [] })
  })
  it('returns empty state on corrupt payloads', () => {
    const st = memStorage()
    st.setItem('qd:app:metrics', '{broken')
    expect(getMetrics('app', st)).toEqual({ since: null, counters: {}, events: [] })
  })
})
