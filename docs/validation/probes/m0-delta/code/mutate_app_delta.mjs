// M0 delta review, claims 8d / 8e (and the DataSourcesTable half of 8f): app mutation probe.
// Usage:
//   node mutate_app_delta.mjs <app-COPY with node_modules> [id-prefix ...]
// NEVER point this at the real app/: files are rewritten (and restored).
// For each mutant: apply one targeted textual change, run `npx vitest run`, record rc and the
// failing test names, restore, and verify the file's sha256. rc == 0 means the mutant SURVIVED.
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'

const A = process.argv[2]
const ONLY = process.argv.slice(3)
const MF = 'src/lib/MetaFooter.tsx', DS = 'src/lib/DataSourcesSection.tsx', M = 'src/lib/meta.ts'

const MUTANTS = [
  // --- 8d: stale-response guards -------------------------------------------------------------
  ['mf-1 footer guard removed', MF, 'if (!cancelled) setState(', 'if (true) setState('],
  ['mf-2 footer cleanup no-op', MF, '      cancelled = true\n', '      cancelled = false\n'],
  ['mf-3 footer effect deps []', MF, '  }, [url, fetchImpl])', '  }, [])'],
  ['ds-1 sources guard removed', DS, '      if (cancelled) return\n', ''],
  ['ds-2 sources cleanup no-op', DS, '      cancelled = true\n', '      cancelled = false\n'],
  // --- 8e: parseMetaData rules -----------------------------------------------------------------
  ['pm-1 extra keys not detected', M, 'const extra = Object.keys(obj).filter((k) => !expected.includes(k))', 'const extra: string[] = []'],
  ['pm-2 missing keys not detected', M, 'const missing = expected.filter((k) => !Object.hasOwn(obj, k))', 'const missing: string[] = []'],
  ['pm-3 project check removed', M, 'if (!isText(project)) return', 'if (false) return'],
  ['pm-4 milestone check removed', M, 'if (!isMilestone(milestone)) return', 'if (false) return'],
  ['pm-5 title check removed', M, 'if (!isText(title)) return', 'if (false) return'],
  ['pm-6 empty data_sources allowed', M, "if (!Array.isArray(data_sources) || data_sources.length === 0) {", 'if (!Array.isArray(data_sources)) {'],
  ['pm-7 duplicate names allowed', M, 'if (sources.some((o) => o.name === s.name)) return', 'if (false) return'],
  ['pm-8 isText without trim', M, "typeof x === 'string' && x.trim().length > 0", "typeof x === 'string' && x.length > 0"],
  ['pm-9 http allowed', M, '/^https:\\/\\/\\S+$/', '/^https?:\\/\\/\\S+$/'],
  ['pm-10 url regex unanchored at end', M, '/^https:\\/\\/\\S+$/', '/^https:\\/\\/\\S+/'],
  ['pm-11 committed type unchecked', M, "if (typeof s.committed !== 'boolean') return", 'if (false) return'],
  ['pm-12 licence url unchecked', M, 'if (!isHttpsUrl(data_licence.url)) return', 'if (false) return'],
  ['pm-13 attribution unchecked', M, 'if (!isText(data_licence.attribution)) return', 'if (false) return'],
  ['pm-14 applies_to array unchecked', M, 'if (!Array.isArray(applies_to)) return', 'if (false) return'],
  ['pm-15 applies_to names unchecked', M, '    if (!names.includes(n)) {', '    if (false) {'],
  ['pm-16 applies_to not copied', M, 'applies_to: [...applies_to]', 'applies_to: applies_to as string[]'],
  ['pm-17 uses unchecked', M, 'if (!isText(s.uses)) return', 'if (false) return'],
  ['pm-18 source licence unchecked', M, 'if (!isText(s.licence)) return', 'if (false) return'],
  ['pm-19 isObject accepts arrays', M, "typeof x === 'object' && x !== null && !Array.isArray(x)", "typeof x === 'object' && x !== null"],
  ['pm-20 licence name unchecked', M, 'if (!isText(data_licence.name)) return', 'if (false) return'],
  ['pm-21 output licence = name', M, 'licence: s.licence, committed: s.committed })', 'licence: s.name, committed: s.committed })'],
  ['pm-22 milestone may be negative', M, 'Number.isInteger(m) && m >= 0', 'Number.isInteger(m) && m >= -1'],
  ['pm-23 source url unchecked', M, 'if (!isHttpsUrl(s.url)) return', 'if (false) return'],
  ['pm-24 source must be object unchecked', M, 'if (!isObject(s)) return', 'if (false) return'],
  // --- 8f: the table draws what the file says -----------------------------------------------
  ['dt-1 licence linked for every source', DS, '{data_licence.applies_to.includes(s.name) ? (', '{true ? ('],
  ['dt-2 committed text swapped', DS, "{s.committed ? 'derived rows only' : 'never'}", "{s.committed ? 'never' : 'derived rows only'}"],
  ['dt-3 attribution not rendered', DS, '        {data_licence.attribution}\n', ''],
  ['dt-4 licence cell shows licence name not source licence', DS, '                    {s.licence}\n', '                    {data_licence.name}\n'],
]

const sha = (b) => createHash('sha256').update(b).digest('hex')
let survivors = 0, ran = 0
for (const [id, rel, from, to] of MUTANTS) {
  if (ONLY.length && !ONLY.some((o) => id.startsWith(o))) continue
  const f = join(A, rel)
  const before = readFileSync(f)
  const text = before.toString('utf8')
  const n = text.split(from).length - 1
  if (n !== 1) { console.log(`PROBE_INVALID ${id}: pattern found ${n}x`); continue }
  writeFileSync(f, text.replace(from, to))
  let p
  try {
    p = spawnSync('npx', ['vitest', 'run', '--reporter=dot'], { cwd: A, encoding: 'utf8', timeout: 300000 })
  } finally {
    writeFileSync(f, before)
  }
  if (sha(readFileSync(f)) !== sha(before)) throw new Error(`restore failed: ${rel}`)
  ran++
  const out = (p.stdout || '') + (p.stderr || '')
  const failed = [...new Set([...out.matchAll(/FAIL\s+(\S+\.tsx?)\s+>\s+(.+)/g)].map((m) => `${m[1]} > ${m[2].trim()}`))]
  const summary = (out.match(/Tests\s+[^\n]+/) || ['?'])[0]
  const status = p.status === 0 ? 'SURVIVED' : 'KILLED  '
  if (p.status === 0) survivors++
  console.log(`${status} rc=${p.status} ${id.padEnd(46)} | ${summary}`)
  for (const t of failed.slice(0, 4)) console.log(`           - ${t}`)
}
console.log(`mutants run=${ran} survivors=${survivors}`)
