/** Shared numeric formatting for consistent tabular display. */
export function fmt(n: number, dp = 2): string {
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp })
}

export function pct(n: number, dp = 2): string {
  if (!Number.isFinite(n)) return '—'
  return `${(n * 100).toFixed(dp)}%`
}

export function bps(n: number, dp = 1): string {
  if (!Number.isFinite(n)) return '—'
  return `${(n * 10_000).toFixed(dp)} bps`
}

/** A number exactly as the data file has it (no rounding, no arithmetic), or "—" for null (no value). */
export function asGiven(n: number | null): string {
  return n === null ? '—' : String(n)
}

/**
 * What a table shows in place of a p-value the exporter withheld as mis-sized: the G1 rejection rate under the
 * calibrated null, as a percent, and the number of replications it was measured on.
 */
export function withheldText(g1Size: number, g1Reps: number): string {
  return `withheld (G1 size ${pct(g1Size)} over ${g1Reps.toLocaleString('en-US')} replications)`
}

/**
 * What a table shows under the p-value of a primary whose gate-G1 size check failed (fix R1: the p-value is kept): the
 * rejection rate under the calibrated null, as a percent, and the number of replications it was measured on.
 */
export function sizeCheckFailedText(g1Size: number, g1Reps: number): string {
  return `size check failed: G1 size ${pct(g1Size)} over ${g1Reps.toLocaleString('en-US')} replications, liberal; a rejection would not be trusted`
}
