// d10: the tests.json parser and withheld p-values (delta claim 5). Bundle first (scratch):
//   app/node_modules/.bin/esbuild <entry re-exporting parseTests> --bundle --format=esm --platform=node --outfile=<scratch>/results_parser.mjs
// Run: node docs/validation/probes/m3-delta/d10_parser.mjs <scratch>/results_parser.mjs
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
const P = await import(pathToFileURL(process.argv[2]).href)
const env = JSON.parse(readFileSync('/home/rajib2k5/dev/earnings-vol-study/app/public/data/tests.json', 'utf8'))
const clone = (x) => JSON.parse(JSON.stringify(x))
const withheld = (d) => d.rows.findIndex((r) => r.g1_size !== null)
const prim = (d) => d.rows.findIndex((r) => r.role === 'primary')
const cases = [
  ['committed file', (d) => d, true],
  ['withheld row: p null, ci null, g1_size given', (d) => d, true],
  ['g1_size next to a p-value', (d) => { d.rows[withheld(d)].p_value = 0.01 }, false],
  ['g1_size 1.2 (not a probability)', (d) => { d.rows[withheld(d)].g1_size = 1.2 }, false],
  ['withheld row with its CI restored', (d) => { const r = d.rows[withheld(d)]; r.ci_lo = -1; r.ci_hi = 1 }, null],
  ['a PRIMARY row withheld (p null, g1_size 0.07)', (d) => { const r = d.rows[prim(d)]; r.p_value = null; r.ci_lo = null; r.ci_hi = null; r.g1_size = 0.07 }, null],
  ['robustness row p null and no g1_size', (d) => { const r = d.rows[withheld(d)]; r.g1_size = null }, null],
]
for (const [label, edit, want] of cases) {
  const d = clone(env.data)
  edit(d)
  const r = P.parseTests(d)
  const verdict = want === null ? '(no rule stated)' : (r.ok === want ? 'as claimed' : 'CONTRADICTS CLAIM')
  console.log(`${label}: ${r.ok ? 'accepted' : 'rejected: ' + r.error} ${verdict}`)
}
