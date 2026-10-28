/**
 * Content of the Architecture page, as plain data. The diagram components in `diagrams.tsx` draw
 * it; `architecture.test.ts` checks the structural rules (unique ids, edges that point at real
 * nodes, labels short enough to fit) so a typo here fails a test instead of drawing a broken figure.
 */
import type { ActEdge, ActNode, ArchLayer, SeqStep } from './diagrams'
import { SCHEMA_VERSION } from './contract'

/** End-to-end data flow, top to bottom. Python does everything down to the JSON; the app only draws. */
export const ARCH_LAYERS: ArchLayer[] = [
  { label: 'DoltHub', boxes: ['earnings_calendar', 'eps_history', 'option_chain'] },
  { label: 'Market data', boxes: ['CBOE VX* single-stock IV', 'yfinance prices'] },
  { label: 'Ingest / cache', boxes: ['parquet under $VOL_DATA_DIR/earnings-vol-study/cache'] },
  { label: 'IV measures', boxes: ['front ATM IV', '30d constant-maturity IV', 'event var. / implied move'] },
  { label: 'Event panel', boxes: ['event window [-10,+10]', 'baseline [-60,-22], clean days'] },
  { label: 'Abnormal IV', boxes: ['abnormal IV vs baseline window'] },
  { label: 'Inference', boxes: ['primary: two-way cluster t', 'robustness: BMP, KP family', 'regressions: two-way SE'] },
  { label: 'Export', boxes: ['tools/export_app_data.py'] },
  { label: 'JSON contract', boxes: [`app/public/data/*.json, schema ${SCHEMA_VERSION}`] },
  { label: 'This app', boxes: ['validate envelope', 'charts and 3D views'] },
]

/** One earnings event travelling through the Python pipeline. Steps index into SEQUENCE_ACTORS. */
export const SEQUENCE_ACTORS: string[] = ['Calendar', 'Resolver', 'IV series', 'Event panel', 'Aggregate', 'JSON']

export const SEQUENCE_STEPS: SeqStep[] = [
  { from: 0, to: 1, label: 'calendar row' },
  { from: 1, to: 1, label: 'day 0 = date (BMO) or next session (AMC)' },
  { from: 1, to: 2, label: 'ticker, day 0' },
  { from: 2, to: 3, label: 'daily IV' },
  { from: 3, to: 3, label: 'slice window [-10,+10] + baseline [-60,-22]' },
  { from: 3, to: 3, label: 'abnormal IV vs baseline' },
  { from: 3, to: 4, label: 'per-event result' },
  { from: 4, to: 4, label: 'aggregate across events' },
  { from: 4, to: 5, label: 'export' },
]

/** The per-milestone workflow. The two "no" edges loop back to the build step; their labels say why. */
export const ACTIVITY_NODES: ActNode[] = [
  { id: 'start', label: 'milestone starts', type: 'start' },
  { id: 'build', label: 'build' },
  { id: 'tests', label: 'tests + coverage gate' },
  { id: 'green', label: 'tests green?', type: 'decision' },
  { id: 'review', label: 'adversarial review' },
  { id: 'holds', label: 'claims survive?', type: 'decision' },
  { id: 'verify', label: 'verify (re-measure)' },
  { id: 'push', label: 'push' },
  { id: 'learner', label: 'learner checkpoint' },
  { id: 'done', label: 'milestone done', type: 'end' },
]

export const ACTIVITY_EDGES: ActEdge[] = [
  { from: 'start', to: 'build' },
  { from: 'build', to: 'tests' },
  { from: 'tests', to: 'green' },
  { from: 'green', to: 'review', label: 'yes' },
  { from: 'green', to: 'build', label: 'no: tests fail' },
  { from: 'review', to: 'holds' },
  { from: 'holds', to: 'verify', label: 'yes' },
  { from: 'holds', to: 'build', label: 'no: refuted' },
  { from: 'verify', to: 'push' },
  { from: 'push', to: 'learner' },
  { from: 'learner', to: 'done' },
]
