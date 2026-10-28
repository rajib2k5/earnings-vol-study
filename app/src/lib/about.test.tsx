import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AboutPage, DiagramSections, type AboutContent } from './about'

const base: AboutContent = {
  intro: ['An app.'],
  architecture: { layers: [] },
  sequence: { actors: [], steps: [] },
  activity: { nodes: [], edges: [] },
}

describe('AboutPage use cases', () => {
  it('renders every use case with who, how and the page that delivers it', () => {
    const useCases = [
      { title: 'Size a trade', who: 'A PM', how: 'Set the risk budget and read the size.', page: 'Sizing' },
      { title: 'Audit a model', who: 'Model risk', how: 'Replay the seed and compare.', page: 'Registry' },
    ]
    render(<AboutPage slug="t" storage={null} content={{ ...base, useCases }} />)
    const items = within(screen.getByRole('list', { name: 'Use cases' })).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[1].textContent).toContain('Audit a model')
    expect(items[1].textContent).toContain('Model risk')
    expect(items[1].textContent).toContain('Registry')
  })

  it('omits the section entirely when there are no use cases', () => {
    render(<AboutPage slug="t" storage={null} content={base} />)
    expect(screen.queryByRole('heading', { name: 'Use cases' })).toBeNull()
    expect(screen.queryByRole('list', { name: 'Use cases' })).toBeNull()
  })
})

describe('AboutPage without diagrams, and DiagramSections', () => {
  const intro = { intro: ['An app.'] }
  it('draws no diagram when none is supplied, and renders children after the intro', () => {
    render(
      <AboutPage slug="t" storage={null} content={intro}>
        <h2>Extra section</h2>
      </AboutPage>,
    )
    expect(screen.getByText('An app.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Extra section' })).toBeInTheDocument()
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Architecture' })).toBeNull()
  })
  it('DiagramSections draws only the diagrams it is given', () => {
    render(<DiagramSections slug="t" storage={null} content={{ architecture: { layers: [{ label: 'Core', boxes: ['engine'] }] } }} />)
    expect(screen.getByRole('img', { name: 'Architecture diagram' })).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: 'Sequence diagram' })).toBeNull()
    expect(screen.queryByRole('img', { name: 'Activity diagram' })).toBeNull()
  })
  it('DiagramSections draws all three when all are given', () => {
    render(<DiagramSections slug="t" storage={null} content={base} />)
    expect(screen.getAllByRole('img')).toHaveLength(3)
  })
})
