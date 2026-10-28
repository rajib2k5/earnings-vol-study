/** Catches errors thrown while rendering its children (e.g. a failed lazy import or no WebGL) and shows a fallback. */
import { Component, type ReactNode } from 'react'

interface Props {
  fallback: (error: Error) => ReactNode
  children: ReactNode
}

export class ErrorBoundary extends Component<Props, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    return this.state.error ? this.props.fallback(this.state.error) : this.props.children
  }
}
