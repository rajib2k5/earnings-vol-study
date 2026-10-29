// p09: the contract-0.4.0 parsers accept the committed files and reject malformed payloads (claim 9).
// Bundle first (scratch, not the repo):
//   app/node_modules/.bin/esbuild <entry.ts re-exporting the five parsers> --bundle --format=esm --platform=node --outfile=<scratch>/parsers.mjs
// Run: node docs/validation/probes/m3/p09_parsers.mjs <scratch>/parsers.mjs [--falsify]
// --falsify: the "malformed" payloads are the unmodified files, so every "must reject" line fails.
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const P = await import(pathToFileURL(process.argv[2]).href)
const FALSIFY = process.argv.includes('--falsify')
const load = (n) => JSON.parse(readFileSync(`/home/rajib2k5/dev/earnings-vol-study/app/public/data/${n}.json`, 'utf8'))
const clone = (x) => JSON.parse(JSON.stringify(x))
const parsers = { tests: P.parseTests, event_paths: P.parseEventPaths, terrain: P.parseTerrainData, heatmap: P.parseHeatmap }
let bad = 0
for (const [name, parse] of Object.entries(parsers)) {
  const env = load(name)
  const e = P.parseEnvelope(env)
  const r = parse(env.data)
  console.log(`accept ${name}: envelope ok=${e.ok} schema_version=${env.schema_version} data ok=${r.ok}${r.ok ? '' : ' ' + r.error}`)
  if (!e.ok || !r.ok) bad++
}
const muts = {
  tests: [
    ['p_value 1.5', (d) => { d.rows[0].p_value = 1.5 }],
    ['estimate as string', (d) => { d.rows[0].estimate = '-0.2' }],
    ['role unknown', (d) => { d.rows[0].role = 'headline' }],
    ['row extra key', (d) => { d.rows[0].beta = 0.3 }],
    ['row missing key', (d) => { delete d.rows[0].se }],
    ['ci_lo > ci_hi', (d) => { const r = d.rows.find((x) => x.ci_lo !== null); [r.ci_lo, r.ci_hi] = [r.ci_hi + 1, r.ci_lo] }],
    ['g1 band decreasing', (d) => { d.g1.band = [0.07, 0.03] }],
    ['g1 pass not boolean', (d) => { d.g1.calibrated[0].pass = 'yes' }],
    ['holm family not list', (d) => { d.holm.family = 'H1' }],
    ['caveats empty string', (d) => { d.caveats.push('') }],
  ],
  event_paths: [
    ['series mean wrong length', (d) => { d.series[0].mean.pop() }],
    ['per_event value string', (d) => { d.per_event[0].values[0] = 'x' }],
    ['adjustment unknown', (d) => { d.series[0].adjustment = 'vix' }],
    ['duplicate series', (d) => { d.series.push(clone(d.series[0])) }],
  ],
  terrain: [
    ['ragged values row', (d) => { d.values[0].pop() }],
    ['rows/values count differ', (d) => { d.rows.pop() }],
  ],
  heatmap: [
    ['n negative', (d) => { d.grids[0].n[0][0] = -1 }],
    ['values not matrix', (d) => { d.grids[0].values[0] = 3 }],
  ],
}
for (const [name, list] of Object.entries(muts)) {
  for (const [label, f] of list) {
    const d = clone(load(name).data)
    if (!FALSIFY) f(d)
    const r = parsers[name](d)
    const ok = !r.ok
    if (!ok) bad++
    console.log(`${ok ? 'rejected' : 'ACCEPTED'} ${name}: ${label}${r.ok ? '' : ' -> ' + String(r.error).slice(0, 90)}`)
  }
}
const env = load('tests'); env.schema_version = '0.3.0'
console.log(`envelope 0.3.0 rejected: ${!P.parseEnvelope(env).ok}`)
if (P.parseEnvelope(env).ok) bad++
console.log(`SUMMARY bad=${bad}`)
process.exit(bad ? 1 : 0)
