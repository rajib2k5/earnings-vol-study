/**
 * About-page table of data sources and licences. Every cell comes from `data/meta.json`, which the
 * Python exporter writes (`tools/export_app_data.py` is the only place that lists the sources, the
 * licence and the attribution text); this app keeps no copy. The file is checked with
 * `parseMetaData` first, and a missing or invalid file shows an explicit error instead of a table.
 */
import { useEffect, useState } from 'react'
import { loadMeta, META_URL, parseMetaData, type MetaData } from './meta'

type State = { status: 'loading' } | { status: 'ok'; meta: MetaData } | { status: 'error'; error: string }

export function DataSourcesTable({ meta }: { meta: MetaData }) {
  const { data_sources, data_licence } = meta
  return (
    <div className="card scroll-x">
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Used for</th>
            <th>Licence</th>
            <th>Committed to repo</th>
          </tr>
        </thead>
        <tbody>
          {data_sources.map((s) => (
            <tr key={s.name}>
              <td>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.name}
                </a>
              </td>
              <td className="num">{s.uses}</td>
              <td>
                {data_licence.applies_to.includes(s.name) ? (
                  <a href={data_licence.url} target="_blank" rel="noreferrer">
                    {s.licence}
                  </a>
                ) : (
                  s.licence
                )}
              </td>
              <td>{s.committed ? 'derived rows only' : 'never'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="sub" style={{ marginTop: '.8rem', marginBottom: 0 }}>
        {data_licence.attribution}
      </p>
    </div>
  )
}

export function DataSourcesSection({ url = META_URL, fetchImpl }: { url?: string; fetchImpl?: typeof fetch }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false // ignore the answer if the section unmounts first
    loadMeta(url, fetchImpl).then((r) => {
      if (cancelled) return
      if (!r.ok) return setState({ status: 'error', error: r.error })
      const parsed = parseMetaData(r.envelope.data)
      setState(parsed.ok ? { status: 'ok', meta: parsed.data } : { status: 'error', error: `${url}: ${parsed.error}` })
    })
    return () => {
      cancelled = true
    }
  }, [url, fetchImpl])

  if (state.status === 'loading') {
    return (
      <p className="sub" role="status">
        Loading data sources…
      </p>
    )
  }
  if (state.status === 'error') {
    return (
      <p className="sub" role="alert">
        <span className="badge err-badge">data error</span> Data sources and licences could not be shown: {state.error}
      </p>
    )
  }
  return <DataSourcesTable meta={state.meta} />
}
