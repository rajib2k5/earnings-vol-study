import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { ProvisionalNotice } from './ProvisionalNotice'

const CAVEATS = ['Fixture caveat one.', 'Fixture caveat two.']

describe('ProvisionalNotice', () => {
  it('says the timing labels are provisional, with the number of look-ups done, while the look-ups are not complete', () => {
    render(<ProvisionalNotice lookups={{ n_done: 7, complete: false }} caveats={CAVEATS} />)
    const notice = screen.getByRole('complementary', { name: 'Provisional timing labels' })
    expect(notice).toHaveTextContent('provisional')
    expect(notice).toHaveTextContent(
      'Timing labels are provisional: 7 timing look-ups are done and the look-ups are not complete, so some events may sit on the wrong day 0. Every number on this page depends on those labels.',
    )
  })
  it('lists every caveat, in the order of the file', () => {
    render(<ProvisionalNotice lookups={{ n_done: 7, complete: false }} caveats={CAVEATS} />)
    const items = within(screen.getByRole('list', { name: 'Caveats' })).getAllByRole('listitem')
    expect(items.map((li) => li.textContent)).toEqual(CAVEATS)
  })
  it('takes the look-up count from the file: 0 done is stated as 0, not left out', () => {
    render(<ProvisionalNotice lookups={{ n_done: 0, complete: false }} caveats={[]} />)
    expect(screen.getByRole('complementary')).toHaveTextContent('0 timing look-ups are done')
  })
  it('does not call the labels provisional once the look-ups are complete', () => {
    render(<ProvisionalNotice lookups={{ n_done: 1353, complete: true }} caveats={CAVEATS} />)
    const notice = screen.getByRole('complementary')
    expect(notice).toHaveTextContent('Timing look-ups are complete: 1353 done.')
    expect(notice).not.toHaveTextContent('provisional')
    expect(within(notice).getByText('complete')).toBeInTheDocument()
  })
  it('draws no empty list when the file has no caveats', () => {
    render(<ProvisionalNotice lookups={{ n_done: 7, complete: false }} caveats={[]} />)
    expect(screen.queryByRole('list')).toBeNull()
  })
})
