import { describe, it, expect } from 'vitest'
import {
  FOREST_LABEL_MAX,
  FOREST_ROW,
  forestBox,
  forestLayout,
  niceStep,
  niceTicks,
  percentTickLabel,
  plotArea,
  SCATTER_BOX,
  scatterLayout,
  tickLabel,
  truncateLabel,
  type ScatterSource,
} from './chartLayout'
import { IMPLIED_REALISED_DATA_FIXTURE } from '../test/impliedRealisedFixture'

/*
 * Mutations this file must catch: 21 of 21 tried were killed. Each was applied to src/lib/chartLayout.ts, one at a time,
 * and this file then failed; the file was restored and its sha256 checked each time (script outside the repo).
 *   CL1: round steps lose 2.5
 *   CL2: a step must exceed (not just cover) the raw step
 *   CL3: ticks no longer rounded to 12 digits
 *   CL4: no tolerance at the top end (7.000000000000001 rounds up to 8)
 *   CL5: no tolerance at the bottom end (2.9999999999999996 rounds down to 2)
 *   CL6: a range with no width gives one tick
 *   CL7: tick labels cut to two significant digits (1.25 reads 1.3)
 *   CL8: percent tick label multiplies by 10
 *   CL9: a label of exactly max characters is cut
 *   CL10: scatter y axis not flipped (larger y drawn lower)
 *   CL11: scatter x and y swapped
 *   CL12: axis maximum ignores the realised moves
 *   CL13: diagonal drawn from top left to bottom right
 *   CL14: events without an expected move not counted
 *   CL15: plot area ignores the right margin
 *   CL16: forest axis no longer forced to contain 0
 *   CL17: forest rows sit at the top of their band, not the middle
 *   CL18: a forest interval is drawn when either end is there
 *   CL19: forest x scale reversed
 *   CL20: axis maximum also set by events that are not drawn
 *   CL21: forest box height forgets the bottom margin
 */

describe('niceStep: the smallest 1, 2, 2.5 or 5 times a power of ten that covers the span in at most maxIntervals steps', () => {
  // raw = span / maxIntervals; the step is the first of 1, 2, 2.5, 5, 10 (times the power of ten at or below raw) that is at least raw
  it.each([
    [0.1, 6, 0.02], // raw 0.01667: 1 x 0.01 is too small, 2 x 0.01 is enough
    [0.30663, 8, 0.05], // raw 0.03833: 5 x 0.01
    [7, 6, 2], // raw 1.1667
    [2.2, 1, 2.5], // raw 2.2: 2 is too small, 2.5 is enough
    [60, 6, 10], // raw exactly 10: 1 x 10 is enough (not 2 x 10)
    [42, 6, 10], // raw 7: nothing up to 5 x 1 covers it, so 10
    [0.75, 6, 0.2], // raw 0.125
  ])('niceStep(%f, %i) is %f', (span, maxIntervals, step) => {
    expect(niceStep(span, maxIntervals)).toBeCloseTo(step, 12)
  })
})

describe('niceTicks', () => {
  it('starts at 0 and ends at the first multiple of the step at or above the maximum', () => {
    expect(niceTicks(0, 0.1)).toEqual([0, 0.02, 0.04, 0.06, 0.08, 0.1])
    expect(niceTicks(0, 0.30663, 8)).toEqual([0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35])
    expect(niceTicks(0, 1)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1])
  })
  it('covers a range with negative values and keeps 0 on a tick', () => {
    expect(niceTicks(-0.375, 0.375)).toEqual([-0.4, -0.2, 0, 0.2, 0.4])
    expect(niceTicks(-0.02, 0.05)).toEqual([-0.02, 0, 0.02, 0.04, 0.06])
    expect(niceTicks(-1, 1, 4)).toEqual([-1, -0.5, 0, 0.5, 1])
  })
  it('does not add a tick when the end of the range lies exactly on one (no float noise past it)', () => {
    expect(niceTicks(0, 10, 5)).toEqual([0, 2, 4, 6, 8, 10])
    expect(niceTicks(0, 0.35, 8)).toEqual([0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35])
  })
  it('does not add a tick past the end of the range when hi / step comes out a hair above a whole number (0.14 / 0.02 is 7.000000000000001)', () => {
    expect(niceTicks(0, 0.14, 7)).toEqual([0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.12, 0.14])
  })
  it('starts on the tick at the start of the range when float noise puts it just below (0.3 / 0.1 is 2.9999999999999996)', () => {
    expect(niceTicks(0.3, 0.6, 3)).toEqual([0.3, 0.4, 0.5, 0.6])
  })
  it('rounds the ticks to 12 digits: 3 x 0.1 is 0.3, not 0.30000000000000004', () => {
    expect(niceTicks(0, 0.3, 3)).toEqual([0, 0.1, 0.2, 0.3])
  })
  it('gives lo - 1, lo and lo + 1 for a range with no width', () => {
    expect(niceTicks(5, 5)).toEqual([4, 5, 6])
    expect(niceTicks(0, 0)).toEqual([-1, 0, 1])
  })
  it('never has more than maxIntervals steps when the range starts on a tick', () => {
    for (const hi of [0.03, 0.1, 0.2, 0.3066, 0.9, 1.7, 12]) {
      const ticks = niceTicks(0, hi, 6)
      expect(ticks.length - 1, String(hi)).toBeLessThanOrEqual(6)
      expect(ticks[ticks.length - 1], String(hi)).toBeGreaterThanOrEqual(hi)
      expect(ticks[0]).toBe(0)
    }
  })
})

describe('tick labels', () => {
  it('tickLabel shows the tick as it is: no float noise, no trailing zeros, and no rounding of a tick that has three digits', () => {
    expect(tickLabel(0.05)).toBe('0.05')
    expect(tickLabel(-0.0154)).toBe('-0.0154')
    expect(tickLabel(0)).toBe('0')
    expect(tickLabel(-0)).toBe('0')
    expect(tickLabel(0.2)).toBe('0.2')
    expect(tickLabel(1234)).toBe('1234')
    expect(tickLabel(1.25)).toBe('1.25') // not "1.3": 1.25 is a tick of a step of 0.25
    expect(tickLabel(0.125)).toBe('0.125')
    expect(tickLabel(0.1 + 0.2)).toBe('0.3') // 0.30000000000000004
  })
  it('percentTickLabel shows a fraction as a percent', () => {
    expect(percentTickLabel(0.025)).toBe('2.5%')
    expect(percentTickLabel(0.3)).toBe('30%')
    expect(percentTickLabel(0.07)).toBe('7%') // 0.07 * 100 is 7.000000000000001
    expect(percentTickLabel(0)).toBe('0%')
    expect(percentTickLabel(0.1)).toBe('10%')
  })
  it('truncateLabel cuts a long label to max characters, the last being an ellipsis, and leaves a short one alone', () => {
    expect(truncateLabel('abc', 5)).toBe('abc')
    expect(truncateLabel('abcde', 5)).toBe('abcde')
    expect(truncateLabel('abcdef', 5)).toBe('abcd…')
    expect(truncateLabel('abc', 0)).toBe('…')
    expect(truncateLabel('', 3)).toBe('')
  })
})

describe('plotArea', () => {
  it('is the box inside its margins, in pixels', () => {
    expect(plotArea({ width: 100, height: 80, left: 10, right: 20, top: 5, bottom: 15 })).toEqual({ left: 10, right: 80, top: 5, bottom: 65 })
  })
  it('is square for the scatter box (so the line y = x is at 45 degrees)', () => {
    const p = plotArea(SCATTER_BOX)
    expect(p).toEqual({ left: 56, right: 504, top: 16, bottom: 464 })
    expect(p.right - p.left).toBe(p.bottom - p.top)
  })
})

describe('scatterLayout', () => {
  const points = IMPLIED_REALISED_DATA_FIXTURE.points as ScatterSource[]
  // Hand-worked: the largest value of either variable is 0.1 (FIXB's realised move), so the ticks are 0, 0.02 .. 0.1 and the
  // axis maximum is 0.1. The plot area is x 56..504 and y 16..464 (448 pixels each), so
  //   cx = 56 + x / 0.1 * 448      cy = 464 - y / 0.1 * 448
  //   FIXA (0.05, 0.025):    cx 280, cy 352          FIXB (0.0625, 0.1):   cx 336, cy 16
  //   FIXC (0.03125, 0.0375): cx 196, cy 296         FIXD (0.0375, 0.0125): cx 224, cy 408
  const layout = scatterLayout(points)

  it('has the round ticks of both axes, from 0 to the axis maximum', () => {
    expect(layout.ticks).toEqual([0, 0.02, 0.04, 0.06, 0.08, 0.1])
  })
  it('puts every dot at its hand-worked pixel, in file order, leaving out the event with no expected move', () => {
    expect(layout.dots.map((d) => d.id)).toEqual(['FIXA:2031-01-01', 'FIXB:2031-02-01', 'FIXC:2031-03-01', 'FIXD:2031-04-01'])
    const px = layout.dots.map((d) => [d.cx, d.cy])
    const expected = [[280, 352], [336, 16], [196, 296], [224, 408]]
    px.forEach(([cx, cy], i) => {
      expect(cx, `dot ${i} cx`).toBeCloseTo(expected[i][0], 9)
      expect(cy, `dot ${i} cy`).toBeCloseTo(expected[i][1], 9)
    })
  })
  it('keeps x as the expected move and y as the realised move (not the other way round), with the values as written', () => {
    expect(layout.dots[1]).toMatchObject({ x: 0.0625, y: 0.1, timing: 'AMC', label: 'FIXB 2031-02-02' })
    expect(layout.dots[0]).toMatchObject({ x: 0.05, y: 0.025, timing: 'BMO', label: 'FIXA 2031-01-02' })
    expect(layout.dots[3].timing).toBeNull()
  })
  it('puts the larger realised move higher on the screen (smaller cy) and the larger expected move further right (larger cx)', () => {
    const [a, b] = layout.dots
    expect(b.y).toBeGreaterThan(a.y)
    expect(b.cy).toBeLessThan(a.cy)
    expect(b.x).toBeGreaterThan(a.x)
    expect(b.cx).toBeGreaterThan(a.cx)
  })
  it('puts the ticks at the right pixels on each axis: x from the left edge, y from the bottom edge', () => {
    const expectedX = [56, 145.6, 235.2, 324.8, 414.4, 504]
    layout.tickX.forEach((v, i) => expect(v).toBeCloseTo(expectedX[i], 9))
    layout.tickY.forEach((v, i) => expect(v).toBeCloseTo(520 - 56 - (expectedX[i] - 56), 9))
    expect(layout.tickY[0]).toBe(464)
    expect(layout.tickY[layout.tickY.length - 1]).toBe(16)
  })
  it('draws the line y = x from the bottom left to the top right corner of the plot area, and a dot with x equal to y sits on it', () => {
    expect(layout.diagonal).toEqual({ x1: 56, y1: 464, x2: 504, y2: 16 })
    const onLine = scatterLayout([{ ...points[0], implied_abs_move_total: 0.0625, abs_realized: 0.0625 }, points[1]])
    const d = onLine.dots[0]
    expect(d.cx - onLine.plot.left).toBeCloseTo(onLine.plot.bottom - d.cy, 9)
  })
  it('counts the events with no expected move and does not draw them', () => {
    expect(layout.withoutImplied).toBe(1)
    expect(layout.dots).toHaveLength(4)
  })
  it('centres the axis titles on the plot area', () => {
    expect(layout.centre).toEqual({ x: 280, y: 240 })
  })
  it('scales to the box it is given', () => {
    const small = scatterLayout(points, { width: 100, height: 100, left: 10, right: 10, top: 10, bottom: 10 })
    // plot area 10..90: FIXB is at 0.0625 / 0.1 of the width and 0.1 / 0.1 of the height
    expect(small.dots[1].cx).toBeCloseTo(60, 9)
    expect(small.dots[1].cy).toBeCloseTo(10, 9)
    expect(small.diagonal).toEqual({ x1: 10, y1: 90, x2: 90, y2: 10 })
  })
  it('lets a large realised move set the axis maximum, and a large expected move too', () => {
    const big = (x: number, y: number): ScatterSource => ({ ...points[0], implied_abs_move_total: x, abs_realized: y })
    expect(scatterLayout([big(0.05, 0.3)]).ticks.at(-1)).toBeGreaterThanOrEqual(0.3)
    expect(scatterLayout([big(0.3, 0.05)]).ticks.at(-1)).toBeGreaterThanOrEqual(0.3)
    expect(scatterLayout([big(0.05, 0.05)]).ticks.at(-1)).toBeLessThan(0.3)
  })
  it('does not let an event with no expected move set the axis: only drawn dots count', () => {
    const l = scatterLayout([points[0], { ...points[4], abs_realized: 5 }])
    expect(l.ticks.at(-1)).toBeLessThan(1)
  })
  it('gives a unit axis and no dots when no event has an expected move', () => {
    const l = scatterLayout([points[4]])
    expect(l.dots).toEqual([])
    expect(l.ticks).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1])
    expect(l.withoutImplied).toBe(1)
    expect(scatterLayout([]).withoutImplied).toBe(0)
  })
})

describe('forestLayout', () => {
  // Hand-worked: values -0.375 .. 0.375 and 0, so the ticks are -0.4, -0.2, 0, 0.2, 0.4 and the axis is -0.4 .. 0.4.
  // Three rows make the box 640 x 142 with the plot area x 230..616, y 24..102, so
  //   x = 230 + (v + 0.4) / 0.8 * 386        row i is centred at y = 24 + (i + 0.5) * 26
  const sources = [
    { label: 'Term A', coef: 0.25, ci_lo: 0.125, ci_hi: 0.375 },
    { label: 'Term B', coef: -0.125, ci_lo: -0.375, ci_hi: 0.125 },
    { label: 'Term C', coef: 0.1875, ci_lo: null, ci_hi: null },
  ]
  const layout = forestLayout(sources)

  it('sizes the box by the number of rows', () => {
    expect(forestBox(3)).toEqual({ width: 640, height: 24 + 3 * FOREST_ROW + 40, left: 230, right: 24, top: 24, bottom: 40 })
    expect(layout.box).toEqual(forestBox(3))
    expect(layout.box.height).toBe(142)
    expect(layout.plot).toEqual({ left: 230, right: 616, top: 24, bottom: 102 })
  })
  it('has the round ticks of the axis, which contain 0', () => {
    expect(layout.ticks).toEqual([-0.4, -0.2, 0, 0.2, 0.4])
  })
  it('puts the zero line and the ticks at their hand-worked pixels', () => {
    expect(layout.zeroX).toBeCloseTo(423, 9)
    const expected = [230, 326.5, 423, 519.5, 616]
    layout.tickX.forEach((v, i) => expect(v).toBeCloseTo(expected[i], 9))
  })
  it('puts every row at its hand-worked pixel: point, interval ends and height', () => {
    const rows = layout.rows
    expect(rows.map((r) => r.y)).toEqual([37, 63, 89])
    expect(rows[0].x).toBeCloseTo(543.625, 9)
    expect(rows[0].x1).toBeCloseTo(483.3125, 9)
    expect(rows[0].x2).toBeCloseTo(603.9375, 9)
    expect(rows[1].x).toBeCloseTo(362.6875, 9)
    expect(rows[1].x1).toBeCloseTo(242.0625, 9)
    expect(rows[1].x2).toBeCloseTo(483.3125, 9)
    expect(rows[2].x).toBeCloseTo(513.46875, 9)
  })
  it('puts a positive coefficient right of the zero line and a negative one left of it, and the interval ends around the point', () => {
    const [a, b] = layout.rows
    expect(a.x).toBeGreaterThan(layout.zeroX)
    expect(b.x).toBeLessThan(layout.zeroX)
    expect(a.x1 as number).toBeLessThan(a.x)
    expect(a.x2 as number).toBeGreaterThan(a.x)
  })
  it('gives a row with no interval its point only (x1 and x2 null)', () => {
    expect(layout.rows[2]).toMatchObject({ x1: null, x2: null })
  })
  it('draws only the point when just one end of the interval is there', () => {
    const l = forestLayout([{ label: 'one end', coef: 0.1, ci_lo: null, ci_hi: 0.3 }, { label: 'other end', coef: 0.1, ci_lo: -0.1, ci_hi: null }])
    expect(l.rows.map((r) => [r.x1, r.x2])).toEqual([[null, null], [null, null]])
  })
  it('lets the interval ends set the axis, not only the coefficients', () => {
    const l = forestLayout([{ label: 'wide', coef: 0.1, ci_lo: -0.9, ci_hi: 0.9 }])
    expect(l.ticks[0]).toBeLessThanOrEqual(-0.9)
    expect(l.ticks.at(-1)).toBeGreaterThanOrEqual(0.9)
  })
  it('keeps 0 inside the axis when every value is positive (the zero line is always drawn)', () => {
    const l = forestLayout([{ label: 'positive', coef: 0.5, ci_lo: 0.25, ci_hi: 0.75 }])
    expect(l.ticks[0]).toBe(0)
    expect(l.zeroX).toBeCloseTo(l.plot.left, 9)
  })
  it('keeps 0 inside the axis when every value is negative', () => {
    const l = forestLayout([{ label: 'negative', coef: -0.5, ci_lo: -0.75, ci_hi: -0.25 }])
    expect(l.ticks.at(-1)).toBe(0)
    expect(l.zeroX).toBeCloseTo(l.plot.right, 9)
  })
  it('cuts a long label to fit the margin and keeps the whole label for the hover title', () => {
    const label = 'a long term label that does not fit the margin of the plot'
    const l = forestLayout([{ label, coef: 0.1, ci_lo: null, ci_hi: null }])
    expect(l.rows[0].label).toHaveLength(FOREST_LABEL_MAX)
    expect(l.rows[0].label.endsWith('…')).toBe(true)
    expect(l.rows[0].full).toBe(label)
    expect(layout.rows[0].label).toBe('Term A')
  })
  it('gives the axis alone around 0 for no rows', () => {
    const l = forestLayout([])
    expect(l.rows).toEqual([])
    expect(l.ticks).toEqual([-1, 0, 1])
    expect(l.box.height).toBe(64)
    expect(l.zeroX).toBeCloseTo(423, 9)
  })
})
