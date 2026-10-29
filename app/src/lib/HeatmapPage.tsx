/**
 * "Heatmap" page: draws `data/heatmap.json` as grids of coloured cells (company by event day, company
 * by season). Each cell is coloured on a diverging scale that is symmetric around 0 and spans the
 * grid's own largest absolute value (`heatColour`); a cell without a value is drawn empty, never as 0.
 * Every cell says its row, column, value and n in its title and aria-label. The numbers are the
 * file's; the page works out no statistic.
 */
import { useEffect, useState } from 'react'
import { HEAT_LEGEND_GRADIENT, heatColour, legendLabels, maxAbs } from './heatColour'
import { cellText, HEATMAP_URL, loadHeatmap, type HeatGrid, type HeatmapData } from './heatmap'
import { ProvisionalNotice } from './ProvisionalNotice'

type State = { status: 'loading' } | { status: 'ok'; heatmap: HeatmapData } | { status: 'error'; error: string }

function HeatGridView({ grid }: { grid: HeatGrid }) {
  const max = maxAbs(grid.values)
  const [lowLabel, highLabel] = legendLabels(max)
  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>{grid.title}</h2>
      <p className="sub">
        {grid.measure} · {grid.units}. Colour: blue below 0, red above 0, strongest at the grid&apos;s largest absolute value. A dashed empty cell has no data.
      </p>
      <div className="heat-legend" aria-label={`${grid.title} colour scale`} role="img">
        <span className="num">{lowLabel}</span>
        <span className="heat-legend-bar" style={{ backgroundImage: HEAT_LEGEND_GRADIENT }} />
        <span className="num">{highLabel}</span>
      </div>
      <div className="scroll-x">
        <table className="heat" aria-label={grid.title}>
          <thead>
            <tr>
              <th scope="col" />
              {grid.col_labels.map((c, j) => (
                <th key={j} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.row_labels.map((label, i) => (
              <tr key={grid.row_keys[i]}>
                <th scope="row">{label}</th>
                {grid.col_labels.map((_, j) => {
                  const colour = heatColour(grid.values[i][j], max)
                  const text = cellText(grid, i, j)
                  return <td key={j} className={colour === null ? 'heat-cell heat-empty' : 'heat-cell'} style={colour === null ? undefined : { backgroundColor: colour }} title={text} aria-label={text} />
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function HeatmapDisplay({ heatmap }: { heatmap: HeatmapData }) {
  return (
    <>
      <ProvisionalNotice lookups={heatmap.lookups} caveats={heatmap.caveats} />
      <p className="sub">
        Where in the sample implied volatility moves, company by company. Python computes the numbers and writes the file; this page only draws it. Sample:{' '}
        <strong>{heatmap.provenance.sample_label}</strong>.
      </p>
      {heatmap.grids.map((g) => (
        <HeatGridView key={g.id} grid={g} />
      ))}
    </>
  )
}

export function HeatmapPage({ url = HEATMAP_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the page unmounts or the url changes first
    loadHeatmap(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', heatmap: r.data } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  return (
    <section className="heatmap">
      <h2>Heatmap</h2>
      {state.status === 'loading' && (
        <p className="sub" role="status">
          Loading heatmap…
        </p>
      )}
      {state.status === 'error' && (
        <p className="sub" role="alert">
          <span className="badge err-badge">data error</span> The heatmap could not be shown: {state.error}
        </p>
      )}
      {state.status === 'ok' && <HeatmapDisplay heatmap={state.heatmap} />}
    </section>
  )
}
