import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ErrorBoundary } from './ErrorBoundary'

afterEach(() => vi.restoreAllMocks())

function Boom(): never {
  throw new Error('kaboom')
}

describe('ErrorBoundary', () => {
  it('renders its children when nothing throws', () => {
    render(
      <ErrorBoundary fallback={() => <p>fallback</p>}>
        <p>fine</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText('fine')).toBeInTheDocument()
    expect(screen.queryByText('fallback')).toBeNull()
  })
  it('renders the fallback, given the error, when a child throws during render', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {}) // React logs caught render errors
    render(
      <ErrorBoundary fallback={(e) => <p>failed: {e.message}</p>}>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByText('failed: kaboom')).toBeInTheDocument()
  })
})
