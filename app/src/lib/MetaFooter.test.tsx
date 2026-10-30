import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MetaFooter } from './MetaFooter'

// Hand-built fixture in the shape the Python exporter writes.
const good = {
  schema_version: '0.5.0',
  kind: 'meta',
  generated_at: '2026-10-27T12:00:00Z',
  source_commit: 'abc1234',
  data: { milestone: 0 },
}

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch

describe('MetaFooter', () => {
  it('shows a loading line first, then the schema, milestone, commit and timestamp', async () => {
    render(<MetaFooter fetchImpl={respond({ ok: true, status: 200, json: async () => good })} />)
    expect(screen.getByRole('status')).toHaveTextContent('Checking data contract')
    const footer = await screen.findByText(/source commit abc1234/)
    expect(footer).toHaveTextContent('data contract 0.5.0 · milestone M0 · source commit abc1234 · generated 2026-10-27T12:00:00Z')
  })
  it('shows "milestone unknown" when the file has no usable milestone', async () => {
    const f = respond({ ok: true, status: 200, json: async () => ({ ...good, data: { milestone: 'M0' } }) })
    render(<MetaFooter fetchImpl={f} />)
    expect(await screen.findByText(/milestone unknown/)).toBeInTheDocument()
  })
  it('requests the relative data/meta.json by default', async () => {
    const f = respond({ ok: true, status: 200, json: async () => good })
    render(<MetaFooter fetchImpl={f} />)
    await screen.findByText(/source commit/)
    expect(f).toHaveBeenCalledWith('data/meta.json', { cache: 'no-cache' })
  })
  it('shows a clear alert when the file is missing (HTTP 404)', async () => {
    render(<MetaFooter fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('HTTP 404')
  })
  it('shows a clear alert when the contract is violated (wrong schema version)', async () => {
    render(<MetaFooter fetchImpl={respond({ ok: true, status: 200, json: async () => ({ ...good, schema_version: '9.0.0' }) })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "9.0.0"')
  })
  it('ignores a late answer for an old url after the url has changed', async () => {
    // React no longer warns about a state update after unmount, so the visible rule is this one:
    // the first request answers last, with an error, and must not replace the newer status line.
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const newFetch = respond({ ok: true, status: 200, json: async () => good })
    const { rerender } = render(<MetaFooter url="old/meta.json" fetchImpl={oldFetch} />)
    rerender(<MetaFooter url="new/meta.json" fetchImpl={newFetch} />)
    await screen.findByText(/source commit abc1234/)
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('status')).toHaveTextContent('source commit abc1234')
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
