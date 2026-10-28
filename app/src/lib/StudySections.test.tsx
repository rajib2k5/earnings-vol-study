import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { StudySections } from './StudySections'
import { DISCLAIMER, MILESTONES, QUESTIONS } from './studyContent'
import { jsonFetch, META_DATA_FIXTURE, META_FIXTURE } from '../test/metaFixture'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(jsonFetch(META_FIXTURE)))
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('StudySections', () => {
  it('lists every question, the data sources from meta.json, and the milestone status', async () => {
    render(<StudySections />)
    expect(within(screen.getByRole('list', { name: 'Questions' })).getAllByRole('listitem')).toHaveLength(QUESTIONS.length)
    expect(screen.getByRole('heading', { name: 'Data sources and licences' })).toBeInTheDocument()
    const rows = within(await screen.findByRole('table')).getAllByRole('row')
    expect(rows).toHaveLength(META_DATA_FIXTURE.data_sources.length + 1) // + header row
    for (const s of META_DATA_FIXTURE.data_sources) expect(screen.getByRole('link', { name: s.name })).toHaveAttribute('href', s.url)
    const milestones = within(screen.getByRole('list', { name: 'Milestones' })).getAllByRole('listitem')
    expect(milestones).toHaveLength(MILESTONES.length)
    expect(milestones[0]).toHaveTextContent('M0')
    expect(milestones[0]).toHaveTextContent(MILESTONES[0].status)
  })
  it('shows the attribution text from meta.json and the "Not financial advice" section', async () => {
    render(<StudySections />)
    expect(await screen.findByText(META_DATA_FIXTURE.data_licence.attribution)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Not financial advice' })).toBeInTheDocument()
    expect(screen.getByText(DISCLAIMER)).toBeInTheDocument()
  })
  it('keeps the rest of the page, and shows an error instead of the table, when meta.json cannot be loaded', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500 }) as Response))
    render(<StudySections />)
    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 500')
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.getByRole('list', { name: 'Questions' })).toBeInTheDocument()
    expect(screen.getByText(DISCLAIMER)).toBeInTheDocument()
  })
})
