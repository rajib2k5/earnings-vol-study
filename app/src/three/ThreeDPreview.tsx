/** "3D preview" page: lazy-loads the r3f surface so first paint (and tests) need no WebGL. */
import { lazy, Suspense } from 'react'
import { ErrorBoundary } from '../lib/ErrorBoundary'

const EventTerrain3D = lazy(() => import('./EventTerrain3D'))

export function ThreeDPreview() {
  return (
    <section>
      <h2>3D preview</h2>
      <p className="sub">
        Placeholder for the event-time IV surface: one row per company, one column per day around the announcement. Real surfaces replace this once
        Python exports the event panel.
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
            <EventTerrain3D />
          </Suspense>
        </ErrorBoundary>
      </div>
    </section>
  )
}
