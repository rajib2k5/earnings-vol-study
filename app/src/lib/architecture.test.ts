import { describe, it, expect } from 'vitest'
import { ACTIVITY_EDGES, ACTIVITY_NODES, ARCH_LAYERS, SEQUENCE_ACTORS, SEQUENCE_STEPS } from './architecture'
import { SCHEMA_VERSION } from './contract'

// Layout limits, measured from diagrams.tsx: the box row is 588px wide, text is 11px monospace
// (about 6.6px a glyph), and boxes are separated by 10px. Characters that fit in one box:
//   1 box: 588/6.6 = 89   2 boxes: 289/6.6 = 43   3 boxes: 189/6.6 = 28
// The limits below leave a little margin. The layer label column is 110px of 10px letter-spaced
// capitals (about 7px a glyph).
const MAX_BOX_CHARS: Record<number, number> = { 1: 80, 2: 40, 3: 26 }
const MAX_LAYER_LABEL_CHARS = 14

const dupes = (xs: string[]) => xs.filter((x, i) => xs.indexOf(x) !== i)

describe('ARCH_LAYERS (architecture diagram)', () => {
  it('has unique layer labels (React keys) and unique box labels within each layer', () => {
    expect(dupes(ARCH_LAYERS.map((l) => l.label))).toEqual([])
    for (const l of ARCH_LAYERS) expect(dupes(l.boxes), l.label).toEqual([])
  })
  it('has 1-3 non-empty boxes per layer, each short enough to fit its box', () => {
    for (const l of ARCH_LAYERS) {
      expect(l.boxes.length, l.label).toBeGreaterThanOrEqual(1)
      expect(l.boxes.length, l.label).toBeLessThanOrEqual(3)
      for (const b of l.boxes) {
        expect(b.trim().length, `${l.label}: empty box`).toBeGreaterThan(0)
        expect(b.length, `${l.label}: "${b}" too long`).toBeLessThanOrEqual(MAX_BOX_CHARS[l.boxes.length])
      }
      expect(l.label.length, `layer label "${l.label}"`).toBeLessThanOrEqual(MAX_LAYER_LABEL_CHARS)
    }
  })
  it('keeps the pipeline order: sources, then cache, then measures ... then export, contract, app', () => {
    const order = ARCH_LAYERS.map((l) => l.label)
    const idx = (label: string) => order.indexOf(label)
    for (const label of ['DoltHub', 'Ingest / cache', 'IV measures', 'Event panel', 'Abnormal IV', 'Inference', 'Export', 'JSON contract', 'This app']) {
      expect(idx(label), label).toBeGreaterThanOrEqual(0)
    }
    const chain = ['DoltHub', 'Ingest / cache', 'IV measures', 'Event panel', 'Abnormal IV', 'Inference', 'Export', 'JSON contract', 'This app']
    expect(chain.map(idx)).toEqual([...chain.map(idx)].sort((a, b) => a - b))
  })
  it('names every data source and quotes the contract version the validator enforces', () => {
    const boxes = ARCH_LAYERS.flatMap((l) => l.boxes).join(' | ')
    for (const s of ['earnings_calendar', 'eps_history', 'option_chain', 'CBOE VX*', 'yfinance']) expect(boxes).toContain(s)
    expect(boxes).toContain(`schema ${SCHEMA_VERSION}`)
  })
})

describe('sequence diagram data', () => {
  it('has unique, non-empty actor names', () => {
    expect(dupes(SEQUENCE_ACTORS)).toEqual([])
    for (const a of SEQUENCE_ACTORS) expect(a.trim().length).toBeGreaterThan(0)
  })
  it('points every step at an existing actor index and gives it a label', () => {
    expect(SEQUENCE_STEPS.length).toBeGreaterThan(0)
    for (const s of SEQUENCE_STEPS) {
      for (const end of [s.from, s.to]) {
        expect(Number.isInteger(end), s.label).toBe(true)
        expect(end, s.label).toBeGreaterThanOrEqual(0)
        expect(end, s.label).toBeLessThan(SEQUENCE_ACTORS.length)
      }
      expect(s.label.trim().length).toBeGreaterThan(0)
    }
  })
  it('never puts a note (self-step) on the last actor, where its text would run off the figure', () => {
    const last = SEQUENCE_ACTORS.length - 1
    for (const s of SEQUENCE_STEPS) if (s.from === s.to) expect(s.from, s.label).not.toBe(last)
  })
})

describe('activity diagram data', () => {
  const ids = ACTIVITY_NODES.map((n) => n.id)
  const type = (id: string) => ACTIVITY_NODES.find((n) => n.id === id)?.type ?? 'action'
  const outgoing = (id: string) => ACTIVITY_EDGES.filter((e) => e.from === id)
  const incoming = (id: string) => ACTIVITY_EDGES.filter((e) => e.to === id)

  it('has unique node ids and non-empty labels', () => {
    expect(dupes(ids)).toEqual([])
    for (const n of ACTIVITY_NODES) expect(n.label.trim().length, n.id).toBeGreaterThan(0)
  })
  it('only has edges whose endpoints are real nodes (the diagram silently skips unknown ids)', () => {
    for (const e of ACTIVITY_EDGES) {
      expect(ids, `edge from "${e.from}"`).toContain(e.from)
      expect(ids, `edge to "${e.to}"`).toContain(e.to)
    }
  })
  it('has no self-loops and no duplicate edges', () => {
    for (const e of ACTIVITY_EDGES) expect(e.from).not.toBe(e.to)
    expect(dupes(ACTIVITY_EDGES.map((e) => `${e.from}->${e.to}`))).toEqual([])
  })
  it('has exactly one start (nothing flows into it) and at least one end (nothing flows out of it)', () => {
    const starts = ACTIVITY_NODES.filter((n) => n.type === 'start')
    const ends = ACTIVITY_NODES.filter((n) => n.type === 'end')
    expect(starts).toHaveLength(1)
    expect(ends.length).toBeGreaterThanOrEqual(1)
    expect(incoming(starts[0].id)).toHaveLength(0)
    for (const n of ends) expect(outgoing(n.id), n.id).toHaveLength(0)
  })
  it('lets every non-end node continue, and every decision branch carry a label', () => {
    for (const n of ACTIVITY_NODES) {
      if (type(n.id) !== 'end') expect(outgoing(n.id).length, n.id).toBeGreaterThanOrEqual(1)
      if (type(n.id) === 'decision') {
        expect(outgoing(n.id).length, n.id).toBeGreaterThanOrEqual(2)
        for (const e of outgoing(n.id)) expect(e.label?.trim().length ?? 0, `${n.id} -> ${e.to}`).toBeGreaterThan(0)
      }
    }
  })
  it('can reach every node from the start, and an end from every node', () => {
    const reach = (from: string, next: (id: string) => string[]) => {
      const seen = new Set([from])
      const todo = [from]
      while (todo.length > 0) {
        for (const nx of next(todo.pop() as string)) {
          if (!seen.has(nx)) {
            seen.add(nx)
            todo.push(nx)
          }
        }
      }
      return seen
    }
    const start = ACTIVITY_NODES.find((n) => n.type === 'start')!.id
    expect([...reach(start, (id) => outgoing(id).map((e) => e.to))].sort()).toEqual([...ids].sort())
    for (const end of ACTIVITY_NODES.filter((n) => n.type === 'end')) {
      expect([...reach(end.id, (id) => incoming(id).map((e) => e.from))].sort()).toEqual([...ids].sort())
    }
  })
  it('lists nodes top-down in workflow order (the diagram lays them out by array position)', () => {
    const order = ['build', 'tests', 'review', 'verify', 'push', 'learner']
    const pos = order.map((id) => ids.indexOf(id))
    expect(pos.every((p) => p >= 0)).toBe(true)
    expect(pos).toEqual([...pos].sort((a, b) => a - b))
  })
})
