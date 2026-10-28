// C5.1 / C4.4 probe: feed what contract.py emits (JSON lines from contract_py_probe.py) and a list
// of hand-made deviations into the REAL app/src/lib/contract.ts parseEnvelope.
// Usage: node --experimental-strip-types contract_ts_probe.mjs <path/to/contract.ts> <py_envelopes.jsonl> <app/public/data/meta.json>
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
const [contractPath, pyLines, metaPath] = process.argv.slice(2)
const { parseEnvelope } = await import(pathToFileURL(contractPath).href)

const run = (label, text) => {
  let parsed
  try {
    parsed = JSON.parse(text)
  } catch (e) {
    console.log(`${label.padEnd(44)} JSON.parse THROWS ${e.constructor.name}: ${e.message}`)
    return
  }
  const r = parseEnvelope(parsed)
  const x = parsed && parsed.data && typeof parsed.data === 'object' ? parsed.data.x : undefined
  console.log(`${label.padEnd(44)} ok=${r.ok}${r.ok ? '' : ' error=' + r.error}${x !== undefined ? ' data.x=' + x : ''}`)
}

console.log('== (a) every envelope contract.py emitted')
for (const line of readFileSync(pyLines, 'utf8').trim().split('\n')) {
  const { case: c, text } = JSON.parse(line)
  run(c, text)
}
console.log('== (b) the real app/public/data/meta.json')
run('meta.json', readFileSync(metaPath, 'utf8'))

console.log('== (c) deviations (each must be rejected)')
const good = { schema_version: '0.1.0', kind: 'meta', generated_at: '2026-10-27T12:00:00Z', source_commit: 'abc1234', data: { milestone: 0 } }
const dev = {
  'wrong version 0.2.0': { ...good, schema_version: '0.2.0' },
  'version as number': { ...good, schema_version: 0.1 },
  'missing kind': (({ kind, ...r }) => r)(good),
  'missing data': (({ data, ...r }) => r)(good),
  'extra key': { ...good, extra: 1 },
  'extra key __proto__ (via JSON text)': null,
  'time +00:00': { ...good, generated_at: '2026-10-27T12:00:00+00:00' },
  'time no zone': { ...good, generated_at: '2026-10-27T12:00:00' },
  'time lowercase z': { ...good, generated_at: '2026-10-27T12:00:00z' },
  'time 3-digit year (py year 999)': { ...good, generated_at: '999-01-01T00:00:00Z' },
  'data array': { ...good, data: [1] },
  'data null': { ...good, data: null },
  'data string': { ...good, data: 'x' },
  'kind number': { ...good, kind: 5 },
  'source_commit null': { ...good, source_commit: null },
}
for (const [k, v] of Object.entries(dev)) {
  if (v === null) run(k, '{"schema_version":"0.1.0","kind":"meta","generated_at":"2026-10-27T12:00:00Z","source_commit":"a","data":{},"__proto__":{"x":1}}')
  else run(k, JSON.stringify(v))
}
console.log('== (d) bare non-finite tokens, as Python would write them with allow_nan=True')
run('bare NaN in data', '{"schema_version":"0.1.0","kind":"meta","generated_at":"2026-10-27T12:00:00Z","source_commit":"a","data":{"x":NaN}}')
run('bare Infinity in data', '{"schema_version":"0.1.0","kind":"meta","generated_at":"2026-10-27T12:00:00Z","source_commit":"a","data":{"x":Infinity}}')
for (const t of ['NaN', 'Infinity', '-Infinity']) {
  try { JSON.parse(t); console.log(`JSON.parse(${t}) did not throw`) } catch (e) { console.log(`JSON.parse(${t}) -> ${e.constructor.name}: ${e.message}`) }
}
console.log(`node ${process.version}`)
