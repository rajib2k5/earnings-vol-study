/**
 * "IV measures" page: draws `data/iv_measures.json` (the distribution of the implied move at day -1
 * and of the 30-day IV crush) exactly as the Python exporter wrote it. Every number is shown as
 * given: the counts, the quantiles, the bin edges. The only thing this page works out is the height
 * of each histogram bar (a bin's count against the largest count of the same histogram), which is
 * layout, not a result. The file is checked with `loadIvMeasures` first, and a missing or invalid
 * file shows an explicit error instead of a chart.
 */
import { useEffect, useState } from 'react'
import { IV_MEASURES_URL, loadIvMeasures, QUANTILE_NAMES, type IvMeasures, type Quantiles } from './ivMeasures'

type State = { status: 'loading' } | { status: 'ok'; iv: IvMeasures } | { status: 'error'; error: string }

const IMPLIED_MOVE_TITLE = 'Implied move √E on day −1, events with E > 0'
const CRUSH_TITLE = '30-day IV crush, ln IV(day 0) − ln IV(day −1)'

/** CSS height of a bar: its count against the largest count of the histogram. A largest count of 0 gives empty bars. */
const barHeight = (count: number, maxCount: number): string => (maxCount > 0 ? `${(count / maxCount) * 100}%` : '0%')

/** A number as the file has it, or "—" for null. */
const orDash = (x: number | null): string => (x === null ? '—' : String(x))

const eventsLabel = (n: number): string => `${n} ${n === 1 ? 'event' : 'events'}`

function Histogram({ title, edges, counts }: { title: string; edges: number[]; counts: number[] }) {
  if (counts.length === 0) {
    return <p className="sub">No histogram: the file has no bins.</p>
  }
  const max = counts.reduce((a, b) => Math.max(a, b), 0)
  return (
    <div>
      <div className="hist" role="group" aria-label={`${title} histogram`}>
        {counts.map((c, i) => (
          <div key={i} className="hist-bar" role="img" aria-label={`${edges[i]} to ${edges[i + 1]}: ${eventsLabel(c)}`} style={{ height: barHeight(c, max) }} />
        ))}
      </div>
      <div className="hist-axis">
        <span>{edges[0]}</span>
        <span>{edges[edges.length - 1]}</span>
      </div>
    </div>
  )
}

function QuantileTable({ label, quantiles }: { label: string; quantiles: Quantiles | null }) {
  if (quantiles === null) return <p className="sub">No quantiles: the file has none for the {label}.</p>
  return (
    <table aria-label={`${label} quantiles`}>
      <thead>
        <tr>
          <th>Quantile</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        {QUANTILE_NAMES.map((name) => (
          <tr key={name}>
            <td>{name}</td>
            <td className="num">{quantiles[name]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Label / value rows of the numbers that sit beside a histogram. */
function FactsTable({ label, rows }: { label: string; rows: [string, string][] }) {
  return (
    <table aria-label={`${label} numbers`}>
      <tbody>
        {rows.map(([name, value]) => (
          <tr key={name}>
            <td>{name}</td>
            <td className="num">{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function IvMeasuresDisplay({ iv }: { iv: IvMeasures }) {
  const move = iv.implied_move
  const crush = iv.crush
  return (
    <>
      <p className="sub">
        How big the market expects the earnings move to be, and how far implied volatility falls after it. Python computes the numbers and writes
        the file; this page only draws it. Sample: <strong>{iv.sample.label}</strong>, <span className="num">{iv.sample.n_events}</span> events.
      </p>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>{IMPLIED_MOVE_TITLE}</h2>
        <p className="sub">Units: {move.units}</p>
        <div className="iv-layout">
          <Histogram title="Implied move" edges={move.bin_edges} counts={move.counts} />
          <div>
            <FactsTable
              label="Implied move"
              rows={[
                ['Events in the histogram (n)', String(move.n)],
                ['Events with E worked out (n_identified)', String(move.n_identified)],
                ['E ≤ 0, no implied move', String(move.n_nonpositive)],
                ['√(mean E), all events, E signed', orDash(move.sqrt_mean_evar)],
              ]}
            />
            <QuantileTable label="Implied move" quantiles={move.quantiles} />
          </div>
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>{CRUSH_TITLE}</h2>
        <p className="sub">Units: {crush.units}</p>
        <div className="iv-layout">
          <Histogram title="IV crush" edges={crush.bin_edges} counts={crush.counts} />
          <div>
            <FactsTable
              label="IV crush"
              rows={[
                ['Events in the histogram (n)', String(crush.n)],
                ['Mean', orDash(crush.mean)],
              ]}
            />
            <QuantileTable label="IV crush" quantiles={crush.quantiles} />
          </div>
        </div>
      </div>

      <h2>Caveats</h2>
      <ul aria-label="Caveats" className="sub">
        {iv.caveats.map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
    </>
  )
}

export function IvMeasuresPage({ url = IV_MEASURES_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the page unmounts or the url changes first
    loadIvMeasures(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', iv: r.data } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  return (
    <section className="iv-measures">
      <h2>IV measures</h2>
      {state.status === 'loading' && (
        <p className="sub" role="status">
          Loading IV measures…
        </p>
      )}
      {state.status === 'error' && (
        <p className="sub" role="alert">
          <span className="badge err-badge">data error</span> The IV measures could not be shown: {state.error}
        </p>
      )}
      {state.status === 'ok' && <IvMeasuresDisplay iv={state.iv} />}
    </section>
  )
}
