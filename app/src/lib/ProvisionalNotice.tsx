/**
 * The "timing labels are provisional" notice that goes at the top of every page that shows a result.
 * It is built from the file's own `lookups` (how many timing look-ups are done, and whether that is
 * all of them) and lists every caveat of the file, so what the page says is what Python wrote.
 */
import type { Lookups } from './dataParts'

export function ProvisionalNotice({ lookups, caveats }: { lookups: Lookups; caveats: readonly string[] }) {
  return (
    <aside className={`provisional${lookups.complete ? ' provisional-done' : ''}`} aria-label="Provisional timing labels">
      <p className="provisional-head">
        <span className={`badge ${lookups.complete ? '' : 'warn-badge'}`}>{lookups.complete ? 'complete' : 'provisional'}</span>
        {lookups.complete
          ? `Timing look-ups are complete: ${lookups.n_done} done.`
          : `Timing labels are provisional: ${lookups.n_done} timing look-ups are done and the look-ups are not complete, so some events may sit on the wrong day 0. Every number on this page depends on those labels.`}
      </p>
      {caveats.length > 0 && (
        <ul aria-label="Caveats" className="sub">
          {caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </aside>
  )
}
