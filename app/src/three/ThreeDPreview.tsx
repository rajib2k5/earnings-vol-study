/**
 * "3D view" page: loads and validates `data/terrain.json` (in `src/lib`, so first paint needs no
 * WebGL), then lazy-loads the r3f surface and hands it the grid. The surface is the file's mean
 * abnormal log IV by company and event day; a cell with no data is a hole.
 */
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { ErrorBoundary } from '../lib/ErrorBoundary'
import { ProvisionalNotice } from '../lib/ProvisionalNotice'
import { loadTerrainData, TERRAIN_URL, terrainCaption, terrainGrid, type TerrainData } from '../lib/terrainData'

const EventTerrain3D = lazy(() => import('./EventTerrain3D'))

type State = { status: 'loading' } | { status: 'ok'; terrain: TerrainData } | { status: 'error'; error: string }

function TerrainView({ terrain }: { terrain: TerrainData }) {
  const grid = useMemo(() => terrainGrid(terrain), [terrain])
  return (
    <>
      <ProvisionalNotice lookups={terrain.lookups} caveats={terrain.caveats} />
      <p className="sub">
        Each company&apos;s mean abnormal log IV (mean-adjusted) on each event day: a description of the shape the study is looking at, not a test.
        Python computes the numbers and writes the file; this view only draws it. Sample: <strong>{terrain.provenance.sample_label}</strong>.
      </p>
      <div className="card">
        <ErrorBoundary
          fallback={(e) => (
            <p role="alert" className="sub">
              The 3D view could not start (it needs WebGL): {e.message}
            </p>
          )}
        >
          <Suspense fallback={<p className="sub">Loading 3D view…</p>}>
            <EventTerrain3D grid={grid} caption={terrainCaption(terrain)} />
          </Suspense>
        </ErrorBoundary>
      </div>
    </>
  )
}

export function ThreeDPreview({ url = TERRAIN_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the page unmounts or the url changes first
    loadTerrainData(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', terrain: r.data } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  return (
    <section>
      <h2>3D view</h2>
      {state.status === 'loading' && (
        <p className="sub" role="status">
          Loading terrain data…
        </p>
      )}
      {state.status === 'error' && (
        <p className="sub" role="alert">
          <span className="badge err-badge">data error</span> The 3D view could not be shown: {state.error}
        </p>
      )}
      {state.status === 'ok' && <TerrainView terrain={state.terrain} />}
    </section>
  )
}
