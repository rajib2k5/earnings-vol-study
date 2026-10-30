/**
 * "Results" page: draws `data/tests.json` exactly as the Python exporter wrote it. Every number is
 * shown as given (`asGiven`: no rounding, no arithmetic); the page does not work out a statistic, a
 * p-value or a Holm adjustment. It groups and orders rows (layout) and says, at the top, that the
 * timing labels behind every number are provisional, with the file's own look-up count and caveats.
 * A p-value the exporter withheld as mis-sized shows as "withheld" with the G1 rate the file gives (as a percent,
 * with the replications it was measured on), and
 * each table lists the file's row notes under it (for the primary family, its caption). The Holm p of a primary that has a
 * season-cut counterfactual (a row of the same hypothesis with subgroup_key "season_cut") shows that row's Holm p next to it,
 * with its number of clusters G. The Holm statement says which hypotheses of the declared family failed their G1 size check
 * and stay in the family (fix R1 of the milestone-4 review). The file is checked with `loadTests` first, and a missing or
 * invalid file shows an explicit error.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { asGiven, withheldText } from './format'
import { ProvisionalNotice } from './ProvisionalNotice'
import { groupByHypothesis, loadTests, rowsWithRole, TESTS_URL, type G1, type Holm, type TestRow, type TestsData } from './results'

type State = { status: 'loading' } | { status: 'ok'; tests: TestsData } | { status: 'error'; error: string }

interface Column {
  header: string
  cell: (r: TestRow) => ReactNode
  /** Numbers are set in the monospace face. */
  num?: boolean
}

/** The confidence interval as "[lo, hi]", or a dash when the row has none. */
const interval = (r: TestRow): string => (r.ci_lo === null && r.ci_hi === null ? '—' : `[${asGiven(r.ci_lo)}, ${asGiven(r.ci_hi)}]`)

/** Measure, with what it is measured in and how it was adjusted under it. */
const measureCell = (r: TestRow): ReactNode => (
  <>
    {r.measure}
    <div className="sub cell-note">
      {r.units} · {r.adjustment}-adjusted · {r.sample} sample{r.subgroup_key === 'all' ? '' : ` · ${r.subgroup_key}: ${r.subgroup_value}`}
    </div>
  </>
)

const N: Column = { header: 'n', cell: (r) => r.n, num: true }
const ESTIMATE: Column = { header: 'Estimate', cell: (r) => asGiven(r.estimate), num: true }
const SE: Column = { header: 'SE', cell: (r) => asGiven(r.se), num: true }
const CI: Column = { header: 'CI', cell: interval, num: true }
const STAT: Column = { header: 'Stat', cell: (r) => asGiven(r.stat), num: true }
const DF: Column = { header: 'df', cell: (r) => asGiven(r.df), num: true }
/** The p-value as given; a withheld one (null, with a G1 rate) says so and shows that rate, as a percent, and its replications instead. */
const pValue = (r: TestRow): string => (r.p_value === null && r.g1_size !== null ? withheldText(r.g1_size, Number(r.g1_reps)) : asGiven(r.p_value))
const P_VALUE: Column = { header: 'p', cell: pValue, num: true }
const MEASURE: Column = { header: 'Measure', cell: measureCell }
const STATISTIC: Column = { header: 'Statistic', cell: (r) => r.statistic }

/** The Holm p as given and, for each season-cut counterfactual of the same hypothesis, "(G = n: its Holm p)". */
const holmWithCuts = (rows: readonly TestRow[]) => (r: TestRow): string => {
  const cuts = r.hypothesis === null ? [] : rows.filter((c) => c.subgroup_key === 'season_cut' && c.hypothesis === r.hypothesis)
  return [asGiven(r.p_holm), ...cuts.map((c) => `(G = ${asGiven(c.n_clusters)}: ${asGiven(c.p_holm)})`)].join(' ')
}

/** The columns of the primary family; the Holm p cell looks up the season-cut rows among `rows`. */
const primaryColumns = (rows: readonly TestRow[]): Column[] => [
  { header: 'Hypothesis', cell: (r) => r.hypothesis ?? '—' },
  MEASURE,
  STATISTIC,
  N,
  ESTIMATE,
  SE,
  CI,
  STAT,
  DF,
  P_VALUE,
  { header: 'Holm p', cell: holmWithCuts(rows), num: true },
]
const ROBUSTNESS_COLUMNS: Column[] = [MEASURE, STATISTIC, { header: 'Estimand', cell: (r) => r.estimand ?? '—' }, N, ESTIMATE, SE, CI, STAT, DF, P_VALUE]
const EXPLORATORY_COLUMNS: Column[] = [MEASURE, STATISTIC, N, ESTIMATE, SE, CI, STAT, DF, P_VALUE, { header: 'q (BH)', cell: (r) => asGiven(r.q_bh), num: true }]

/** Which row a note belongs to: hypothesis, statistic and, when it is not "all", the subgroup. */
const rowName = (r: TestRow): string =>
  `${r.hypothesis ?? '—'} ${r.statistic}${r.subgroup_key === 'all' ? '' : ` (${r.subgroup_key}: ${r.subgroup_value})`}`

function RowsTable({ label, columns, rows }: { label: string; columns: Column[]; rows: TestRow[] }) {
  const noted = rows.filter((r) => r.note !== null)
  return (
    <div className="scroll-x">
      <table aria-label={label}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.header}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.header} className={c.num ? 'num' : undefined}>
                  {c.cell(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {noted.length > 0 && (
        <ul className="sub cell-note" aria-label={`${label} notes`}>
          {noted.map((r, i) => (
            <li key={i}>
              <strong>{rowName(r)}</strong>: {r.note}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const listOrNone = (names: readonly string[]): string => (names.length === 0 ? 'none' : names.join(', '))

function HolmStatement({ holm, g1, rows }: { holm: Holm; g1: G1; rows: readonly TestRow[] }) {
  // hypotheses of the declared family whose G1 size check failed: since fix R1 they stay in the family
  const failed = [...new Set(g1.calibrated.filter((c) => !c.pass && holm.family.includes(c.hypothesis)).map((c) => c.hypothesis))]
  const elsewhere = failed.filter((h) => !rows.some((r) => r.hypothesis === h))
  return (
    <>
      <ul aria-label="Holm statement">
        <li>Family: {listOrNone(holm.family)}</li>
        <li>Tested: {listOrNone(holm.tested)}</li>
        <li>Untested, entering the family as p = 1: {listOrNone(holm.untested)}</li>
        {holm.left_family.length > 0 && <li>Left the family: {holm.left_family.join(', ')}</li>}
      </ul>
      {failed.length > 0 && (
        <p className="sub" aria-label="Failed size checks">
          {failed.join(', ')} failed gate G1&apos;s size check and {failed.length === 1 ? 'stays' : 'stay'} in the family with {failed.length === 1 ? 'its p-value' : 'their p-values'}: the
          statistic is liberal on this design, so a rejection by it would not be trusted.
          {elsewhere.length > 0 && ` The rows of ${elsewhere.join(', ')} are on the Drivers page.`}
        </p>
      )}
    </>
  )
}

function G1Gate({ g1 }: { g1: G1 }) {
  return (
    <>
      <p className="sub">
        Simulated size check of the primary tests: {g1.reps} replications. Band: {g1.band[0]} to {g1.band[1]}. The verdict is the exporter&apos;s; the
        rejection rate is compared with the upper edge of the band.
      </p>
      <div className="scroll-x">
        <table aria-label="G1 calibration">
          <thead>
            <tr>
              <th>Hypothesis</th>
              <th>Statistic</th>
              <th>Rejection rate</th>
              <th>Band upper edge</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {g1.calibrated.map((c) => (
              <tr key={`${c.hypothesis}-${c.statistic}`}>
                <td>{c.hypothesis}</td>
                <td>{c.statistic}</td>
                <td className="num">{c.rejection_rate}</td>
                <td className="num">{g1.band[1]}</td>
                <td>
                  <span className={`badge ${c.pass ? '' : 'err-badge'}`}>{c.pass ? 'pass' : 'fail'}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Power</h3>
      <div className="scroll-x">
        <table aria-label="G1 power">
          <thead>
            <tr>
              <th>Hypothesis</th>
              <th>Smallest shift with 80% power</th>
              <th>Power at each shift</th>
            </tr>
          </thead>
          <tbody>
            {g1.power.map((p) => (
              <tr key={p.hypothesis}>
                <td>{p.hypothesis}</td>
                <td className="num">{p.detectable_80 === null ? 'not reached on the grid' : p.detectable_80}</td>
                <td className="num">{p.shifts.map((s, i) => `${s}: ${p.power[i]}`).join(' · ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details>
        <summary>Simulation calibration</summary>
        <table aria-label="G1 calibration parameters">
          <tbody>
            {Object.entries(g1.calibration).map(([name, value]) => (
              <tr key={name}>
                <td>{name}</td>
                <td className="num">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  )
}

export function ResultsDisplay({ tests }: { tests: TestsData }) {
  const primary = rowsWithRole(tests.rows, 'primary')
  const robustness = groupByHypothesis(rowsWithRole(tests.rows, 'robustness'))
  const exploratory = rowsWithRole(tests.rows, 'exploratory')
  return (
    <>
      <ProvisionalNotice lookups={tests.lookups} caveats={tests.caveats} />
      <p className="sub">
        The test results of the study. Python computes every number and writes the file; this page only draws it. Sample: <strong>{tests.provenance.sample_label}</strong>.
      </p>

      <h2>Primary family</h2>
      <RowsTable label="Primary family" columns={primaryColumns(tests.rows)} rows={primary} />

      <section aria-label="Robustness checks">
        <h2>Robustness checks</h2>
        {robustness.length === 0 && <p className="sub">The file has no robustness rows.</p>}
        {robustness.map((g) => {
          const name = g.hypothesis ?? 'No hypothesis'
          return (
            <div key={name}>
              <h3>{name}</h3>
              <RowsTable label={`Robustness ${name}`} columns={ROBUSTNESS_COLUMNS} rows={g.rows} />
            </div>
          )
        })}
      </section>

      <h2>Exploratory</h2>
      <details>
        <summary>Exploratory rows ({exploratory.length})</summary>
        <p className="sub">Not part of the primary family. q (BH) is the exporter&apos;s Benjamini-Hochberg adjustment within these rows.</p>
        <RowsTable label="Exploratory" columns={EXPLORATORY_COLUMNS} rows={exploratory} />
      </details>

      <h2>G1 gate: size and power</h2>
      <G1Gate g1={tests.g1} />

      <h2>Holm adjustment</h2>
      <HolmStatement holm={tests.holm} g1={tests.g1} rows={tests.rows} />
    </>
  )
}

export function ResultsPage({ url = TESTS_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the page unmounts or the url changes first
    loadTests(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', tests: r.data } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  return (
    <section className="results">
      <h2>Results</h2>
      {state.status === 'loading' && (
        <p className="sub" role="status">
          Loading results…
        </p>
      )}
      {state.status === 'error' && (
        <p className="sub" role="alert">
          <span className="badge err-badge">data error</span> The results could not be shown: {state.error}
        </p>
      )}
      {state.status === 'ok' && <ResultsDisplay tests={state.tests} />}
    </section>
  )
}
