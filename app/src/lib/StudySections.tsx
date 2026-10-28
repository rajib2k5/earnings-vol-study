/** About-page sections for this study: questions, data sources and licences, status, disclaimer. */
import { DataSourcesSection } from './DataSourcesSection'
import { DISCLAIMER, MILESTONES, QUESTIONS } from './studyContent'

export function StudySections() {
  return (
    <>
      <h2>Questions the study answers</h2>
      <ol className="sub" aria-label="Questions">
        {QUESTIONS.map((q) => (
          <li key={q}>{q}</li>
        ))}
      </ol>

      <h2>Data sources and licences</h2>
      <DataSourcesSection />

      <h2>Milestone status</h2>
      <ul aria-label="Milestones" className="sub">
        {MILESTONES.map((m) => (
          <li key={m.id}>
            <span className="badge">{`M${m.id}`}</span>
            {m.title} — <strong>{m.status}</strong>
          </li>
        ))}
      </ul>

      <h2>Not financial advice</h2>
      <p className="sub">{DISCLAIMER}</p>
    </>
  )
}
