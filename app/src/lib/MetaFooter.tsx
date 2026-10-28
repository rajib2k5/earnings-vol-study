/**
 * Footer status line: loads data/meta.json, validates the envelope and shows which schema,
 * milestone and Python commit produced the data. Missing or invalid files show an explicit error.
 */
import { useEffect, useState } from 'react'
import { formatMilestone, loadMeta, META_URL, summarizeMeta, type MetaSummary } from './meta'

type State = { status: 'loading' } | { status: 'ok'; meta: MetaSummary } | { status: 'error'; error: string }

export function MetaFooter({ url = META_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the footer unmounts first
    loadMeta(url, fetchImpl).then((r) => {
      if (!cancelled) setState(r.ok ? { status: 'ok', meta: summarizeMeta(r.envelope) } : { status: 'error', error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  // The footer element keeps its own landmark role; the live-region role goes on an inner element.
  if (state.status === 'loading') {
    return (
      <footer>
        <span role="status">Checking data contract…</span>
      </footer>
    )
  }
  if (state.status === 'error') {
    return (
      <footer>
        <span role="alert">
          <span className="badge err-badge">data error</span> {state.error}
        </span>
      </footer>
    )
  }
  const m = state.meta
  return (
    <footer>
      <span role="status">
        data contract {m.schemaVersion} · milestone {formatMilestone(m.milestone)} · source commit {m.sourceCommit} · generated {m.generatedAt}
      </span>
    </footer>
  )
}
