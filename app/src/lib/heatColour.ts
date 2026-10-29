/**
 * Colours for the Heatmap page: a diverging scale that is symmetric around 0 and spans each grid's own
 * largest absolute value, so 0 is always the neutral colour and +x and -x are equally strong. It is
 * a layout transform of the file's numbers into colours; no statistic is worked out here.
 */

type Rgb255 = readonly [number, number, number]

/** The end of the scale for the most negative value (blue), the middle (near white) and the most positive (red). */
export const HEAT_NEGATIVE: Rgb255 = [33, 102, 172]
export const HEAT_NEUTRAL: Rgb255 = [247, 247, 247]
export const HEAT_POSITIVE: Rgb255 = [178, 24, 43]

/** The largest absolute value among the non-null cells of a grid, or 0 when every cell is null. */
export function maxAbs(values: readonly (readonly (number | null)[])[]): number {
  let m = 0
  for (const row of values) {
    for (const v of row) {
      if (v !== null && Number.isFinite(v)) m = Math.max(m, Math.abs(v))
    }
  }
  return m
}

const css = (c: Rgb255): string => `rgb(${c[0]},${c[1]},${c[2]})`

/**
 * CSS colour of a cell, or null when the cell has no value (the page draws it empty; null is never
 * treated as 0). The strength is |value| against `maxAbsValue`, capped at 1; the channels are
 * blended linearly from the neutral colour to the end colour of the value's sign and rounded.
 * A `maxAbsValue` of 0 (a grid of zeros) leaves every cell neutral.
 */
export function heatColour(value: number | null, maxAbsValue: number): string | null {
  if (value === null || !Number.isFinite(value)) return null
  const t = maxAbsValue > 0 ? Math.min(1, Math.abs(value) / maxAbsValue) : 0
  const end = value < 0 ? HEAT_NEGATIVE : HEAT_POSITIVE
  return css([0, 1, 2].map((i) => Math.round(HEAT_NEUTRAL[i] + (end[i] - HEAT_NEUTRAL[i]) * t)) as unknown as Rgb255)
}

/** The legend bar: the scale from -max to +max, left to right. */
export const HEAT_LEGEND_GRADIENT = `linear-gradient(to right, ${css(HEAT_NEGATIVE)}, ${css(HEAT_NEUTRAL)}, ${css(HEAT_POSITIVE)})`

/** The two end labels of the legend: "-max" and "+max", or "0" and "0" for a grid whose cells are all 0 (or empty). */
export function legendLabels(maxAbsValue: number): [string, string] {
  return maxAbsValue > 0 ? [`-${maxAbsValue}`, `+${maxAbsValue}`] : ['0', '0']
}
