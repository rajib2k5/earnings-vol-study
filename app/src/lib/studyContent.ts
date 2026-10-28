/**
 * Plain-data content for the About page: what the study asks and how far along the work is. Kept as
 * data (not JSX) so tests can check it. Where the data comes from, its licence and the attribution
 * text are NOT here: Python writes them into `data/meta.json` and the About page reads them there.
 */

export const PROJECT_SLUG = 'earnings-vol-study'
export const PROJECT_TITLE = 'Earnings & Implied Volatility'

export const PITCH =
  'An event study of how earnings announcements move options implied volatility: the run-up, the crush and what drives them.'

/** About-page intro paragraphs (the pitch comes first). */
export const ABOUT_INTRO: string[] = [
  PITCH,
  'Python computes every number. This app only draws the JSON files that Python exports and checks, so no result is calculated in the browser. The 3D preview is a labelled synthetic shape, not data. The Architecture page shows how the data flows.',
]

export const QUESTIONS: string[] = [
  'Does implied volatility run up in the days before an earnings announcement?',
  'How big is the "crush" right after the announcement, and how quickly does IV settle?',
  'Is IV abnormal compared with a baseline window (sessions -60 to -22, minus days near the same company’s other reports), and is that statistically significant? Primary test: a t-test on the plain mean with two-way cluster-robust standard errors, by announcement date and company for the crush, and by earnings season and company for the run-up and persistence (a randomisation p-value by season when seasons are unbalanced). BMP and the Kolari-Pynnönen family are reported as robustness checks of the precision-weighted mean.',
  'What drives the size of the run-up and the crush: the earnings surprise, or the level of IV beforehand?',
  'Do the moves options imply for earnings match the moves that are actually realised?',
]

export type MilestoneStatus = 'planned' | 'in progress' | 'done'

export interface Milestone {
  id: number
  title: string
  status: MilestoneStatus
}

/** M0 is the only milestone recorded here; add a line when the next one starts. */
export const MILESTONES: Milestone[] = [{ id: 0, title: 'App shell: architecture page, JSON data contract, 3D proof of life', status: 'in progress' }]

export const DISCLAIMER =
  'Not financial advice. This is an educational research project. Nothing here is a recommendation to buy, sell or hold any security or option, and past patterns in implied volatility do not predict future returns.'
