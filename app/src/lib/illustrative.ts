/**
 * ILLUSTRATIVE synthetic data for the milestone-0 3D preview. It is NOT market data and NOT a
 * result: it only draws the stylised shape the study is looking for (implied volatility ramping
 * up into the announcement, peaking on day 0, then "crushing" back). Seeded, so it never changes.
 */
import { gaussian, mulberry32 } from './rng'

/** Shown on-screen next to every illustrative visual. The wording is part of the requirement. */
export const ILLUSTRATIVE_LABEL = 'Illustrative synthetic shape — not data'

/** Event days shown on the x axis: -10 ... +10 relative to the announcement. */
export const EVENT_DAYS: readonly number[] = Array.from({ length: 21 }, (_, i) => i - 10)

/** Stylised IV bump (0..1) for an event day: convex run-up, peak at day 0, fast decay. */
export function ivBump(day: number): number {
  if (day < 0) return ((day + 10) / 10) ** 2 // 0 at day -10, 0.81 at day -1
  if (day === 0) return 1
  return 0.15 * Math.exp(-(day - 1) / 3) // crush: well below the pre-event level, then fades
}

/**
 * Grid `values[company][eventDayIndex]` of illustrative IV levels (vol points).
 * Each company has its own baseline level, run-up size and a little noise.
 */
export function illustrativeIvGrid(seed: number, companies = 24): number[][] {
  const rand = mulberry32(seed)
  return Array.from({ length: companies }, () => {
    const base = 25 + 20 * rand() // 25-45 vol points
    const amp = 0.2 + 0.3 * rand() // run-up of 20-50% of the baseline
    return EVENT_DAYS.map((d) => base * (1 + amp * ivBump(d)) + 0.4 * gaussian(rand))
  })
}
