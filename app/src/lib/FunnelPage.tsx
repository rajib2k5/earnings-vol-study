/**
 * "Sample" page: draws `data/sample_funnel.json` (how many earnings events survive each filtering
 * step) exactly as the Python exporter wrote it. Every number is shown as given. The only thing this
 * page works out is the length of each bar (a step's `n_events` against the first step's), which is
 * layout, not a result. The file is checked with `loadSampleFunnel` first, and a missing or invalid
 * file shows an explicit error instead of a chart.
 */
import { useEffect, useState } from 'react'
import { loadSampleFunnel, SAMPLE_FUNNEL_URL, TIMING_STATUSES, type SampleFunnel } from './funnel'

type State = { status: 'loading' } | { status: 'ok'; funnel: SampleFunnel } | { status: 'error'; error: string }

/** CSS width of a bar: its step's events against the first step's. A first step of 0 gives an empty bar. */
const barWidth = (nEvents: number, firstNEvents: number): string => (firstNEvents > 0 ? `${(nEvents / firstNEvents) * 100}%` : '0%')

/** The status strings start with the machine word "not_computed:"; the page says it in plain words. */
const notComputed = (status: string): string => `not computed yet: ${status.replace(/^not_computed:\s*/, '')}`

export function FunnelDisplay({ funnel }: { funnel: SampleFunnel }) {
  const first = funnel.steps[0].n_events // steps is validated as non-empty
  return (
    <>
      <p className="sub">
        How many earnings events are left after each filtering step. Python counts them and writes the file; this page only draws it.
      </p>

      <div className="card scroll-x">
        <table aria-label="Funnel steps">
          <thead>
            <tr>
              <th>Step</th>
              <th>Events</th>
              <th>Removed</th>
              <th>Reason</th>
              <th>Events, relative to the first step</th>
            </tr>
          </thead>
          <tbody>
            {funnel.steps.map((s, i) => (
              <tr key={`${s.step}-${i}`}>
                <td>{s.label}</td>
                <td className="num">{s.n_events}</td>
                <td className="num">{s.n_removed}</td>
                <td className="num">{s.reason ?? '—'}</td>
                <td>
                  <div className="funnel-track">
                    <div className="funnel-bar" role="img" aria-label={`${s.n_events} of ${first} events`} style={{ width: barWidth(s.n_events, first) }} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid">
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Events by sample</h2>
          <table aria-label="Events by sample">
            <thead>
              <tr>
                <th>Sample</th>
                <th>Events</th>
              </tr>
            </thead>
            <tbody>
              {funnel.by_sample.map((s, i) => (
                <tr key={`${s.sample}-${i}`}>
                  <td>{s.sample}</td>
                  <td className="num">{s.n_events}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Timing status</h2>
          <table aria-label="Timing status counts">
            <thead>
              <tr>
                <th>Status</th>
                <th>Events</th>
              </tr>
            </thead>
            <tbody>
              {TIMING_STATUSES.map((status) => (
                <tr key={status}>
                  <td>{status}</td>
                  <td className="num">{funnel.timing_status_counts[status]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <h2>Timing lookups</h2>
      <p className="sub">
        <span className="num">{funnel.lookups.n_done}</span> lookups done <span className="badge">{funnel.lookups.complete ? 'complete' : 'provisional'}</span>
      </p>

      <h2>Not computed yet</h2>
      <ul aria-label="Not computed yet" className="sub">
        <li>
          <strong>By move tercile</strong> — <span>{notComputed(funnel.by_move_tercile_status)}</span>
        </li>
        <li>
          <strong>Non-positive event variance</strong> — <span>{notComputed(funnel.evar_nonpositive_status)}</span>
        </li>
      </ul>

      <h2>Caveats</h2>
      <ul aria-label="Caveats" className="sub">
        {funnel.caveats.map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
    </>
  )
}

export function FunnelPage({ url = SAMPLE_FUNNEL_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the page unmounts or the url changes first
    loadSampleFunnel(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', funnel: r.data } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  return (
    <section className="funnel">
      <h2>Sample funnel</h2>
      {state.status === 'loading' && (
        <p className="sub" role="status">
          Loading sample funnel…
        </p>
      )}
      {state.status === 'error' && (
        <p className="sub" role="alert">
          <span className="badge err-badge">data error</span> The sample funnel could not be shown: {state.error}
        </p>
      )}
      {state.status === 'ok' && <FunnelDisplay funnel={state.funnel} />}
    </section>
  )
}
