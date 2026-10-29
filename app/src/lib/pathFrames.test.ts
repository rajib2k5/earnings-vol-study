import { describe, it, expect, vi } from 'vitest'
import {
  bandPath,
  CHART,
  extentOf,
  extentWithZero,
  FRAME_MS,
  initialPlayback,
  linearTicks,
  padExtent,
  runsToPath,
  scaleLinear,
  seekPlayback,
  stepPlayback,
  togglePlayback,
  visibleRuns,
  xPixels,
  xTickDays,
  yScale,
  type Playback,
} from './pathFrames'

// The chart is 640 x 320 with margins left 56, right 16, top 22, bottom 34, so the plot area runs
// from x = 56 to x = 640 - 16 = 624 (568 wide) and from y = 22 down to y = 320 - 34 = 286 (264 tall).

describe('scaleLinear', () => {
  it('maps the ends and the middle of the domain to the ends and the middle of the range', () => {
    // 5 is halfway through 0..10, so halfway through 100..200: 100 + 0.5 * 100 = 150
    expect(scaleLinear(5, 0, 10, 100, 200)).toBe(150)
    expect(scaleLinear(0, 0, 10, 100, 200)).toBe(100)
    expect(scaleLinear(10, 0, 10, 100, 200)).toBe(200)
  })
  it('handles a range that runs backwards, as the y axis of a screen does', () => {
    // 2.5 is a quarter of the way through 0..10: 200 + 0.25 * (100 - 200) = 175
    expect(scaleLinear(2.5, 0, 10, 200, 100)).toBe(175)
    expect(scaleLinear(10, 0, 10, 200, 100)).toBe(100)
  })
  it('extends past the ends instead of clamping (clamping would hide a value that is out of range)', () => {
    expect(scaleLinear(20, 0, 10, 100, 200)).toBe(300)
    expect(scaleLinear(-10, 0, 10, 100, 200)).toBe(0)
  })
  it('maps a domain with no width to the middle of the range', () => {
    expect(scaleLinear(3, 3, 3, 0, 10)).toBe(5)
  })
})

describe('extentOf, padExtent, linearTicks', () => {
  it('finds the smallest and largest number over all arrays, skipping null and non-finite', () => {
    expect(extentOf([[1, null, 3], [-2, 0.5]])).toEqual([-2, 3])
    expect(extentOf([[NaN, 1, Infinity]])).toEqual([1, 1])
  })
  it('is null when there is no number at all (all null, empty arrays, no arrays)', () => {
    expect(extentOf([[null, null]])).toBeNull()
    expect(extentOf([[]])).toBeNull()
    expect(extentOf([])).toBeNull()
  })
  it('does not read null as 0: an all-positive array does not get 0 in its extent', () => {
    expect(extentOf([[2, null, 5]])).toEqual([2, 5])
  })
  it('extentWithZero always contains 0: all-positive 2..5 becomes 0..5, all-negative -3..-1 becomes -3..0, a span across 0 is unchanged', () => {
    expect(extentWithZero([[2, null, 5]])).toEqual([0, 5])
    expect(extentWithZero([[-3, -1]])).toEqual([-3, 0])
    expect(extentWithZero([[-1, 2]])).toEqual([-1, 2])
  })
  it('extentWithZero of no number at all is [0, 0]', () => {
    expect(extentWithZero([[null, null]])).toEqual([0, 0])
    expect(extentWithZero([])).toEqual([0, 0])
  })
  it('pads each side by a fraction of the width: 0..10 with 0.1 gives -1..11 (pad = 10 * 0.1 = 1)', () => {
    expect(padExtent([0, 10], 0.1)).toEqual([-1, 11])
    expect(padExtent([-2, 2], 0.25)).toEqual([-3, 3])
  })
  it('gives a flat extent a span of its own: 2..2 becomes 1.5..2.5 (pad 0.5)', () => {
    expect(padExtent([2, 2], 0.1)).toEqual([1.5, 2.5])
  })
  it('makes evenly spaced ticks including both ends: 0..1 in 5 ticks is 0, 0.25, 0.5, 0.75, 1', () => {
    expect(linearTicks(0, 1, 5)).toEqual([0, 0.25, 0.5, 0.75, 1])
    expect(linearTicks(-1, 1, 3)).toEqual([-1, 0, 1])
    expect(linearTicks(3, 9, 2)).toEqual([3, 9])
    expect(linearTicks(3, 9, 1)).toEqual([3])
  })
})

describe('xPixels and yScale', () => {
  it('puts the first day at the left edge of the plot and the last at the right edge', () => {
    // 5 days: 568 / 4 = 142 pixels apart, starting at 56
    expect(xPixels([-2, -1, 0, 1, 2])).toEqual([56, 198, 340, 482, 624])
  })
  it('spaces days by their value, not their index (a gap in the days is a gap on the axis)', () => {
    // days 0, 1, 4: 568 / 4 = 142 per day -> 56, 198, 624
    expect(xPixels([0, 1, 4])).toEqual([56, 198, 624])
  })
  it('puts day 0 of a -10..10 window in the middle: 56 + 10 * 28.4 = 340', () => {
    const days = Array.from({ length: 21 }, (_, i) => i - 10)
    const xs = xPixels(days)
    expect(xs[0]).toBe(56)
    expect(xs[10]).toBeCloseTo(340, 9)
    expect(xs[20]).toBe(624)
  })
  it('puts a single day in the middle of the plot: (56 + 624) / 2 = 340', () => {
    expect(xPixels([0])).toEqual([340])
  })
  it('uses the box it is given', () => {
    expect(xPixels([0, 10], { width: 200, height: 100, left: 20, right: 10, top: 5, bottom: 15 })).toEqual([20, 190])
  })
  it('puts the smallest value at the bottom of the plot and the largest at the top', () => {
    const toY = yScale([0, 2])
    expect(toY(0)).toBe(286) // 320 - 34
    expect(toY(2)).toBe(22)
    // 1 is halfway: 286 + 0.5 * (22 - 286) = 154
    expect(toY(1)).toBe(154)
    // a value below the extent is drawn below the plot area, not clamped: 286 + (-1 / 2) * (22 - 286) = 286 + 132 = 418
    expect(toY(-1)).toBe(418)
  })
  it('puts 0 in the middle of a symmetric extent: -1..1 maps 0 to (286 + 22) / 2 = 154', () => {
    expect(yScale([-1, 1])(0)).toBe(154)
  })
  it('exposes the plot area its tests assume', () => {
    expect(CHART).toMatchObject({ width: 640, height: 320, left: 56, right: 16, top: 22, bottom: 34 })
  })
})

describe('visibleRuns: which points are visible at frame k', () => {
  // toY(v) = 100 - v, so the values are easy to follow: value 1 is at y = 99, value 3 at y = 97.
  const xs = [10, 20, 30, 40]
  const toY = (v: number) => 100 - v

  it('shows nothing before the first frame, and the first point at frame 0', () => {
    expect(visibleRuns([1, 2, 3, 4], -1, xs, toY)).toEqual([])
    expect(visibleRuns([1, 2, 3, 4], 0, xs, toY)).toEqual([[[10, 99]]])
  })
  it('grows by one day per frame: frame k shows day indexes 0 .. k', () => {
    expect(visibleRuns([1, 2, 3, 4], 1, xs, toY)).toEqual([[[10, 99], [20, 98]]])
    expect(visibleRuns([1, 2, 3, 4], 2, xs, toY)).toEqual([[[10, 99], [20, 98], [30, 97]]])
    expect(visibleRuns([1, 2, 3, 4], 3, xs, toY)).toEqual([[[10, 99], [20, 98], [30, 97], [40, 96]]])
  })
  it('shows the whole path from the last frame on, however far past it the frame is', () => {
    const whole = visibleRuns([1, 2, 3, 4], 3, xs, toY)
    expect(visibleRuns([1, 2, 3, 4], 4, xs, toY)).toEqual(whole)
    expect(visibleRuns([1, 2, 3, 4], 999, xs, toY)).toEqual(whole)
  })
  it('breaks the line at a null: [1, null, 3, 4] is two runs once day 2 is reached', () => {
    expect(visibleRuns([1, null, 3, 4], 1, xs, toY)).toEqual([[[10, 99]]])
    expect(visibleRuns([1, null, 3, 4], 2, xs, toY)).toEqual([[[10, 99]], [[30, 97]]])
    expect(visibleRuns([1, null, 3, 4], 3, xs, toY)).toEqual([[[10, 99]], [[30, 97], [40, 96]]])
  })
  it('never draws a null as a value: it does not call toY for it, and a leading null starts no run', () => {
    const spy = vi.fn(toY)
    expect(visibleRuns([null, 2, null, null], 3, xs, spy)).toEqual([[[20, 98]]])
    expect(spy.mock.calls).toEqual([[2]])
    expect(visibleRuns([null, null, null, null], 3, xs, toY)).toEqual([])
  })
  it('handles an empty path', () => {
    expect(visibleRuns([], 5, [], toY)).toEqual([])
  })
})

describe('runsToPath and bandPath', () => {
  it('writes one subpath per run: M for the first point, L for the others', () => {
    expect(runsToPath([[[10, 99], [20, 98], [30, 97]]])).toBe('M10 99 L20 98 L30 97')
    expect(runsToPath([[[10, 99]], [[30, 97], [40, 96]]])).toBe('M10 99h0 M30 97 L40 96')
    expect(runsToPath([])).toBe('')
  })
  it('rounds to two decimals and prints no trailing zeros', () => {
    expect(runsToPath([[[1.234, 5.678], [2, 3.5]]])).toBe('M1.23 5.68 L2 3.5')
    expect(runsToPath([[[0.001, -0.001], [1, 1]]])).toBe('M0 0 L1 1') // no "-0"
  })

  // lo = [1, 2, 3, 4], hi = [3, 4, 5, 6] at x = 10, 20, 30, 40 and toY(v) = 100 - v.
  const xs = [10, 20, 30, 40]
  const toY = (v: number) => 100 - v
  it('draws a band as the upper edge left to right, then the lower edge right to left, closed', () => {
    // upper edge hi: (10, 97) (20, 96) (30, 95) (40, 94); lower edge lo reversed: (40, 96) (30, 97) (20, 98) (10, 99)
    expect(bandPath(xs, [1, 2, 3, 4], [3, 4, 5, 6], toY)).toBe('M10 97 L20 96 L30 95 L40 94 L40 96 L30 97 L20 98 L10 99Z')
  })
  it('leaves a gap where an edge is null and splits the band into one polygon per stretch', () => {
    const x5 = [10, 20, 30, 40, 50]
    // stretch 0-1: hi (10, 97) (20, 96), lo reversed (20, 98) (10, 99); stretch 3-4: hi 6, 7 -> y 94, 93; lo 5, 4 reversed -> y 95 at x 50, y 96 at x 40
    expect(bandPath(x5, [1, 2, null, 4, 5], [3, 4, null, 6, 7], toY)).toBe('M10 97 L20 96 L20 98 L10 99Z M40 94 L50 93 L50 95 L40 96Z')
  })
  it('treats a null in either edge as a gap, and draws nothing for a stretch of a single day', () => {
    expect(bandPath(xs, [1, 2, 3, 4], [3, null, 5, 6], toY)).toBe('M30 95 L40 94 L40 96 L30 97Z')
    expect(bandPath(xs, [1, null, 3, null], [3, 4, 5, 6], toY)).toBe('')
    expect(bandPath(xs, [null, null, null, null], [null, null, null, null], toY)).toBe('')
    expect(bandPath([], [], [], toY)).toBe('')
  })
})

describe('xTickDays', () => {
  it('labels every multiple of 5: -10, -5, 0, 5, 10 for a -10..10 window', () => {
    expect(xTickDays(Array.from({ length: 21 }, (_, i) => i - 10))).toEqual([-10, -5, 0, 5, 10])
  })
  it('labels only the multiples that exist', () => {
    expect(xTickDays([-2, -1, 0, 1, 2])).toEqual([0])
    expect(xTickDays([1, 2, 3])).toEqual([])
    expect(xTickDays([])).toEqual([])
  })
})

describe('playback: reduced motion, play, pause, seek', () => {
  it('starts playing from the first frame when motion is allowed', () => {
    expect(initialPlayback(false, 20)).toEqual({ frame: 0, playing: true })
  })
  it('does NOT autoplay under reduced motion: it shows the finished picture, paused', () => {
    expect(initialPlayback(true, 20)).toEqual({ frame: 20, playing: false })
  })
  it('steps one frame per tick while playing', () => {
    expect(stepPlayback({ frame: 3, playing: true }, 20)).toEqual({ frame: 4, playing: true })
    expect(stepPlayback({ frame: 19, playing: true }, 20)).toEqual({ frame: 20, playing: true })
  })
  it('stops on the last frame, and never goes past it', () => {
    expect(stepPlayback({ frame: 20, playing: true }, 20)).toEqual({ frame: 20, playing: false })
    expect(stepPlayback({ frame: 25, playing: true }, 20)).toEqual({ frame: 20, playing: false })
  })
  it('does nothing on a tick while paused (the very same state comes back)', () => {
    const paused: Playback = { frame: 3, playing: false }
    expect(stepPlayback(paused, 20)).toBe(paused)
  })
  it('plays a whole animation of 3 frames: 0, 1, 2, then stops', () => {
    const seen: Playback[] = []
    let p = initialPlayback(false, 2)
    seen.push(p)
    while (p.playing) {
      p = stepPlayback(p, 2)
      seen.push(p)
    }
    expect(seen).toEqual([
      { frame: 0, playing: true },
      { frame: 1, playing: true },
      { frame: 2, playing: true },
      { frame: 2, playing: false },
    ])
  })
  it('toggle pauses while playing and keeps the frame', () => {
    expect(togglePlayback({ frame: 7, playing: true }, 20)).toEqual({ frame: 7, playing: false })
  })
  it('toggle resumes from where it paused', () => {
    expect(togglePlayback({ frame: 7, playing: false }, 20)).toEqual({ frame: 7, playing: true })
  })
  it('toggle restarts from the first frame when the animation had finished (also the reduced-motion start)', () => {
    expect(togglePlayback({ frame: 20, playing: false }, 20)).toEqual({ frame: 0, playing: true })
    expect(togglePlayback(initialPlayback(true, 20), 20)).toEqual({ frame: 0, playing: true })
  })
  it('seek goes to the frame, rounded and kept inside 0..last, and pauses', () => {
    expect(seekPlayback(7, 20)).toEqual({ frame: 7, playing: false })
    expect(seekPlayback(7.6, 20)).toEqual({ frame: 8, playing: false })
    expect(seekPlayback(-3, 20)).toEqual({ frame: 0, playing: false })
    expect(seekPlayback(99, 20)).toEqual({ frame: 20, playing: false })
    expect(seekPlayback(NaN, 20)).toEqual({ frame: 0, playing: false })
  })
  it('has a frame time of 400 ms (an animation of 21 days takes 8 seconds)', () => {
    expect(FRAME_MS).toBe(400)
  })
})
