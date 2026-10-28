// M0 delta review, claim 8f: does the About page draw whatever app/public/data/meta.json says?
// NOT part of the app's suite. meta_single_source.sh copies this file into a scratch COPY of app/
// as src/realMetaRender.probe.test.tsx and runs it there; it never goes into the real app/.
// It serves the real public/data/meta.json (read with the same raw glob publicData.test.ts uses)
// to a stubbed global fetch, renders the production <App />, and prints the licence cells.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import App from './App'

vi.mock('@react-three/fiber', () => ({ Canvas: () => <div data-testid="r3f-canvas" /> }))
vi.mock('@react-three/drei', () => ({ OrbitControls: () => null }))

const files = import.meta.glob('../public/data/meta.json', { eager: true, query: '?raw', import: 'default' }) as Record<string, string>
const body = JSON.parse(Object.values(files)[0])

beforeEach(() => {
  window.location.hash = ''
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => (url === 'data/meta.json' ? ({ ok: true, status: 200, json: async () => body } as Response) : ({ ok: false, status: 404 } as Response))),
  )
})
afterEach(() => vi.unstubAllGlobals())

describe('probe: About page renders public/data/meta.json', () => {
  it('shows each source licence exactly as the file says', async () => {
    render(<App />)
    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row').slice(1)
    const cells = rows.map((r) => within(r).getAllByRole('cell')[2].textContent)
    console.log('PROBE licence cells:', JSON.stringify(cells))
    console.log('PROBE attribution shown:', screen.queryByText(body.data.data_licence.attribution) !== null)
    expect(cells).toEqual(body.data.data_sources.map((s: { licence: string }) => s.licence))
    await screen.findByText(/source commit/)
  })
})
