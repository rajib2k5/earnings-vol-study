// C8.1 / C8.3 / C8.4 mutation probe for the app. Usage:
//   node mutate_app.mjs <app-COPY with node_modules>      (never the real app/: files are rewritten)
// For each mutant: apply one targeted textual change, run `npx vitest run`, record rc and the
// failing test names, restore, and verify the file's sha256. rc == 0 means the mutant SURVIVED.
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'

const A = process.argv[2]
const C = 'src/lib/contract.ts', T = 'src/lib/terrain.ts', M = 'src/lib/meta.ts', R = 'src/lib/rng.ts'
const E = 'src/three/EventTerrain3D.tsx', I = 'src/lib/illustrative.ts'
const MUTANTS = [
  ['ctr-1 extra keys allowed', C, 'if (missing.length > 0 || extra.length > 0) {', 'if (missing.length > 0) {'],
  ['ctr-2 offsets accepted', C, String.raw`(?:\.\d+)?Z$/`, String.raw`(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/`],
  ['ctr-3 no round-trip date check', C, 'return roundTrip.slice(0, 19) === s.slice(0, 19)', 'return roundTrip.length > 0'],
  ['ctr-4 arrays count as objects', C, "typeof x === 'object' && x !== null && !Array.isArray(x)", "typeof x === 'object' && x !== null"],
  ['ctr-5 non-string version falls through', C, "if (Object.hasOwn(input, 'schema_version') && input.schema_version !== SCHEMA_VERSION) {", "if (typeof input.schema_version === 'string' && input.schema_version !== SCHEMA_VERSION) {"],
  ['ctr-6 inherited keys count', C, 'ENVELOPE_KEYS.filter((k) => !Object.hasOwn(input, k))', 'ENVELOPE_KEYS.filter((k) => !(k in input))'],
  ['ter-1 winding flipped', T, 'indices.push(a, c, b, b, c, d)', 'indices.push(a, b, c, b, d, c)'],
  ['ter-2 hole check misses corner d', T, 'if (isMissing[a] || isMissing[b] || isMissing[c] || isMissing[d]) continue', 'if (isMissing[a] || isMissing[b] || isMissing[c]) continue'],
  ['ter-3 lerp not clamped', T, 'const k = Math.min(1, Math.max(0, t))', 'const k = t'],
  ['ter-4 sRGB gamma 2.2', T, '((c + 0.055) / 1.055) ** 2.4', '((c + 0.055) / 1.055) ** 2.2'],
  ['ter-5 single sample off-centre', T, 'return n === 1 ? 0 :', 'return n === 1 ? -0.5 * extent :'],
  ['ter-6 #rgb expands wrong', T, '.map((c) => c + c)', ".map((c) => c + '0')"],
  ['ter-7 flat grid at top', T, 'const t = span === 0 ? 0 : (v - min) / span', 'const t = span === 0 ? 1 : (v - min) / span'],
  ['met-1 fractional milestone ok', M, "typeof m === 'number' && Number.isInteger(m) && m >= 0", "typeof m === 'number' && Number.isFinite(m) && m >= 0"],
  ['met-2 negative milestone ok', M, 'Number.isInteger(m) && m >= 0', 'Number.isInteger(m)'],
  ['met-3 no no-cache', M, "res = await fetchImpl(url, { cache: 'no-cache' })", 'res = await fetchImpl(url)'],
  ['met-4 HTTP status ignored', M, 'if (!res.ok) return', 'if (false) return'],
  ['met-5 unknown shown as M?', M, "milestone === null ? 'unknown'", "milestone === null ? 'M?'"],
  ['met-6 string milestone coerced', M, 'milestone: isMilestone(m) ? m : null,', 'milestone: isMilestone(Number(m)) ? Number(m) : null,'],
  ['rng-1 increment constant', R, 'a = (a + 0x6d2b79f5) >>> 0', 'a = (a + 0x6d2b79f4) >>> 0'],
  ['rng-2 seed not uint32', R, 'let a = seed >>> 0', 'let a = seed'],
  ['rng-3 divisor 2^32-1', R, '>>> 0) / 4294967296', '>>> 0) / 4294967295'],
  ['rng-4 gaussian log(0)', R, 'const u = 1 - rand()', 'const u = rand()'],
  ['rng-5 shift 15 -> 16', R, 'Math.imul(t ^ (t >>> 15), t | 1)', 'Math.imul(t ^ (t >>> 16), t | 1)'],
  ['3d-1 ignores reduced motion', E, 'useState(() => controlsConfig(prefersReducedMotion()))', 'useState(() => controlsConfig(false))'],
  ['3d-2 label hyphen not em dash', I, "'Illustrative synthetic shape — not data'", "'Illustrative synthetic shape - not data'"],
  ['3d-3 label not rendered', E, '<span className="terrain-label">{ILLUSTRATIVE_LABEL}</span>', '<span className="terrain-label" />'],
]
const sha = (b) => createHash('sha256').update(b).digest('hex')
let survivors = 0
for (const [id, rel, from, to] of MUTANTS) {
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
  const out = (p.stdout || '') + (p.stderr || '')
  const failed = [...new Set([...out.matchAll(/FAIL\s+(\S+\.tsx?)\s+>\s+(.+)/g)].map((m) => `${m[1]} > ${m[2].trim()}`))]
  const summary = (out.match(/Tests\s+[^\n]+/) || ['?'])[0]
  const status = p.status === 0 ? 'SURVIVED' : 'KILLED  '
  if (p.status === 0) survivors++
  console.log(`${status} rc=${p.status} ${id.padEnd(40)} | ${summary}`)
  for (const t of failed.slice(0, 4)) console.log(`           - ${t}`)
}
console.log(`mutants=${MUTANTS.length} survivors=${survivors}`)
