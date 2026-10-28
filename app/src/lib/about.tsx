/**
 * About page: overview copy, optional use cases, optional extra sections (children) and the three
 * animated diagrams (architecture, sequence, activity). Content is app-specific and passed in.
 * The diagrams are optional here so an app can show them on a separate page via DiagramSections.
 */
import type { ReactNode } from 'react'
import { ArchDiagram, SequenceDiagram, ActivityDiagram, type ArchLayer, type SeqStep, type ActNode, type ActEdge } from './diagrams'
import { track } from './metrics'
import type { StorageLike } from './storage'

/**
 * One concrete way someone could use this app. `page` names the nav tab that delivers it, so a
 * reader can go and do it; a use case with no page behind it is a claim, not a use case.
 */
export interface UseCase {
  title: string
  who: string
  how: string
  page: string
}

// Self-contained so every app gets a usable layout without touching its own stylesheet; the
// colours come from the app's theme tokens, with fallbacks for apps that name them differently.
const USECASE_STYLE = `
.usecases { list-style: none; margin: 0 0 1rem; padding: 0; display: grid; gap: .8rem; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
.usecase { margin: 0; display: flex; flex-direction: column; gap: .3rem; }
.usecase-title { font-weight: 600; color: var(--ink, inherit); }
.usecase-who { font-size: .8rem; color: var(--accent, currentColor); }
.usecase-how { margin: 0; font-size: .88rem; color: var(--muted, inherit); flex: 1; }
.usecase-page { align-self: flex-start; margin-top: .2rem; }
`

/** The three diagram definitions; each is optional and only the ones given are drawn. */
export interface DiagramContent {
  architecture?: { layers: ArchLayer[] }
  sequence?: { actors: string[]; steps: SeqStep[] }
  activity?: { nodes: ActNode[]; edges: ActEdge[] }
}

export interface AboutContent extends DiagramContent {
  intro: string[]
  useCases?: UseCase[]
}

export function DiagramSections({ slug, content, storage }: { slug: string; content: DiagramContent; storage?: StorageLike | null }) {
  return (
    <>
      {content.architecture && (
        <>
          <h2>Architecture</h2>
          <div className="card">
            <ArchDiagram layers={content.architecture.layers} />
          </div>
        </>
      )}
      {content.sequence && (
        <>
          <h2>Sequence — primary flow</h2>
          <div className="card">
            <SequenceDiagram
              actors={content.sequence.actors}
              steps={content.sequence.steps}
              onReplay={() => track(slug, 'about.replaySequence', undefined, { storage })}
            />
          </div>
        </>
      )}
      {content.activity && (
        <>
          <h2>Activity — decision flow</h2>
          <div className="card">
            <ActivityDiagram nodes={content.activity.nodes} edges={content.activity.edges} />
          </div>
        </>
      )}
    </>
  )
}

export function AboutPage({
  slug,
  content,
  storage,
  children,
}: {
  slug: string
  content: AboutContent
  storage?: StorageLike | null
  /** Extra sections rendered after the intro and use cases, before any diagrams. */
  children?: ReactNode
}) {
  return (
    <section className="about">
      <h2>About — how this system works</h2>
      {content.intro.map((p, i) => (
        <p className="sub" key={i}>
          {p}
        </p>
      ))}
      {content.useCases && content.useCases.length > 0 && (
        <>
          <style>{USECASE_STYLE}</style>
          <h2>Use cases</h2>
          <ul className="usecases" aria-label="Use cases">
            {content.useCases.map((u) => (
              <li className="card usecase" key={u.title}>
                <div className="usecase-title">{u.title}</div>
                <div className="usecase-who">{u.who}</div>
                <p className="usecase-how">{u.how}</p>
                <span className="badge usecase-page">{u.page}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {children}
      <DiagramSections slug={slug} content={content} storage={storage} />
    </section>
  )
}
