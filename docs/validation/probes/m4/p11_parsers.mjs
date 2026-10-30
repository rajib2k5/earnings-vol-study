// p11 (claim 11): the contract-0.5.0 parsers against the committed files and malformed payloads.
// Run: node docs/validation/probes/m4/p11_parsers.mjs <bundle.mjs> [--falsify]
// The bundle is an esbuild bundle of parseDrivers, parseImpliedRealised, parseTests (scratch).
// --falsify swaps every parser for one that accepts anything: every malformed case must then "pass".
import { readFileSync } from 'node:fs'
const mod = await import(process.argv[2])
const fals = process.argv.includes('--falsify')
const P = fals ? { parseDrivers: () => ({ ok: true }), parseImpliedRealised: () => ({ ok: true }), parseTests: () => ({ ok: true }) } : mod
const load = (k) => JSON.parse(readFileSync(`app/public/data/${k}.json`, 'utf8')).data
const clone = (x) => JSON.parse(JSON.stringify(x))
let bad = 0
const expect = (name, parser, data, wantOk) => {
  const r = P[parser](data)
  const ok = r.ok === wantOk
  if (!ok) bad++
  console.log(`${ok ? 'ok  ' : 'MISS'} ${name}: ${r.ok ? 'accepted' : 'rejected'}${r.ok ? '' : ' (' + String(r.error).slice(0, 90) + ')'}`)
}
const D = load('drivers'), I = load('implied_vs_realised'), T = load('tests')
expect('drivers committed', 'parseDrivers', D, true)
expect('implied committed', 'parseImpliedRealised', I, true)
expect('tests committed', 'parseTests', T, true)
const term = (d, pred) => { for (const m of d.models) for (const t of m.terms) if (pred(t)) return t }
const md = (f) => { const d = clone(D); f(d); return d }
expect('D withheld primary (g1_size on role primary)', 'parseDrivers', md((d) => { const t = term(d, (t) => t.hypothesis === 'H5' && t.statistic === 'twoway_date_t' && t.role !== 'robustness'); t.role = 'primary'; t.p_value = null; t.ci_lo = null; t.ci_hi = null; t.g1_size = 0.0955; t.g1_reps = 2000 }), false)
expect('D withheld robustness row keeps its CI', 'parseDrivers', md((d) => { const t = term(d, (t) => t.g1_size !== null); t.ci_lo = 0.001; t.ci_hi = 0.02 }), false)
expect('D silent withheld primary (role primary, p null, no g1_size)', 'parseDrivers', md((d) => { const t = term(d, (t) => t.hypothesis === 'H5' && t.statistic === 'twoway_date_t' && t.role !== 'robustness'); t.role = 'primary'; t.p_value = null }), false)
expect('D p_value 1.5', 'parseDrivers', md((d) => { term(d, (t) => t.p_value !== null).p_value = 1.5 }), false)
expect('D coef as string', 'parseDrivers', md((d) => { term(d, (t) => t.coef !== null).coef = '0.01' }), false)
expect('D extra key in a term', 'parseDrivers', md((d) => { term(d, () => true).extra = 1 }), false)
expect('D missing key in a term', 'parseDrivers', md((d) => { delete term(d, () => true).se }), false)
expect('D ci_lo > ci_hi', 'parseDrivers', md((d) => { const t = term(d, (t) => t.ci_lo !== null); [t.ci_lo, t.ci_hi] = [t.ci_hi, t.ci_lo] }), false)
expect('D hypothesis H8', 'parseDrivers', md((d) => { term(d, (t) => t.hypothesis === 'H5').hypothesis = 'H8' }), false)
expect('D all_declared 1.2', 'parseDrivers', md((d) => { d.holm.all_declared.H5 = 1.2 }), false)
expect('D H5 both in family and left_family', 'parseDrivers', md((d) => { d.holm.family = [...d.holm.family, 'H5'] }), false)
expect('D g1 calibrated pass true above the band', 'parseDrivers', md((d) => { const c = d.g1.calibrated.find((c) => c.primary); c.pass = true }), false)
expect('D exploratory row carries p_holm', 'parseDrivers', md((d) => { term(d, (t) => t.role === 'exploratory' && t.p_value !== null).p_holm = 0.04 }), false)
expect('D n negative', 'parseDrivers', md((d) => { d.models[0].n = -3 }), false)
expect('D g1_size without g1_reps', 'parseDrivers', md((d) => { term(d, (t) => t.g1_size !== null).g1_reps = null }), false)
const mi = (f) => { const d = clone(I); f(d); return d }
expect('I regression role primary with g1_pass false', 'parseImpliedRealised', mi((d) => { d.summary.regression.role = 'primary' }), false)
expect('I wald_p 1.5', 'parseImpliedRealised', mi((d) => { d.summary.regression.wald_p = 1.5 }), false)
expect('I b_ci reversed', 'parseImpliedRealised', mi((d) => { d.summary.regression.b_ci = [1.07, 0.46] }), false)
expect('I benchmark 0.5', 'parseImpliedRealised', mi((d) => { d.summary.share_exceed_benchmark = 0.5 }), false)
expect('I event_var as string', 'parseImpliedRealised', mi((d) => { d.points[0].event_var = 'x' }), false)
expect('I extra key in a point', 'parseImpliedRealised', mi((d) => { d.points[0].vix = 1 }), false)
expect('I withheld one-way Wald p given (p while G1 failed it)', 'parseImpliedRealised', mi((d) => { d.summary.regression.wald_p_one_way = 0.39 }), false)
expect('I duplicate event_id', 'parseImpliedRealised', mi((d) => { d.points[1].event_id = d.points[0].event_id }), false)
const mt = (f) => { const d = clone(T); f(d); return d }
const prow = (d) => d.rows.find((r) => r.role === 'primary')
expect('T withheld primary (g1_size)', 'parseTests', mt((d) => { const r = prow(d); r.p_value = null; r.ci_lo = null; r.ci_hi = null; r.g1_size = 0.07; r.g1_reps = 2000 }), false)
expect('T withheld row keeps its CI', 'parseTests', mt((d) => { const r = d.rows.find((r) => r.g1_size !== null); r.ci_lo = -0.1; r.ci_hi = 0.1 }), false)
expect('T silent withheld primary (p null, no g1_size)', 'parseTests', mt((d) => { const r = prow(d); r.p_value = null }), false)
console.log(`MISSES ${bad}`)
process.exit(bad ? 1 : 0)
