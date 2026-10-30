/**
 * Layout of the two milestone-4 charts, kept pure so it is testable without a browser: round axis ticks, the
 * pixel position of every dot of the implied-versus-realised scatter, and of every row of the coefficient (forest)
 * plot. The components only draw what this returns. None of it works out a result: it moves the file's numbers to pixels
 * (`scaleLinear` and `ChartBox` come from `pathFrames.ts`).
 */
import { scaleLinear, type ChartBox } from './pathFrames'

/**
 * The step of a round tick sequence (1, 2, 2.5 or 5 times a power of ten) that is the smallest one covering
 * `span` in at most `maxIntervals` steps. `span` and `maxIntervals` must be positive.
 */
export function niceStep(span: number, maxIntervals: number): number {
  const raw = span / maxIntervals
  const base = 10 ** Math.floor(Math.log10(raw))
  const mantissa = [1, 2, 2.5, 5].find((m) => m * base >= raw) ?? 10
  return mantissa * base
}

/**
 * Round ticks that cover [lo, hi]: multiples of `niceStep`, from the one at or below `lo` to the one at or above `hi`, with at
 * most `maxIntervals` steps between them (one more when the range does not start on a tick). A range with no width (lo equal to hi)
 * gets the ticks lo - 1, lo and lo + 1.
 */
export function niceTicks(lo: number, hi: number, maxIntervals = 6): number[] {
  if (lo === hi) return [lo - 1, lo, lo + 1]
  const step = niceStep(hi - lo, maxIntervals)
  const first = Math.floor(lo / step + 1e-9)
  const last = Math.ceil(hi / step - 1e-9)
  // 12 significant digits: i * 0.1 would otherwise come out as 0.30000000000000004
  return Array.from({ length: last - first + 1 }, (_, i) => Number(((first + i) * step).toPrecision(12)))
}

/**
 * A label for an axis tick: the tick as it is, without float noise or trailing zeros ("0.05", "-0.015", "1.25", "0").
 * Ticks are round numbers (`niceTicks`) with up to three digits (0.125, 1.25), so they are not shortened: a tick at 1.25 must not read 1.3.
 */
export const tickLabel = (v: number): string => String(Number(v.toPrecision(12)))

/** A label for a tick of an axis that holds fractions, shown as percents: 0.025 is "2.5%", 0.3 is "30%". */
export const percentTickLabel = (v: number): string => `${tickLabel(v * 100)}%`

/** `text` cut to at most `max` characters, the last one being "…" when something was cut. */
export const truncateLabel = (text: string, max: number): string => (text.length <= max ? text : `${text.slice(0, Math.max(max - 1, 0))}…`)

/** The plot area of a chart in pixels: inside the margins that hold the axes and their labels. */
export interface PlotArea {
  left: number
  right: number
  top: number
  bottom: number
}

export const plotArea = (box: ChartBox): PlotArea => ({ left: box.left, right: box.width - box.right, top: box.top, bottom: box.height - box.bottom })

// ---- scatter: expected |move| (x) against realised |move| (y) ----

/** Square plot area (448 by 448 pixels) so a 45 degree line really is y = x. */
export const SCATTER_BOX: ChartBox = { width: 520, height: 520, left: 56, right: 16, top: 16, bottom: 56 }

/** What the scatter needs of an event. */
export interface ScatterSource {
  event_id: string
  ticker: string
  day0: string
  timing_used: 'BMO' | 'AMC' | null
  implied_abs_move_total: number | null
  abs_realized: number
}

export interface ScatterDot {
  id: string
  /** "TICKER day0", for the hover title. */
  label: string
  timing: 'BMO' | 'AMC' | null
  /** The values behind the pixels, as written in the file. */
  x: number
  y: number
  cx: number
  cy: number
}

export interface ScatterLayout {
  box: ChartBox
  plot: PlotArea
  /** Round ticks, the same on both axes; the first is 0 and the last is the axis maximum. */
  ticks: number[]
  /** Pixel x of each tick on the x axis, and pixel y of each tick on the y axis. */
  tickX: number[]
  tickY: number[]
  /** Pixel centre of the plot area, where the axis titles are centred. */
  centre: { x: number; y: number }
  dots: ScatterDot[]
  /** The line y = x, from the origin to the top right corner of the plot area. */
  diagonal: { x1: number; y1: number; x2: number; y2: number }
  /** Events left out because the file gives no expected move for them. */
  withoutImplied: number
}

/**
 * Pixel layout of the scatter. Only events with an expected |move| are drawn (the others are counted in `withoutImplied`),
 * on two axes that start at 0 and share the same round maximum, which covers the largest value of either variable.
 */
export function scatterLayout(points: readonly ScatterSource[], box: ChartBox = SCATTER_BOX): ScatterLayout {
  const plotted = points.flatMap((p) => (p.implied_abs_move_total === null ? [] : [{ p, x: p.implied_abs_move_total }]))
  const biggest = plotted.length === 0 ? 0 : Math.max(...plotted.flatMap(({ p, x }) => [x, p.abs_realized]))
  const ticks = niceTicks(0, biggest > 0 ? biggest : 1)
  const max = ticks[ticks.length - 1]
  const plot = plotArea(box)
  const toX = (v: number) => scaleLinear(v, 0, max, plot.left, plot.right)
  const toY = (v: number) => scaleLinear(v, 0, max, plot.bottom, plot.top)
  return {
    box,
    plot,
    ticks,
    tickX: ticks.map(toX),
    tickY: ticks.map(toY),
    centre: { x: (plot.left + plot.right) / 2, y: (plot.top + plot.bottom) / 2 },
    dots: plotted.map(({ p, x }) => ({
      id: p.event_id,
      label: `${p.ticker} ${p.day0}`,
      timing: p.timing_used,
      x,
      y: p.abs_realized,
      cx: toX(x),
      cy: toY(p.abs_realized),
    })),
    diagonal: { x1: plot.left, y1: plot.bottom, x2: plot.right, y2: plot.top },
    withoutImplied: points.length - plotted.length,
  }
}

// ---- forest plot: one coefficient with its interval per row ----

/** What a forest row needs of a term. */
export interface ForestSource {
  label: string
  coef: number
  ci_lo: number | null
  ci_hi: number | null
}

export interface ForestRowLayout {
  /** The label, cut to fit the left margin; `full` is the whole label for the hover title. */
  label: string
  full: string
  y: number
  x: number
  /** Pixel ends of the interval; both null when the row has no (or only half an) interval and only the point is drawn. */
  x1: number | null
  x2: number | null
}

export interface ForestLayout {
  box: ChartBox
  plot: PlotArea
  ticks: number[]
  tickX: number[]
  /** Pixel x of the zero line. */
  zeroX: number
  rows: ForestRowLayout[]
}

/** Height of one row of the forest plot, in pixels, and the longest label that fits the left margin. */
export const FOREST_ROW = 26
export const FOREST_LABEL_MAX = 34

/** Size of a forest plot with `rows` rows: fixed width and margins, a height that grows by `FOREST_ROW` per row. */
export const forestBox = (rows: number): ChartBox => ({ width: 640, height: 24 + rows * FOREST_ROW + 40, left: 230, right: 24, top: 24, bottom: 40 })

/**
 * Pixel layout of a forest plot. The x axis covers every coefficient and interval end and always contains 0 (the zero line
 * is the null of every term); a row without an interval keeps its point, and a row with one end only is drawn as a point.
 * An empty list gives a plot of the axis alone around 0.
 */
export function forestLayout(sources: readonly ForestSource[]): ForestLayout {
  const box = forestBox(sources.length)
  const values = sources.flatMap((s) => [s.coef, s.ci_lo, s.ci_hi]).filter((v): v is number => v !== null)
  const ticks = niceTicks(Math.min(...values, 0), Math.max(...values, 0))
  const lo = ticks[0]
  const hi = ticks[ticks.length - 1]
  const plot = plotArea(box)
  const toX = (v: number) => scaleLinear(v, lo, hi, plot.left, plot.right)
  return {
    box,
    plot,
    ticks,
    tickX: ticks.map(toX),
    zeroX: toX(0),
    rows: sources.map((s, i) => {
      const hasInterval = s.ci_lo !== null && s.ci_hi !== null
      return {
        label: truncateLabel(s.label, FOREST_LABEL_MAX),
        full: s.label,
        y: box.top + (i + 0.5) * FOREST_ROW,
        x: toX(s.coef),
        x1: hasInterval ? toX(s.ci_lo as number) : null,
        x2: hasInterval ? toX(s.ci_hi as number) : null,
      }
    }),
  }
}
