/**
 * Layout and animation logic of the "Crush paths" chart, kept pure so it is testable without a
 * browser: scaling given values to pixels, which points of a path are visible at animation frame k,
 * the SVG path strings, and the play / pause / seek state machine. The component only wires a timer
 * to `stepPlayback`. None of this works out a result: it moves the file's numbers to pixels.
 *
 * Frames: an animation has one frame per event day. At frame k a path shows its points for day
 * indexes 0 .. k, so the paths grow from the left, one day per frame.
 */

/** Milliseconds one animation frame (one event day) stays on screen. */
export const FRAME_MS = 400

/** A pixel position: [x, y]. */
export type Point = readonly [number, number]

/** Size of the SVG and its margins (room for the axes), in pixels. The plot area is what is left inside. */
export const CHART = { width: 640, height: 320, left: 56, right: 16, top: 22, bottom: 34 } as const
export type ChartBox = { width: number; height: number; left: number; right: number; top: number; bottom: number }

/**
 * Linear map of `v` from the domain [d0, d1] to the range [r0, r1] (the range may run backwards, as
 * the y axis of a screen does). A domain with no width (d0 equal to d1) maps to the middle of the range.
 */
export function scaleLinear(v: number, d0: number, d1: number, r0: number, r1: number): number {
  if (d0 === d1) return (r0 + r1) / 2
  return r0 + ((v - d0) / (d1 - d0)) * (r1 - r0)
}

/** Smallest and largest finite number over all the arrays (null entries are skipped); null when there is none. */
export function extentOf(arrays: readonly (readonly (number | null)[])[]): [number, number] | null {
  let lo = Infinity
  let hi = -Infinity
  for (const a of arrays) {
    for (const v of a) {
      if (v === null || !Number.isFinite(v)) continue
      lo = Math.min(lo, v)
      hi = Math.max(hi, v)
    }
  }
  return lo <= hi ? [lo, hi] : null
}

/**
 * Like `extentOf`, but the extent always contains 0, so the zero line ("no abnormal IV") is inside the
 * chart. A chart with no number at all gets [0, 0].
 */
export function extentWithZero(arrays: readonly (readonly (number | null)[])[]): [number, number] {
  const e = extentOf(arrays)
  return e === null ? [0, 0] : [Math.min(e[0], 0), Math.max(e[1], 0)]
}

/**
 * The extent widened by `frac` of its width on each side, so lines do not touch the frame. An extent
 * with no width (flat data) is widened by 0.5 each side so the scale still has a span.
 */
export function padExtent([lo, hi]: readonly [number, number], frac: number): [number, number] {
  const pad = hi > lo ? (hi - lo) * frac : 0.5
  return [lo - pad, hi + pad]
}

/** `count` evenly spaced values from `lo` to `hi`, both included (count 1 gives just `lo`). */
export function linearTicks(lo: number, hi: number, count: number): number[] {
  if (count <= 1) return [lo]
  return Array.from({ length: count }, (_, i) => lo + ((hi - lo) * i) / (count - 1))
}

/** Pixel x of each event day: the first day at the left edge of the plot area, the last at the right edge. */
export function xPixels(days: readonly number[], box: ChartBox = CHART): number[] {
  const first = days[0]
  const last = days[days.length - 1]
  return days.map((d) => scaleLinear(d, first, last, box.left, box.width - box.right))
}

/** Pixel y of a value, for a given [lo, hi] extent: `lo` at the bottom of the plot area, `hi` at the top. */
export function yScale(extent: readonly [number, number], box: ChartBox = CHART): (v: number) => number {
  return (v) => scaleLinear(v, extent[0], extent[1], box.height - box.bottom, box.top)
}

/**
 * The visible part of one path at animation `frame`: its points for day indexes 0 .. frame, as runs
 * of consecutive non-null values (a null day breaks the line, it is never drawn as 0). `xs` holds the
 * pixel x of each day and `toY` maps a value to pixel y. A frame before the first day shows nothing;
 * a frame past the last day shows the whole path.
 */
export function visibleRuns(values: readonly (number | null)[], frame: number, xs: readonly number[], toY: (v: number) => number): Point[][] {
  const runs: Point[][] = []
  let current: Point[] | null = null
  const last = Math.min(frame, values.length - 1)
  for (let i = 0; i <= last; i++) {
    const v = values[i]
    if (v === null) {
      current = null
      continue
    }
    if (current === null) {
      current = []
      runs.push(current)
    }
    current.push([xs[i], toY(v)])
  }
  return runs
}

/** A pixel coordinate for an SVG path: two decimals at most, no trailing zeros. */
const px = (n: number): string => String(Math.round(n * 100) / 100)

/**
 * SVG path data for runs of points: "M x y L x y ...", one subpath per run. A run of a single point
 * is drawn as a zero-length line ("M x y h0"), which a round line cap shows as a dot.
 */
export function runsToPath(runs: readonly (readonly Point[])[]): string {
  return runs
    .map((run) =>
      run.length === 1
        ? `M${px(run[0][0])} ${px(run[0][1])}h0`
        : run.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${px(x)} ${px(y)}`).join(' '),
    )
    .join(' ')
}

/**
 * SVG path data of the confidence band: for every stretch of at least two consecutive days where both
 * edges are there, a closed polygon along the upper edge and back along the lower edge. Days with a
 * null edge leave a gap in the band.
 */
export function bandPath(xs: readonly number[], lo: readonly (number | null)[], hi: readonly (number | null)[], toY: (v: number) => number): string {
  const parts: string[] = []
  let start = 0
  const flush = (end: number) => {
    if (end - start >= 2) {
      const top = []
      const bottom = []
      for (let i = start; i < end; i++) {
        top.push(`${px(xs[i])} ${px(toY(hi[i] as number))}`)
        bottom.unshift(`${px(xs[i])} ${px(toY(lo[i] as number))}`)
      }
      parts.push(`M${[...top, ...bottom].join(' L')}Z`)
    }
  }
  for (let i = 0; i < xs.length; i++) {
    if (lo[i] === null || hi[i] === null) {
      flush(i)
      start = i + 1
    }
  }
  flush(xs.length)
  return parts.join(' ')
}

/** The animation state: which frame is shown and whether the timer is running. */
export interface Playback {
  frame: number
  playing: boolean
}

/**
 * Where the animation starts. Under reduced motion it does not play by itself and shows every
 * frame at once (the finished picture); otherwise it plays from the first frame.
 */
export function initialPlayback(reducedMotion: boolean, lastFrame: number): Playback {
  return reducedMotion ? { frame: lastFrame, playing: false } : { frame: 0, playing: true }
}

/** One timer tick: the next frame; on the last frame the animation stops there. Does nothing while paused. */
export function stepPlayback(p: Playback, lastFrame: number): Playback {
  if (!p.playing) return p
  if (p.frame >= lastFrame) return { frame: lastFrame, playing: false }
  return { frame: p.frame + 1, playing: true }
}

/** The Play / Pause button: pause when playing; otherwise play, from the start if the animation had finished. */
export function togglePlayback(p: Playback, lastFrame: number): Playback {
  if (p.playing) return { frame: p.frame, playing: false }
  return { frame: p.frame >= lastFrame ? 0 : p.frame, playing: true }
}

/** Jump to a frame (the slider): rounded, kept inside 0 .. lastFrame, and paused so the timer does not fight the viewer. */
export function seekPlayback(frame: number, lastFrame: number): Playback {
  const f = Number.isFinite(frame) ? Math.round(frame) : 0
  return { frame: Math.min(Math.max(f, 0), lastFrame), playing: false }
}

/** The event days that get a label on the x axis: every multiple of 5 (-10, -5, 0, 5, 10 for a -10 .. 10 window). */
export const xTickDays = (days: readonly number[]): number[] => days.filter((d) => d % 5 === 0)
