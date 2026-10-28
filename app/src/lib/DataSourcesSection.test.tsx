import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { DataSourcesSection, DataSourcesTable } from './DataSourcesSection'
import { META_DATA_FIXTURE, META_FIXTURE } from '../test/metaFixture'
import type { MetaData } from './meta'

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

describe('DataSourcesSection', () => {
  it('shows a loading line first, then one row per source from the file, plus the attribution', async () => {
    render(<DataSourcesSection fetchImpl={serving(META_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading data sources')
    const table = await screen.findByRole('table')
    expect(screen.queryByRole('status')).toBeNull()
    expect(within(table).getAllByRole('row')).toHaveLength(META_DATA_FIXTURE.data_sources.length + 1) // + header row
    for (const s of META_DATA_FIXTURE.data_sources) {
      expect(within(table).getByRole('link', { name: s.name })).toHaveAttribute('href', s.url)
      expect(within(table).getByRole('row', { name: new RegExp(s.name) })).toHaveTextContent(s.uses)
    }
    expect(screen.getByText(META_DATA_FIXTURE.data_licence.attribution)).toBeInTheDocument()
  })

  it('links the licence text only for the sources the licence applies_to, and says "see source" unlinked otherwise', async () => {
    render(<DataSourcesSection fetchImpl={serving(META_FIXTURE)} />)
    const table = await screen.findByRole('table')
    const open = within(table).getByRole('row', { name: /Fixture open source/ })
    expect(within(open).getByRole('link', { name: 'FIX-OPEN 1.0' })).toHaveAttribute('href', 'https://example.com/licence')
    expect(open).toHaveTextContent('derived rows only')
    const vendor = within(table).getByRole('row', { name: /Fixture vendor/ })
    expect(vendor).toHaveTextContent('see source')
    expect(within(vendor).queryByRole('link', { name: 'see source' })).toBeNull()
    expect(vendor).toHaveTextContent('never')
    expect(within(table).getAllByRole('link', { name: 'FIX-OPEN 1.0' })).toHaveLength(1)
  })

  it('requests the relative data/meta.json by default, and the given url when there is one', async () => {
    const f = serving(META_FIXTURE)
    const { unmount } = render(<DataSourcesSection fetchImpl={f} />)
    await screen.findByRole('table')
    expect(f).toHaveBeenCalledWith('data/meta.json', { cache: 'no-cache' })
    unmount()
    const g = serving(META_FIXTURE)
    render(<DataSourcesSection url="x/meta.json" fetchImpl={g} />)
    await screen.findByRole('table')
    expect(g).toHaveBeenCalledWith('x/meta.json', { cache: 'no-cache' })
  })

  it('shows an error, and no table, when the file is missing (HTTP 404)', async () => {
    render(<DataSourcesSection fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('shows an error when the envelope is invalid (wrong schema version)', async () => {
    render(<DataSourcesSection fetchImpl={serving({ ...META_FIXTURE, schema_version: '9.0.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "9.0.0"')
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('shows an error, naming the file and the rule, when data has the wrong shape', async () => {
    const broken = { ...META_FIXTURE, data: { ...META_DATA_FIXTURE, data_sources: [] } }
    render(<DataSourcesSection url="data/meta.json" fetchImpl={serving(broken)} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data/meta.json: data_sources must be a non-empty array')
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('shows an error for a file from the old exporter that has no data_licence', async () => {
    const old: Record<string, unknown> = { ...META_DATA_FIXTURE }
    delete old.data_licence
    render(<DataSourcesSection fetchImpl={serving({ ...META_FIXTURE, data: old })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('missing key(s): data_licence')
  })

  it('ignores a late answer for an old url after the url has changed', async () => {
    // React no longer warns about a state update after unmount, so the visible rule is this one:
    // the first request answers last, with an error, and must not replace the newer table.
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const newFetch = serving(META_FIXTURE)
    const { rerender } = render(<DataSourcesSection url="old/meta.json" fetchImpl={oldFetch} />)
    rerender(<DataSourcesSection url="new/meta.json" fetchImpl={newFetch} />)
    await screen.findByRole('table')
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('DataSourcesTable', () => {
  it('draws exactly the rows it is given, in order', () => {
    const meta: MetaData = {
      ...META_DATA_FIXTURE,
      data_sources: [...META_DATA_FIXTURE.data_sources].reverse(),
    }
    render(<DataSourcesTable meta={meta} />)
    const rows = within(screen.getByRole('table')).getAllByRole('row')
    expect(rows[1]).toHaveTextContent('Fixture vendor')
    expect(rows[2]).toHaveTextContent('Fixture open source')
  })
})
