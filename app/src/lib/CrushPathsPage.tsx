/**
 * "Crush paths" page: draws `data/event_paths.json` as SVG. The first chart is the mean abnormal log
 * IV path with its pointwise 95% band, for the adjustment (market or mean) and subgroup (all, BMO,
 * AMC) the visitor picks. The second chart animates the per-event paths: they are revealed one event
 * day per frame, with Play / Pause and a slider. Under prefers-reduced-motion nothing plays by
 * itself and the finished picture is shown. All the frame logic and scaling is in `pathFrames.ts`;
 * this component wires a timer to it and draws what it returns. No statistic is worked out here.
 */
import { useEffect, useMemo, useState } from 'react'
import {
  eventsInSubgroup,
  EVENT_PATHS_URL,
  findSeries,
  loadEventPaths,
  seriesOptions,
  type EventPaths,
  type PathSeries,
  type PerEventPath,
  type SubgroupOption,
} from './eventPaths'
import { asGiven } from './format'
import { prefersReducedMotion } from './motion'
import {
  bandPath,
  CHART,
  extentWithZero,
  FRAME_MS,
  initialPlayback,
  linearTicks,
  padExtent,
  runsToPath,
  seekPlayback,
  stepPlayback,
  togglePlayback,
  visibleRuns,
  xPixels,
  xTickDays,
  yScale,
} from './pathFrames'
import { ProvisionalNotice } from './ProvisionalNotice'

type State = { status: 'loading' } | { status: 'ok'; paths: EventPaths } | { status: 'error'; error: string }

/** Gridlines and labels: horizontal ticks at `yTicks`, day labels under the plot, and a marker at day 0. */
function Axes({ days, xs, yTicks, toY, units }: { days: number[]; xs: number[]; yTicks: number[]; toY: (v: number) => number; units: string }) {
  const bottom = CHART.height - CHART.bottom
  return (
    <g className="axes">
      {yTicks.map((t) => (
        <g key={t}>
          <line className="grid-line" x1={CHART.left} x2={CHART.width - CHART.right} y1={toY(t)} y2={toY(t)} />
          <text className="tick" x={CHART.left - 6} y={toY(t)} textAnchor="end" dominantBaseline="middle">
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      {xTickDays(days).map((d) => {
        const x = xs[days.indexOf(d)]
        return (
          <text key={d} className="tick" x={x} y={bottom + 18} textAnchor="middle">
            {d}
          </text>
        )
      })}
      {days.includes(0) && <line className="day0-line" x1={xs[days.indexOf(0)]} x2={xs[days.indexOf(0)]} y1={CHART.top} y2={bottom} />}
      <text className="tick" x={CHART.left + (CHART.width - CHART.left - CHART.right) / 2} y={CHART.height - 4} textAnchor="middle">
        event day
      </text>
      <text className="tick" x={CHART.left} y={CHART.top - 9}>
        {units}
      </text>
    </g>
  )
}

/** Mean path with its band for one series. */
function MeanChart({ days, series, caption }: { days: number[]; series: PathSeries; caption: string }) {
  const [lo, hi] = padExtent(extentWithZero([series.mean, series.ci_lo, series.ci_hi]), 0.08)
  const xs = xPixels(days)
  const toY = yScale([lo, hi])
  return (
    <svg className="path-chart" viewBox={`0 0 ${CHART.width} ${CHART.height}`} role="img" aria-label={caption}>
      <Axes days={days} xs={xs} yTicks={linearTicks(lo, hi, 5)} toY={toY} units={series.units} />
      <path className="path-band" data-testid="mean-band" d={bandPath(xs, series.ci_lo, series.ci_hi, toY)} />
      <path className="path-mean" data-testid="mean-line" d={runsToPath(visibleRuns(series.mean, days.length - 1, xs, toY))} />
    </svg>
  )
}

/** The numbers behind the mean chart, for readers who do not use the chart. */
function SeriesTable({ days, series }: { days: number[]; series: PathSeries }) {
  return (
    <details>
      <summary>Numbers behind the mean path</summary>
      <div className="scroll-x">
        <table aria-label="Mean path numbers">
          <thead>
            <tr>
              <th>Event day</th>
              <th>n</th>
              <th>Mean</th>
              <th>Band low</th>
              <th>Band high</th>
            </tr>
          </thead>
          <tbody>
            {days.map((d, i) => (
              <tr key={d}>
                <td>{d}</td>
                <td className="num">{asGiven(series.n[i])}</td>
                <td className="num">{asGiven(series.mean[i])}</td>
                <td className="num">{asGiven(series.ci_lo[i])}</td>
                <td className="num">{asGiven(series.ci_hi[i])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

const eventLabel = (e: PerEventPath): string => `${e.ticker} ${e.day0} (${e.timing_used ?? 'timing unknown'})`

/** The animated per-event chart. `key` it by the subgroup so a new subgroup starts a new animation. */
function AnimatedEvents({ days, events, mean }: { days: number[]; events: PerEventPath[]; mean: PathSeries | undefined }) {
  const lastFrame = days.length - 1
  const [playback, setPlayback] = useState(() => initialPlayback(prefersReducedMotion(), lastFrame))

  useEffect(() => {
    if (!playback.playing) return
    const timer = setTimeout(() => setPlayback((p) => stepPlayback(p, lastFrame)), FRAME_MS)
    return () => clearTimeout(timer)
  }, [playback, lastFrame])

  const xs = useMemo(() => xPixels(days), [days])
  const extent = useMemo(() => extentWithZero([...events.map((e) => e.values), ...(mean ? [mean.mean] : [])]), [events, mean])
  const [lo, hi] = padExtent(extent, 0.05)
  const toY = yScale([lo, hi])
  const { frame } = playback

  return (
    <div>
      <div className="controls">
        <button type="button" className="primary" onClick={() => setPlayback((p) => togglePlayback(p, lastFrame))}>
          {playback.playing ? 'Pause' : 'Play'}
        </button>
        <label htmlFor="path-frame">Event day shown</label>
        <input
          id="path-frame"
          type="range"
          min={0}
          max={lastFrame}
          step={1}
          value={frame}
          aria-valuetext={`event days ${days[0]} to ${days[frame]}`}
          onChange={(e) => setPlayback(seekPlayback(Number(e.target.value), lastFrame))}
        />
        <span className="sub" style={{ margin: 0 }}>
          Showing event days {days[0]} to {days[frame]}
        </span>
      </div>
      <svg className="path-chart" viewBox={`0 0 ${CHART.width} ${CHART.height}`} role="img" aria-label={`Per-event abnormal log IV paths, ${events.length} events, event days ${days[0]} to ${days[frame]}`}>
        <Axes days={days} xs={xs} yTicks={linearTicks(lo, hi, 5)} toY={toY} units="abnormal log IV (mean-adjusted)" />
        {events.map((e) => (
          <path key={e.event_id} className="path-event" data-event={e.event_id} d={runsToPath(visibleRuns(e.values, frame, xs, toY))}>
            <title>{eventLabel(e)}</title>
          </path>
        ))}
        {mean && <path className="path-mean" data-testid="animated-mean" d={runsToPath(visibleRuns(mean.mean, frame, xs, toY))} />}
      </svg>
    </div>
  )
}

const subgroupId = (g: SubgroupOption): string => `${g.key}=${g.value}`

export function CrushPathsDisplay({ paths }: { paths: EventPaths }) {
  const options = useMemo(() => seriesOptions(paths.series), [paths.series])
  const [chosenAdjustment, setAdjustment] = useState(options.adjustments[0])
  const [groupId, setGroupId] = useState(subgroupId(options.subgroups[0]))
  // The choice can name something a newly loaded file lacks: fall back to the file's first.
  const adjustment = options.adjustments.includes(chosenAdjustment) ? chosenAdjustment : options.adjustments[0]
  const group = options.subgroups.find((g) => subgroupId(g) === groupId) ?? options.subgroups[0]

  const series = findSeries(paths.series, adjustment, group)
  const events = eventsInSubgroup(paths.per_event, group)
  const meanOfEvents = findSeries(paths.series, 'mean', group)
  const caption = `Mean abnormal log IV path with its pointwise 95% band, ${adjustment}-adjusted, subgroup ${group.label}`

  return (
    <>
      <ProvisionalNotice lookups={paths.lookups} caveats={paths.caveats} />
      <p className="sub">
        How implied volatility moves around the announcement: the mean abnormal path with its band, and every event&apos;s own path. Python computes the
        numbers and writes the file; this page only draws it. Sample: <strong>{paths.provenance.sample_label}</strong>.
      </p>

      <div className="controls">
        <label htmlFor="path-adjustment">Adjustment</label>
        <select id="path-adjustment" value={adjustment} onChange={(e) => setAdjustment(e.target.value as typeof chosenAdjustment)}>
          {options.adjustments.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <label htmlFor="path-subgroup">Subgroup</label>
        <select id="path-subgroup" value={subgroupId(group)} onChange={(e) => setGroupId(e.target.value)}>
          {options.subgroups.map((g) => (
            <option key={subgroupId(g)} value={subgroupId(g)}>
              {g.label}
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Mean path with 95% band</h2>
        {series ? (
          <>
            <p className="sub">
              {series.measure} · {series.units} · {adjustment}-adjusted · subgroup {group.label}
            </p>
            <MeanChart days={paths.rel_days} series={series} caption={caption} />
            <SeriesTable days={paths.rel_days} series={series} />
          </>
        ) : (
          <p className="sub">The file has no series for {adjustment}-adjusted values in subgroup {group.label}.</p>
        )}
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Event paths, day by day</h2>
        <p className="sub">One line per event: its abnormal log IV, mean-adjusted (the file has no market-adjusted path per event). The thick line is the mean-adjusted mean path of the subgroup.</p>
        {events === null || events.length === 0 ? (
          <p className="sub">The file has no per-event paths for subgroup {group.label}.</p>
        ) : (
          <AnimatedEvents key={subgroupId(group)} days={paths.rel_days} events={events} mean={meanOfEvents} />
        )}
      </div>
    </>
  )
}

export function CrushPathsPage({ url = EVENT_PATHS_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the page unmounts or the url changes first
    loadEventPaths(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', paths: r.data } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  return (
    <section className="crush-paths">
      <h2>Crush paths</h2>
      {state.status === 'loading' && (
        <p className="sub" role="status">
          Loading event paths…
        </p>
      )}
      {state.status === 'error' && (
        <p className="sub" role="alert">
          <span className="badge err-badge">data error</span> The event paths could not be shown: {state.error}
        </p>
      )}
      {state.status === 'ok' && <CrushPathsDisplay paths={state.paths} />}
    </section>
  )
}
