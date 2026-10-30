import { describe, it, expect } from 'vitest'
import { parseEnvelope } from '../lib/contract'
import { failedHypotheses, forestTerms, parseDrivers } from '../lib/drivers'
import { parseEventPaths, seriesOptions } from '../lib/eventPaths'
import { parseSampleFunnel } from '../lib/funnel'
import { parseHeatmap } from '../lib/heatmap'
import { parseImpliedRealised } from '../lib/impliedRealised'
import { parseIvMeasures } from '../lib/ivMeasures'
import { summarizeMeta, formatMilestone, parseMetaData } from '../lib/meta'
import { groupByHypothesis, parseTests, rowsWithRole } from '../lib/results'
import { parseTerrainData } from '../lib/terrainData'

// Contract check against the REAL files the Python exporter wrote to public/data/. If the Python
// side and contract.ts drift apart, this fails (the other tests only use hand-built fixtures).
const files = import.meta.glob('../../public/data/*.json', { eager: true, query: '?raw', import: 'default' }) as Record<string, string>

/** The parsed envelope of `<name>.json` in public/data, or a thrown reason. */
function envelopeOf(name: string) {
  const raw = Object.entries(files).find(([f]) => f.endsWith(`/${name}.json`))?.[1]
  if (raw === undefined) throw new Error(`public/data/${name}.json does not exist (has the Python exporter been run?)`)
  const r = parseEnvelope(JSON.parse(raw))
  if (!r.ok) throw new Error(r.error)
  return r.envelope
}

describe('public/data/*.json (written by the Python exporter)', () => {
  it('contains at least meta.json', () => {
    expect(Object.keys(files).some((f) => f.endsWith('/meta.json'))).toBe(true)
  })
  for (const [path, raw] of Object.entries(files)) {
    it(`${path.split('/').pop()} is valid JSON and satisfies the schema 0.5.0 envelope`, () => {
      const r = parseEnvelope(JSON.parse(raw))
      expect(r.ok, r.ok ? '' : r.error).toBe(true)
    })
  }
  it('meta.json carries a usable milestone number and a kind of "meta"', () => {
    const raw = Object.entries(files).find(([f]) => f.endsWith('/meta.json'))?.[1]
    const r = parseEnvelope(JSON.parse(raw ?? 'null'))
    if (!r.ok) throw new Error(r.error)
    expect(r.envelope.kind).toBe('meta')
    const m = summarizeMeta(r.envelope)
    expect(m.milestone, 'data.milestone must be a non-negative integer').not.toBeNull()
    expect(formatMilestone(m.milestone)).toMatch(/^M\d+$/)
  })
  it('meta.json data passes the data-shape validator the About page uses (sources, licence, attribution)', () => {
    const raw = Object.entries(files).find(([f]) => f.endsWith('/meta.json'))?.[1]
    const env = parseEnvelope(JSON.parse(raw ?? 'null'))
    if (!env.ok) throw new Error(env.error)
    const r = parseMetaData(env.envelope.data)
    if (!r.ok) throw new Error(r.error)
    // Cboe: the VIX close (via FRED VIXCLS) is used for the market adjustment, and AGGREGATES of the
    // VIX-adjusted values are committed (owner decision of 2026-10-29: results.parquet, tests.json,
    // event_paths.json); the VIX series and per-event VIX-adjusted values are not. No Cboe single-stock
    // (VX*) data is committed. Two Yahoo-derived labels are committed (owner decision of 2026-10-29,
    // data/derived/README.md). The Python test ties these flags to the schema registry; this checks the
    // file the app really reads.
    const VIX = 'FRED VIXCLS (Cboe VIX)'
    const VX = 'Cboe single-stock volatility indices (VX*)'
    const byName = (name: string) => r.data.data_sources.find((s) => s.name === name)
    expect(byName(VIX)?.committed, `${VIX} must be listed and committed (aggregates only)`).toBe(true)
    expect(byName(VIX)?.uses, 'the VIX row must say that only aggregates are committed').toMatch(/aggregates of VIX-adjusted values/)
    expect(byName(VX)?.committed, `${VX} must be listed and not committed`).toBe(false)
    expect(byName('Yahoo Finance')?.committed, 'Yahoo Finance must be listed and committed (two labels)').toBe(true)
    for (const s of r.data.data_sources) {
      // any other Cboe-named source would need its own decision: fail until it is added to this test
      if (/Cboe|CBOE/.test(s.name)) expect([VIX, VX], s.name).toContain(s.name)
      if (/Yahoo/.test(s.name)) expect(s.committed, s.name).toBe(true)
    }
    // A source under the data licence is covered by it; every committed source is named in the
    // attribution text, so a committed source the notice forgets fails here.
    for (const s of r.data.data_sources.filter((x) => x.committed)) {
      if (s.licence === r.data.data_licence.name) expect(r.data.data_licence.applies_to, s.name).toContain(s.name)
      expect(r.data.data_licence.attribution, s.name).toContain(s.name.replace('DoltHub ', ''))
    }
  })
  it('meta.json data.files lists the kind of every file in public/data', () => {
    const meta = parseMetaData(envelopeOf('meta').data)
    if (!meta.ok) throw new Error(meta.error)
    for (const [path, raw] of Object.entries(files)) {
      const env = parseEnvelope(JSON.parse(raw))
      if (!env.ok) throw new Error(`${path}: ${env.error}`)
      expect(meta.data.files, `${path} (kind ${env.envelope.kind}) is missing from meta.json data.files`).toContain(env.envelope.kind)
    }
  })
  it('meta.json data.files lists all nine kinds, and public/data holds a file for each', () => {
    const meta = parseMetaData(envelopeOf('meta').data)
    if (!meta.ok) throw new Error(meta.error)
    const kinds = ['meta', 'sample_funnel', 'iv_measures', 'tests', 'event_paths', 'terrain', 'heatmap', 'drivers', 'implied_vs_realised']
    expect([...meta.data.files].sort()).toEqual([...kinds].sort())
    const present = Object.values(files).map((raw) => {
      const env = parseEnvelope(JSON.parse(raw))
      return env.ok ? env.envelope.kind : `invalid: ${env.error}`
    })
    expect(present.sort()).toEqual([...kinds].sort())
  })
  it('sample_funnel.json exists, has kind "sample_funnel" and passes the data-shape validator the Sample page uses', () => {
    const env = envelopeOf('sample_funnel')
    expect(env.kind).toBe('sample_funnel')
    const r = parseSampleFunnel(env.data)
    expect(r.ok, r.ok ? '' : r.error).toBe(true)
  })
  it('sample_funnel.json has its two milestone-2 fields filled: 9 tercile rows (3 samples x 3 terciles) and a non-positive variance count', () => {
    const r = parseSampleFunnel(envelopeOf('sample_funnel').data)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.by_move_tercile, 'by_move_tercile is null: the exporter has not filled it').not.toBeNull()
    expect(r.data.by_move_tercile).toHaveLength(9)
    // Every (sample, tercile) pair appears exactly once; the order is the exporter's business.
    expect(r.data.by_move_tercile?.map((x) => `${x.sample}-${x.tercile}`).sort()).toEqual(
      ['coarse-1', 'coarse-2', 'coarse-3', 'daily-1', 'daily-2', 'daily-3', 'mixed-1', 'mixed-2', 'mixed-3'],
    )
    expect(r.data.by_move_tercile_status).toMatch(/^computed:/)
    expect(r.data.evar_nonpositive, 'evar_nonpositive is null: the exporter has not filled it').not.toBeNull()
    expect(r.data.evar_nonpositive_status).toMatch(/^computed:/)
  })
  it('iv_measures.json exists, has kind "iv_measures" and passes the data-shape validator the IV measures page uses', () => {
    const env = envelopeOf('iv_measures')
    expect(env.kind).toBe('iv_measures')
    const r = parseIvMeasures(env.data)
    expect(r.ok, r.ok ? '' : r.error).toBe(true)
  })

  // ---- milestone 3: tests, event_paths, terrain, heatmap ----

  /** meta.json data and the funnel's look-up count: what the four new files must agree with. */
  function context() {
    const meta = parseMetaData(envelopeOf('meta').data)
    if (!meta.ok) throw new Error(meta.error)
    const funnel = parseSampleFunnel(envelopeOf('sample_funnel').data)
    if (!funnel.ok) throw new Error(funnel.error)
    return { meta: meta.data, lookups: funnel.data.lookups }
  }
  /** Every new file says the labels are provisional while the look-ups are incomplete, and agrees on how many are done. */
  function expectProvisionalAndConsistent(name: string, data: { lookups: { n_done: number; complete: boolean }; caveats: string[] }) {
    const { lookups } = context()
    expect(data.lookups, `${name}.json lookups must equal sample_funnel.json lookups`).toEqual(lookups)
    if (!lookups.complete) expect(data.caveats.join(' '), `${name}.json caveats must say the timing labels are provisional`).toMatch(/provisional/i)
  }

  it('tests.json exists, has kind "tests" and passes the data-shape validator the Results page uses', () => {
    const env = envelopeOf('tests')
    expect(env.kind).toBe('tests')
    const r = parseTests(env.data)
    if (!r.ok) throw new Error(r.error)
    expectProvisionalAndConsistent('tests', r.data)
  })
  it('tests.json has one primary row for each of H1 to H4, and the declared Holm family H1 to H7 binds: all tested, none untested, none left (fix R1)', () => {
    const r = parseTests(envelopeOf('tests').data)
    if (!r.ok) throw new Error(r.error)
    const primary = rowsWithRole(r.data.rows, 'primary')
    expect(primary.map((x) => x.hypothesis)).toEqual(['H1', 'H2', 'H3', 'H4'])
    const declared = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7']
    expect(r.data.holm.family).toEqual(declared)
    expect(r.data.holm.tested).toEqual(declared)
    expect(r.data.holm.untested).toEqual([])
    expect(r.data.holm.left_family).toEqual([])
    // the binding Holm p over H1 to H7 (fix R1)
    expect(primary.map((x) => x.p_holm)).toEqual([4.06e-22, 0.04688, 1, 1])
    // H2's binding season-cut counterfactual (G = 7) is not rejected, and its primary row says so
    const h2 = primary[1]
    expect(h2.note).toContain('Holm p 0.07812')
    const cut = r.data.rows.filter((x) => x.subgroup_key === 'season_cut')
    expect(cut.map((x) => [x.hypothesis, x.role, x.n_clusters, x.p_holm])).toEqual([['H2', 'robustness', 7, 0.07812]])
    // the caveat on the family names the size failure of H5 to H7 and the post-gate sensitivity
    expect(r.data.caveats[1]).toMatch(/H5 \(9\.55%\), H6 \(8\.10%\), H7 \(16\.15%\) failed gate G1's regression size check/)
    expect(r.data.caveats[1]).toMatch(/Sensitivity, not binding: over the family without them \(H1, H2, H3, H4\)/)
    // the page groups the robustness rows under hypotheses; none may fall into the "no hypothesis" group
    expect(groupByHypothesis(rowsWithRole(r.data.rows, 'robustness')).every((g) => g.hypothesis !== null)).toBe(true)
    // gate G1 now also ran for H5 to H7, and all three failed it
    expect(r.data.g1.calibrated.map((c) => c.hypothesis)).toEqual(['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7'])
    expect(r.data.g1.calibrated.filter((c) => !c.pass).map((c) => c.hypothesis)).toEqual(['H5', 'H6', 'H7'])
  })
  it('event_paths.json exists, has kind "event_paths", passes its validator, and agrees with meta.json (window, events, adjustments, subgroups)', () => {
    const env = envelopeOf('event_paths')
    expect(env.kind).toBe('event_paths')
    const r = parseEventPaths(env.data)
    if (!r.ok) throw new Error(r.error)
    expectProvisionalAndConsistent('event_paths', r.data)
    const { meta } = context()
    const [from, to] = meta.params.event_window
    expect(r.data.rel_days).toEqual(Array.from({ length: to - from + 1 }, (_, i) => from + i))
    expect(r.data.per_event, 'one path per event of the sample').toHaveLength(meta.sample.n_events)
    const options = seriesOptions(r.data.series)
    expect(options.adjustments).toEqual(['market', 'mean'])
    expect(options.subgroups.map((g) => g.label).sort()).toEqual(['AMC', 'BMO', 'all'])
    expect(r.data.series).toHaveLength(6)
  })
  it('terrain.json exists, has kind "terrain", passes its validator, and has one row per security and one column per event day of meta.json', () => {
    const env = envelopeOf('terrain')
    expect(env.kind).toBe('terrain')
    const r = parseTerrainData(env.data)
    if (!r.ok) throw new Error(r.error)
    expectProvisionalAndConsistent('terrain', r.data)
    const { meta } = context()
    expect(r.data.rows).toHaveLength(meta.sample.n_securities)
    const [from, to] = meta.params.event_window
    expect(r.data.rel_days).toEqual(Array.from({ length: to - from + 1 }, (_, i) => from + i))
  })
  it('heatmap.json exists, has kind "heatmap", passes its validator, and has the company-by-event-day and company-by-season grids', () => {
    const env = envelopeOf('heatmap')
    expect(env.kind).toBe('heatmap')
    const r = parseHeatmap(env.data)
    if (!r.ok) throw new Error(r.error)
    expectProvisionalAndConsistent('heatmap', r.data)
    expect(r.data.grids.map((g) => g.id)).toEqual(['company_by_event_day', 'company_by_season'])
    const { meta } = context()
    const byDay = r.data.grids[0]
    expect(byDay.row_labels).toHaveLength(meta.sample.n_securities)
    expect(byDay.col_labels).toHaveLength(meta.params.event_window[1] - meta.params.event_window[0] + 1)
  })
  // ---- milestone 4: drivers, implied_vs_realised ----

  it('drivers.json exists, has kind "drivers", passes its validator, and says the timing labels are provisional', () => {
    const env = envelopeOf('drivers')
    expect(env.kind).toBe('drivers')
    const r = parseDrivers(env.data)
    if (!r.ok) throw new Error(r.error)
    expectProvisionalAndConsistent('drivers', r.data)
    expect(r.data.caveats.join(' ')).toMatch(/provisional/i)
  })
  it('drivers.json has the primary crush model first, models that can be plotted, and a Holm family that matches tests.json', () => {
    const r = parseDrivers(envelopeOf('drivers').data)
    if (!r.ok) throw new Error(r.error)
    const tests = parseTests(envelopeOf('tests').data)
    if (!tests.ok) throw new Error(tests.error)
    expect(r.data.models.length).toBeGreaterThan(1)
    expect(r.data.models[0].model_id).toBe('crush_drivers')
    expect(r.data.models.every((m) => m.terms.length > 0)).toBe(true)
    expect(forestTerms(r.data.models[0]).length, 'the primary model must have a coefficient to plot').toBeGreaterThan(0)
    expect(r.data.holm.family).toEqual(tests.data.holm.family)
    expect(r.data.holm.left_family).toEqual(tests.data.holm.left_family)
    expect(r.data.holm.left_family).toEqual([])
    // the old binding family is now a descriptive sensitivity
    expect(r.data.holm.post_gate).toEqual({ family: ['H1', 'H2', 'H3', 'H4'], p_holm: { H1: 2.32e-22, H2: 0.02344, H3: 1, H4: 1 }, season_cut: { H2: 0.04688 } })
  })
  it('drivers.json keeps H5 to H7 primary with their real p-values, binding Holm p, failed G1 size and a note (fix R1)', () => {
    const r = parseDrivers(envelopeOf('drivers').data)
    if (!r.ok) throw new Error(r.error)
    const primaries = r.data.models.flatMap((m) => m.terms.filter((t) => t.role === 'primary'))
    expect(primaries.map((t) => [t.hypothesis, t.statistic, t.p_holm, t.g1_size, t.g1_reps])).toEqual([
      ['H5', 'twoway_date_t', 0.05108, 0.0955, 2000],
      ['H6', 'twoway_date_t', 1, 0.081, 2000],
      ['H7', 'twoway_date_wald', 1, 0.1615, 2000],
    ])
    for (const t of primaries) {
      expect(t.p_value, t.term).not.toBeNull()
      expect(t.note, t.term).toMatch(/^Size check failed: .* a rejection by it would not be trusted/)
    }
    expect(primaries[0].p_value).toBe(0.01022)
    // none of them is rejected at 5%
    expect(primaries.every((t) => (t.p_holm as number) > 0.05)).toBe(true)
    // the caveat the page repeats next to the coefficient tables (fix R7): exactly one, and it gives the measured range
    const nearTables = r.data.caveats.filter((c) => /exploratory/i.test(c))
    expect(nearTables).toHaveLength(1)
    expect(nearTables[0]).toContain('8.10% to 9.55%')
  })
  it('drivers.json gate G1 is the one of tests.json: same band and replications, and the same rejection rate for every primary statistic', () => {
    const d = parseDrivers(envelopeOf('drivers').data)
    const t = parseTests(envelopeOf('tests').data)
    if (!d.ok) throw new Error(d.error)
    if (!t.ok) throw new Error(t.error)
    expect(d.data.g1.band).toEqual(t.data.g1.band)
    expect(d.data.g1.reps).toBe(t.data.g1.reps)
    const rates = new Map(t.data.g1.calibrated.map((c) => [`${c.hypothesis} ${c.statistic}`, c.rejection_rate]))
    for (const c of d.data.g1.calibrated.filter((x) => x.primary)) expect(rates.get(`${c.hypothesis} ${c.statistic}`), `${c.hypothesis} ${c.statistic}`).toBe(c.rejection_rate)
    // the hypotheses whose primary check failed are the ones the sensitivity leaves out, not ones that left the family
    expect(failedHypotheses(d.data.g1.calibrated)).toEqual(['H5', 'H6', 'H7'])
    expect(d.data.holm.family.filter((h) => !d.data.holm.post_gate.family.includes(h))).toEqual(['H5', 'H6', 'H7'])
  })
  it('implied_vs_realised.json exists, has kind "implied_vs_realised", passes its validator, and says the timing labels are provisional', () => {
    const env = envelopeOf('implied_vs_realised')
    expect(env.kind).toBe('implied_vs_realised')
    const r = parseImpliedRealised(env.data)
    if (!r.ok) throw new Error(r.error)
    expectProvisionalAndConsistent('implied_vs_realised', r.data)
    expect(r.data.caveats.join(' ')).toMatch(/provisional/i)
  })
  it('implied_vs_realised.json has one point per event of its summary, the counts of the summary, the 0.425 benchmark, and an H7 gate verdict equal to drivers.json', () => {
    const r = parseImpliedRealised(envelopeOf('implied_vs_realised').data)
    const d = parseDrivers(envelopeOf('drivers').data)
    if (!r.ok) throw new Error(r.error)
    if (!d.ok) throw new Error(d.error)
    const { points, summary } = r.data
    expect(points).toHaveLength(summary.n)
    expect(points.filter((p) => p.implied_abs_move_total !== null)).toHaveLength(summary.n_with_implied_abs_move)
    expect(points.filter((p) => p.implied_move_status === 'nonpositive_event_variance')).toHaveLength(summary.n_evar_nonpositive)
    expect(summary.share_exceed_benchmark).toBe(0.425)
    const h7 = d.data.g1.calibrated.find((c) => c.hypothesis === 'H7' && c.primary)
    const h7OneWay = d.data.g1.calibrated.find((c) => c.hypothesis === 'H7' && c.statistic === 'cluster_date_wald')
    const h7Term = d.data.models.flatMap((m) => m.terms).find((t) => t.hypothesis === 'H7' && t.role === 'primary')
    const reg = summary.regression
    expect(reg.g1_rate).toBe(h7?.rejection_rate)
    expect(reg.g1_pass).toBe(h7?.pass)
    // fix R1: H7 stays primary, with its binding Holm p and its failed size check
    expect([reg.role, reg.wald_p, reg.p_holm, reg.g1_rate, reg.g1_pass, reg.g1_bar]).toEqual(['primary', 0.2751, 1, 0.1615, false, 0.063])
    expect([reg.wald_p, reg.p_holm]).toEqual([h7Term?.p_value, h7Term?.p_holm])
    expect(reg.g1_bar).toBe(d.data.g1.band[1])
    // the one-way Wald failed its own check (the H7 cluster_date_wald entry of drivers.json), so its p-value is withheld
    expect([reg.g1_rate_one_way, reg.g1_pass_one_way, reg.wald_p_one_way]).toEqual([0.17, false, null])
    expect(reg.g1_rate_one_way).toBe(h7OneWay?.rejection_rate)
  })
})
