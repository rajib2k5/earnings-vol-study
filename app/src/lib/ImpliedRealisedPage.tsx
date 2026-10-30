/**
 * "Implied vs realised" page: draws `data/implied_vs_realised.json` exactly as the Python exporter wrote it. A scatter
 * of the absolute move the options implied (x, from the day before the announcement) against the absolute move that was
 * realised (y, on day 0), one dot per event, with the line y = x: a dot above the line moved more than the options expected.
 * BMO and AMC events differ in colour and in shape. Events with no expected move are not drawn; they are counted under the
 * chart. Beside it, the summary the file gives: the share of events whose move beat the expected one against its benchmark,
 * the slope of the realised-on-implied regression with its interval, the joint Wald test with its role, its Holm p and the
 * verdict of gate G1 (since fix R1 a test that failed its size check stays primary: the page says it is liberal and that a
 * rejection by it would not be trusted), and the one-way p-value, or "withheld" with its G1 rate when its own check failed.
 * Every number is shown as given (`asGiven`), apart from shares and rates, which are shown as percents; the page
 * works out nothing. The pixel work is in `chartLayout.ts`. The file is checked with `loadImpliedRealised` first, and a
 * missing or invalid file shows an explicit error.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { percentTickLabel, scatterLayout, type ScatterLayout } from './chartLayout'
import { asGiven, pct } from './format'
import { IMPLIED_REALISED_URL, loadImpliedRealised, type ImpliedRealisedData, type ImpliedRegression, type ImpliedSummary } from './impliedRealised'
import { ProvisionalNotice } from './ProvisionalNotice'

type State = { status: 'loading' } | { status: 'ok'; data: ImpliedRealisedData } | { status: 'error'; error: string }

/** The mark class of a dot or legend entry: one per timing, so colour and shape both tell BMO from AMC. */
const markClass = (timing: 'BMO' | 'AMC' | null): string => (timing === 'BMO' ? 'mark-bmo' : timing === 'AMC' ? 'mark-amc' : 'mark-unknown')

function Scatter({ layout }: { layout: ScatterLayout }) {
  const { box, plot } = layout
  if (layout.dots.length === 0) return <p className="sub">No event has an expected move to draw.</p>
  const hasUnknown = layout.dots.some((d) => d.timing === null)
  return (
    <>
      <ul className="legend sub" aria-label="Legend">
        <li>
          <svg className="legend-mark" viewBox="-7 -7 14 14" width={14} height={14} aria-hidden="true">
            <circle className="mark-bmo" r={4} />
          </svg>{' '}
          BMO (reported before the open)
        </li>
        <li>
          <svg className="legend-mark" viewBox="-7 -7 14 14" width={14} height={14} aria-hidden="true">
            <path className="mark-amc" d="M0 -5.5 L5.5 0 L0 5.5 L-5.5 0Z" />
          </svg>{' '}
          AMC (reported after the close)
        </li>
        {hasUnknown && (
          <li>
            <svg className="legend-mark" viewBox="-7 -7 14 14" width={14} height={14} aria-hidden="true">
              <circle className="mark-unknown" r={4} />
            </svg>{' '}
            timing unknown
          </li>
        )}
      </ul>
      <svg
        className="path-chart scatter"
        viewBox={`0 0 ${box.width} ${box.height}`}
        role="img"
        aria-label={`Scatter of the realised absolute move against the expected absolute move, ${layout.dots.length} events, with the line where they are equal`}
      >
        <defs>
          <circle id="mark-bmo" r={4} />
          <path id="mark-amc" d="M0 -5.5 L5.5 0 L0 5.5 L-5.5 0Z" />
          <circle id="mark-unknown" r={4} />
        </defs>
        <g className="axes">
          {layout.ticks.map((t, i) => (
            <g key={t}>
              <line className="grid-line" x1={plot.left} x2={plot.right} y1={layout.tickY[i]} y2={layout.tickY[i]} />
              <line className="grid-line" x1={layout.tickX[i]} x2={layout.tickX[i]} y1={plot.top} y2={plot.bottom} />
              <text className="tick" x={plot.left - 6} y={layout.tickY[i]} textAnchor="end" dominantBaseline="middle">
                {percentTickLabel(t)}
              </text>
              <text className="tick" x={layout.tickX[i]} y={plot.bottom + 16} textAnchor="middle">
                {percentTickLabel(t)}
              </text>
            </g>
          ))}
          <text className="tick" x={layout.centre.x} y={box.height - 6} textAnchor="middle">
            expected |move| from the options, day -1
          </text>
          <text className="tick" x={12} y={layout.centre.y} textAnchor="middle" transform={`rotate(-90 12 ${layout.centre.y})`}>
            realised |move|, day 0
          </text>
        </g>
        <line className="diagonal" x1={layout.diagonal.x1} y1={layout.diagonal.y1} x2={layout.diagonal.x2} y2={layout.diagonal.y2} />
        {layout.dots.map((d) => (
          <use key={d.id} href={`#${markClass(d.timing)}`} className={`dot ${markClass(d.timing)}`} x={d.cx} y={d.cy} data-event={d.id}>
            <title>
              {d.label} ({d.timing ?? 'timing unknown'}): expected {pct(d.x)}, realised {pct(d.y)}
            </title>
          </use>
        ))}
      </svg>
    </>
  )
}

/** The one-way p-value as given, or "withheld" with its G1 rate when its size check failed (the file then gives no p). */
const oneWayP = (r: ImpliedRegression): string =>
  r.g1_pass_one_way === false && r.g1_rate_one_way !== null ? `withheld (G1 ${pct(r.g1_rate_one_way)})` : asGiven(r.wald_p_one_way)

/** The measures of the summary, one row each: [name, value, detail]. */
function summaryRows(s: ImpliedSummary): [string, ReactNode, string][] {
  const r = s.regression
  return [
    ['Events', s.n, `${s.n_with_implied_abs_move} with an expected move; ${s.n_evar_nonpositive} with a non-positive event variance`],
    [
      'Share with realised move above the expected move',
      pct(s.share_exceed),
      `SE ${pct(s.share_exceed_se)}; p = ${s.share_exceed_p} against the benchmark ${pct(s.share_exceed_benchmark)}`,
    ],
    ['Slope b of realised on implied variance', asGiven(r.b), `SE ${r.b_se}; interval [${r.b_ci[0]}, ${r.b_ci[1]}]`],
    ['Intercept a', asGiven(r.a), `SE ${r.a_se}`],
    [
      'Joint Wald test a = 0, b = 1',
      `F(${r.wald_df_num}, ${r.wald_df}) = ${r.wald_f}`,
      `p = ${r.wald_p}; Holm p ${asGiven(r.p_holm)}; one-way p ${oneWayP(r)}; n = ${r.n}; ${r.n_clusters_date} date clusters, ${r.n_clusters_firm} firm clusters`,
    ],
    ['Role of the test', r.role, r.role === 'primary' ? 'in the confirmatory family' : 'not in the confirmatory family'],
    [
      'Gate G1 for the test',
      <>
        <span className={`badge ${r.g1_pass ? '' : 'err-badge'}`}>{r.g1_pass ? 'pass' : 'fail'}</span>
        {pct(r.g1_rate)}
      </>,
      `rejection rate under the calibrated null; band upper edge ${pct(r.g1_bar)}`,
    ],
    ['Mean log ratio', asGiven(s.mean_log_ratio), 'of the realised to the expected |move|'],
    ['Median ratio', asGiven(s.median_ratio), 'of the realised to the expected |move|'],
  ]
}

function Summary({ summary }: { summary: ImpliedSummary }) {
  const r = summary.regression
  return (
    <>
      <p className="gate-note" role="note" aria-label="Gate G1 verdict">
        {r.g1_pass
          ? `The joint test passed gate G1: under the calibrated null it rejects ${pct(r.g1_rate)} of the time, within the band's upper edge (${pct(r.g1_bar)}).`
          : `The joint test failed gate G1's size check: under the calibrated null it rejects ${pct(r.g1_rate)} of the time, above the band's upper edge (${pct(r.g1_bar)}). It is liberal on this design, so a rejection by it would not be trusted.` +
            (r.role === 'primary'
              ? ` It stays in the declared Holm family as a primary test with its p-value (Holm p ${asGiven(r.p_holm)}).`
              : ' Its p-value is exploratory: read it as an indication, not as a test.')}
      </p>
      <div className="scroll-x">
        <table aria-label="Summary">
          <thead>
            <tr>
              <th>Measure</th>
              <th>Value</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {summaryRows(summary).map(([name, value, detail]) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td className="num">{value}</td>
                <td className="cell-note">{detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

export function ImpliedRealisedDisplay({ data }: { data: ImpliedRealisedData }) {
  const layout = scatterLayout(data.points)
  return (
    <>
      <ProvisionalNotice lookups={data.lookups} caveats={data.caveats} />
      <p className="sub">
        Do the moves options imply for earnings match the moves that are realised? Python computes every number and writes the file; this page only draws it. Sample:{' '}
        <strong>{data.provenance.sample_label}</strong>.
      </p>

      <h2>Summary</h2>
      <Summary summary={data.summary} />

      <h2>Expected against realised move</h2>
      <p className="sub">
        One dot per event. The dashed line is where the realised move equals the expected one; a dot above it moved more than the options implied.
      </p>
      <Scatter layout={layout} />
      <p className="sub" aria-label="Events not drawn">
        {layout.withoutImplied === 0
          ? `All ${data.points.length} events are drawn.`
          : `${layout.withoutImplied} of ${data.points.length} events have no expected move (the options give none) and are not drawn.`}
      </p>

      <details>
        <summary>Numbers behind the scatter ({data.points.length} events)</summary>
        <div className="scroll-x">
          <table aria-label="Events">
            <thead>
              <tr>
                <th>Event</th>
                <th>Day 0</th>
                <th>Timing</th>
                <th>Expected |move|</th>
                <th>Realised |move|</th>
                <th>Expected move status</th>
              </tr>
            </thead>
            <tbody>
              {data.points.map((p) => (
                <tr key={p.event_id}>
                  <td>{p.event_id}</td>
                  <td>{p.day0}</td>
                  <td>{p.timing_used ?? '—'}</td>
                  <td className="num">{asGiven(p.implied_abs_move_total)}</td>
                  <td className="num">{p.abs_realized}</td>
                  <td>{p.implied_move_status ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}

export function ImpliedRealisedPage({ url = IMPLIED_REALISED_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the page unmounts or the url changes first
    loadImpliedRealised(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', data: r.data } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  return (
    <section className="results implied">
      <h2>Implied vs realised</h2>
      {state.status === 'loading' && (
        <p className="sub" role="status">
          Loading implied and realised moves…
        </p>
      )}
      {state.status === 'error' && (
        <p className="sub" role="alert">
          <span className="badge err-badge">data error</span> The implied and realised moves could not be shown: {state.error}
        </p>
      )}
      {state.status === 'ok' && <ImpliedRealisedDisplay data={state.data} />}
    </section>
  )
}
