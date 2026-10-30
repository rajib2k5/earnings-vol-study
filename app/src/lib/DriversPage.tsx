/**
 * "Drivers" page: draws `data/drivers.json` exactly as the Python exporter wrote it. Every number is shown as
 * given (`asGiven`: no rounding, no arithmetic) except the rejection rates of gate G1, which are shown as percents;
 * the page does not work out a coefficient, a standard error, a p-value or a Holm adjustment. It orders and lays out
 * (the pixel work of the coefficient plots is in `chartLayout.ts`) and says, at the top, that the timing labels behind
 * every number are provisional, with the file's own look-up count and caveats.
 *
 * Top to bottom: gate G1 for the hypotheses of the driver regressions (H5 to H7), with its verdict as the exporter
 * wrote it and a note when a primary statistic failed (since fix R1 such a hypothesis stays in the declared family with
 * its p-value); the Holm statement (Holm runs over the declared family), with the post-gate sensitivity (the Holm p over
 * the family without the hypotheses whose G1 check failed, and the season cut; labelled descriptive, never the binding
 * p); the power table; then the file's caveats on the exploratory p and q next to the coefficient tables, and every
 * model in file order (the first is the primary crush model) with a coefficient plot of its two-way rows and a table of
 * all its rows. A robustness p-value the exporter withheld as mis-sized shows as "withheld" with the G1 rate the file
 * gives; a primary whose size check failed shows its p-value with that rate under it. The file is checked with
 * `loadDrivers` first, and a missing or invalid file shows an explicit error.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { forestLayout, tickLabel } from './chartLayout'
import { failedHypotheses, forestTerms, DRIVERS_URL, loadDrivers, type DriverModel, type DriversData, type DriversG1, type DriversHolm, type DriverTerm } from './drivers'
import { asGiven, pct, sizeCheckFailedText, withheldText } from './format'
import { ProvisionalNotice } from './ProvisionalNotice'

type State = { status: 'loading' } | { status: 'ok'; drivers: DriversData } | { status: 'error'; error: string }

const listOrNone = (names: readonly string[]): string => (names.length === 0 ? 'none' : names.join(', '))

function G1Gate({ g1, holm }: { g1: DriversG1; holm: DriversHolm }) {
  const failed = failedHypotheses(g1.calibrated)
  const staying = failed.filter((h) => holm.family.includes(h))
  return (
    <>
      <p className="sub">
        Simulated size check of the tests of the driver regressions: {g1.reps.toLocaleString('en-US')} replications. Band: {pct(g1.band[0])} to {pct(g1.band[1])}. The verdict is the
        exporter&apos;s; the rejection rate under the calibrated null is compared with the upper edge of the band.
      </p>
      <p className="gate-note" role="note" aria-label="Gate G1 verdict">
        {failed.length === 0
          ? 'Every primary statistic passed gate G1.'
          : `Gate G1 failed for ${failed.join(', ')}: under the calibrated null the primary statistic rejects more often than the upper edge of the band (${pct(g1.band[1])}) allows.`}
        {staying.length > 0 &&
          ` ${staying.join(', ')} stay${staying.length === 1 ? 's' : ''} in the declared Holm family with ${staying.length === 1 ? 'its' : 'their'} p-value${staying.length === 1 ? '' : 's'} and Holm p: the statistic is liberal on this design, so a rejection by it would not be trusted.`}
        {holm.left_family.length > 0 && ` ${holm.left_family.join(', ')} left the family: not Holm-adjusted.`}
      </p>
      <div className="scroll-x">
        <table aria-label="G1 calibration">
          <thead>
            <tr>
              <th>Hypothesis</th>
              <th>Statistic</th>
              <th>Primary</th>
              <th>Rejection rate</th>
              <th>Replications</th>
              <th>Band upper edge</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {g1.calibrated.map((c) => (
              <tr key={`${c.hypothesis}-${c.statistic}`}>
                <td>{c.hypothesis}</td>
                <td>{c.statistic}</td>
                <td>{c.primary ? 'yes' : 'no'}</td>
                <td className="num">{pct(c.rejection_rate)}</td>
                <td className="num">{c.reps.toLocaleString('en-US')}</td>
                <td className="num">{pct(g1.band[1])}</td>
                <td>
                  <span className={`badge ${c.pass ? '' : 'err-badge'}`}>{c.pass ? 'pass' : 'fail'}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details>
        <summary>Rejection rates under the other simulation designs ({g1.designs.length})</summary>
        <div className="scroll-x">
          <table aria-label="G1 designs">
            <thead>
              <tr>
                <th>Design</th>
                <th>Hypothesis</th>
                <th>Statistic</th>
                <th>Primary</th>
                <th>Rejection rate</th>
              </tr>
            </thead>
            <tbody>
              {g1.designs.map((d) => (
                <tr key={`${d.design}-${d.hypothesis}-${d.statistic}`}>
                  <td>{d.design}</td>
                  <td>{d.hypothesis}</td>
                  <td>{d.statistic}</td>
                  <td>{d.primary ? 'yes' : 'no'}</td>
                  <td className="num">{pct(d.rejection_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <details>
        <summary>H7 simulation calibration</summary>
        <table aria-label="H7 calibration parameters">
          <tbody>
            {Object.entries(g1.calibration_h7).map(([name, value]) => (
              <tr key={name}>
                <td>{name}</td>
                <td className="num">{asGiven(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  )
}

function HolmStatement({ holm }: { holm: DriversHolm }) {
  const { post_gate: postGate } = holm
  const dropped = holm.family.filter((h) => !postGate.family.includes(h))
  return (
    <>
      <ul aria-label="Holm statement">
        <li>Holm runs over the declared family: {listOrNone(holm.family)}</li>
        {holm.left_family.length > 0 && <li>Left the family: {holm.left_family.join(', ')}</li>}
      </ul>
      <p className="sub">
        The binding Holm p-values are the ones of the declared family: in the tables below for the driver hypotheses, and on the Results page for the others.
      </p>
      <div className="scroll-x">
        <table aria-label="Holm sensitivity">
          <caption className="sub">
            Descriptive sensitivity, not binding: the Holm p over the family without the hypotheses whose G1 size check failed ({listOrNone(dropped)}).
          </caption>
          <thead>
            <tr>
              <th>Row</th>
              <th>Holm p without {listOrNone(dropped)}</th>
            </tr>
          </thead>
          <tbody>
            {postGate.family.map((h) => (
              <tr key={h}>
                <td>{h}</td>
                <td className="num">{asGiven(postGate.p_holm[h])}</td>
              </tr>
            ))}
            {Object.entries(postGate.season_cut).map(([h, p]) => (
              <tr key={`${h}-cut`}>
                <td>{h} season cut</td>
                <td className="num">{asGiven(p)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function PowerTable({ g1 }: { g1: DriversG1 }) {
  return (
    <div className="scroll-x">
      <table aria-label="G1 power">
        <thead>
          <tr>
            <th>Hypothesis</th>
            <th>Shift of</th>
            <th>Smallest shift with 80% power</th>
            <th>Power at each shift</th>
          </tr>
        </thead>
        <tbody>
          {g1.power.map((p) => (
            <tr key={p.hypothesis}>
              <td>{p.hypothesis}</td>
              <td>{p.kind}</td>
              <td className="num">{p.detectable_80 === null ? 'not reached on the grid' : p.detectable_80}</td>
              <td className="num">{p.shifts.map((s, i) => `${s}: ${p.power[i]}`).join(' · ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface Column {
  header: string
  cell: (t: DriverTerm) => ReactNode
  /** The class of the cells: "num" sets numbers in the monospace face. */
  className?: string
}

/** The interval as "[lo, hi]", or a dash when the row has none (a withheld row, or a Wald test). */
const interval = (t: DriverTerm): string => (t.ci_lo === null && t.ci_hi === null ? '—' : `[${asGiven(t.ci_lo)}, ${asGiven(t.ci_hi)}]`)
/**
 * The p-value as given; a withheld one (null, with a G1 rate) says so and shows that rate and its replications instead.
 * A primary whose size check failed keeps its p-value, with that rate under it.
 */
function pValue(t: DriverTerm): ReactNode {
  if (t.g1_size === null) return asGiven(t.p_value)
  if (t.p_value === null) return withheldText(t.g1_size, Number(t.g1_reps))
  return (
    <>
      {t.p_value}
      <div className="sub cell-note">{sizeCheckFailedText(t.g1_size, Number(t.g1_reps))}</div>
    </>
  )
}
/** The degrees of freedom as given; a Wald test gives numerator and denominator ("2, 49"). */
const dof = (t: DriverTerm): string => (t.df_num === null ? asGiven(t.df) : `${t.df_num}, ${asGiven(t.df)}`)

const TERM_COLUMNS: Column[] = [
  {
    header: 'Term',
    cell: (t) => (
      <>
        {t.label}
        <div className="sub cell-note">{t.term}</div>
      </>
    ),
  },
  { header: 'Hypothesis', cell: (t) => t.hypothesis ?? '—' },
  { header: 'Role', cell: (t) => t.role },
  {
    header: 'Statistic',
    cell: (t) => (
      <>
        {t.statistic}
        <div className="sub cell-note">{t.cov_type}</div>
      </>
    ),
  },
  { header: 'Coef', cell: (t) => asGiven(t.coef), className: 'num' },
  { header: 'SE', cell: (t) => asGiven(t.se), className: 'num' },
  { header: 'CI', cell: interval, className: 'num' },
  { header: 't (F for a Wald test)', cell: (t) => asGiven(t.t), className: 'num' },
  { header: 'df', cell: dof, className: 'num' },
  { header: 'p', cell: pValue, className: 'num' },
  { header: 'q (BH)', cell: (t) => asGiven(t.q_bh), className: 'num' },
  { header: 'Holm p', cell: (t) => asGiven(t.p_holm), className: 'num' },
  { header: 'Note', cell: (t) => t.note ?? '—', className: 'note-cell cell-note' },
]

function TermsTable({ label, terms }: { label: string; terms: DriverTerm[] }) {
  return (
    <div className="scroll-x">
      <table aria-label={label}>
        <thead>
          <tr>
            {TERM_COLUMNS.map((c) => (
              <th key={c.header}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {terms.map((t, i) => (
            <tr key={i}>
              {TERM_COLUMNS.map((c) => (
                <td key={c.header} className={c.className}>
                  {c.cell(t)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** The coefficient of every two-way row with its interval; a row without an interval (withheld) shows its point only, hollow. */
function ForestPlot({ model, caption }: { model: DriverModel; caption: string }) {
  const terms = forestTerms(model)
  if (terms.length === 0) return <p className="sub">The model has no two-way coefficient to plot.</p>
  const layout = forestLayout(terms.map((t) => ({ label: t.label, coef: t.coef, ci_lo: t.ci_lo, ci_hi: t.ci_hi })))
  const { box, plot } = layout
  return (
    <svg className="path-chart forest" viewBox={`0 0 ${box.width} ${box.height}`} role="img" aria-label={caption}>
      <g className="axes">
        {layout.ticks.map((t, i) => (
          <g key={t}>
            <line className="grid-line" x1={layout.tickX[i]} x2={layout.tickX[i]} y1={plot.top} y2={plot.bottom} />
            <text className="tick" x={layout.tickX[i]} y={plot.bottom + 16} textAnchor="middle">
              {tickLabel(t)}
            </text>
          </g>
        ))}
        <line className="day0-line" x1={layout.zeroX} x2={layout.zeroX} y1={plot.top} y2={plot.bottom} />
        <text className="tick" x={plot.left} y={box.height - 4}>
          coefficient (dashed line: zero)
        </text>
      </g>
      {layout.rows.map((r, i) => {
        const t = terms[i]
        return (
          <g key={i} className="forest-row">
            <text className="row-label" x={plot.left - 8} y={r.y} textAnchor="end" dominantBaseline="middle">
              {r.label}
            </text>
            {r.x1 !== null && r.x2 !== null && <line className="forest-ci" x1={r.x1} x2={r.x2} y1={r.y} y2={r.y} />}
            <circle className={`forest-point${r.x1 === null ? ' withheld' : ''}`} cx={r.x} cy={r.y} r={4.5}>
              <title>
                {r.full}: coef {asGiven(t.coef)}, interval {r.x1 === null ? 'withheld' : interval(t)}
              </title>
            </circle>
          </g>
        )
      })}
    </svg>
  )
}

function ModelSection({ model, index }: { model: DriverModel; index: number }) {
  const heading = `Model ${index + 1}: ${model.label}`
  return (
    <section aria-label={heading}>
      <h3>
        {heading}
        {index === 0 && <span className="badge warn-badge model-badge">primary model</span>}
      </h3>
      <p className="sub cell-note">
        {model.dep_var} · {model.adjustment}-adjusted · {model.sample} sample · fixed effects: {listOrNone(model.fixed_effects)} · n = {model.n} · date clusters{' '}
        {asGiven(model.n_clusters_date)} · firm clusters {asGiven(model.n_clusters_firm)} · R² {asGiven(model.r2)}
      </p>
      <ForestPlot model={model} caption={`Coefficients of model ${index + 1}, ${model.label}, with intervals`} />
      <TermsTable label={`Model ${index + 1} terms`} terms={model.terms} />
    </section>
  )
}

/** The file's caveats about the exploratory p and q: shown again next to the coefficient tables they qualify (fix R7). */
const tableCaveats = (caveats: readonly string[]): string[] => caveats.filter((c) => /exploratory/i.test(c))

export function DriversDisplay({ drivers }: { drivers: DriversData }) {
  const nearTables = tableCaveats(drivers.caveats)
  return (
    <>
      <ProvisionalNotice lookups={drivers.lookups} caveats={drivers.caveats} />
      <p className="sub">
        What drives the crush: regressions of the crush on the earnings surprise and the prior level of volatility, and of the realised on the implied variance. Python computes every number
        and writes the file; this page only draws it. Sample: <strong>{drivers.provenance.sample_label}</strong>.
      </p>

      <h2>Gate G1 for the driver tests</h2>
      <G1Gate g1={drivers.g1} holm={drivers.holm} />

      <h2>Holm adjustment</h2>
      <HolmStatement holm={drivers.holm} />

      <h2>Power</h2>
      <PowerTable g1={drivers.g1} />

      <h2>Models</h2>
      {nearTables.length > 0 && (
        <ul className="gate-note" aria-label="Caveats on the coefficient tables">
          {nearTables.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
      {drivers.models.length === 0 && <p className="sub">The file has no models.</p>}
      {drivers.models.map((m, i) => (
        <ModelSection key={i} model={m} index={i} />
      ))}
    </>
  )
}

export function DriversPage({ url = DRIVERS_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the page unmounts or the url changes first
    loadDrivers(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', drivers: r.data } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  return (
    <section className="results drivers">
      <h2>Drivers</h2>
      {state.status === 'loading' && (
        <p className="sub" role="status">
          Loading drivers…
        </p>
      )}
      {state.status === 'error' && (
        <p className="sub" role="alert">
          <span className="badge err-badge">data error</span> The drivers could not be shown: {state.error}
        </p>
      )}
      {state.status === 'ok' && <DriversDisplay drivers={state.drivers} />}
    </section>
  )
}
