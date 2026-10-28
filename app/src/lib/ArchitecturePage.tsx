/** Architecture page: the three diagrams, drawn from the plain data in architecture.ts. */
import { DiagramSections } from './about'
import { ACTIVITY_EDGES, ACTIVITY_NODES, ARCH_LAYERS, SEQUENCE_ACTORS, SEQUENCE_STEPS } from './architecture'

export function ArchitecturePage({ slug }: { slug: string }) {
  return (
    <section className="architecture">
      <p className="sub">
        Python does all the work, from raw data to test statistics, and writes JSON. This app only reads and draws that JSON. Below: the end-to-end data flow,
        one earnings event travelling through the pipeline, and the workflow each milestone follows.
      </p>
      <DiagramSections
        slug={slug}
        content={{
          architecture: { layers: ARCH_LAYERS },
          sequence: { actors: SEQUENCE_ACTORS, steps: SEQUENCE_STEPS },
          activity: { nodes: ACTIVITY_NODES, edges: ACTIVITY_EDGES },
        }}
      />
    </section>
  )
}
